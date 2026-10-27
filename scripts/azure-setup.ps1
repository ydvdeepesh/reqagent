<#
.SYNOPSIS
  One-time Azure setup for ReqAgent: Container Apps deployment plus GitHub Actions OIDC login.

.DESCRIPTION
  Run from the repo root in PowerShell, after `az login`:
      .\scripts\azure-setup.ps1
  Every step explains what it creates and waits for Enter. Safe to re-run: existing
  resources are reused. API keys are read from .env and never printed.

  Creates (all inside one resource group, so deleting the group removes everything):
    - Container Apps environment + Log Analytics workspace
    - Container app "reqagent" (0.5 CPU, 1 GiB, scales to zero, at most 1 replica)
  And outside the group:
    - Entra app registration "reqagent-github" with a federated credential for
      GitHub Actions on main, and Contributor on the resource group only.
#>
param(
    [string]$ResourceGroup = "reqagent-rg",
    [string]$Location = "germanywestcentral",
    [string]$EnvName = "reqagent-env",
    [string]$AppName = "reqagent",
    [string]$Repo = "ydvdeepesh/reqagent",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Image = "ghcr.io/$($Repo.ToLower()):latest"

function Step($n, $title, $what) {
    Write-Host ""
    Write-Host "=== Step ${n}: $title ===" -ForegroundColor Cyan
    Write-Host $what
    Read-Host "Press Enter to run this step (Ctrl+C to stop)" | Out-Null
}

function Invoke-Az {
    # Runs az and stops the script on failure, so nothing continues on a half-done step.
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed (exit $LASTEXITCODE)" }
    return $out
}

function Test-Az {
    # True if the az command succeeds. Errors are expected here ("not found"), so they are
    # silenced instead of stopping the script (Windows PowerShell 5.1 would treat stderr as fatal).
    $ErrorActionPreference = "Continue"
    & az @args -o none 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Read-DotEnv($path) {
    $vars = @{}
    if (-not (Test-Path $path)) { throw "$path not found. Run from the repo root, or pass -EnvFile." }
    foreach ($line in Get-Content $path) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $key, $value = $line.Split("=", 2)
        $value = ($value -replace '\s+#.*$', '').Trim().Trim('"').Trim("'")
        if ($value -ne "") { $vars[$key.Trim()] = $value }
    }
    return $vars
}

# --- Step 0 ------------------------------------------------------------------
Step 0 "Check tools and account" "Checks that the Azure CLI is installed and shows which subscription will be used."
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI not found. Install it: winget install -e --id Microsoft.AzureCLI, then open a new terminal and run az login."
}
$account = Invoke-Az account show -o json | ConvertFrom-Json
Write-Host "Subscription: $($account.name) ($($account.id))"
Write-Host "Tenant:       $($account.tenantId)"
$ok = Read-Host "Use this subscription? (y/n)"
if ($ok -ne "y") { throw "Pick the right one with: az account set --subscription <id>, then re-run." }
$SubId = $account.id
$TenantId = $account.tenantId
Invoke-Az extension add --name containerapp --upgrade --yes --only-show-errors | Out-Null

# --- Step 1 ------------------------------------------------------------------
Step 1 "Check the container image is public" "Azure pulls $Image without a password, so the GHCR package must be public."
$pullable = $false
try {
    $token = (Invoke-RestMethod "https://ghcr.io/token?scope=repository:$($Repo.ToLower()):pull").token
    Invoke-WebRequest -Method Head -UseBasicParsing -Uri "https://ghcr.io/v2/$($Repo.ToLower())/manifests/latest" `
        -Headers @{ Authorization = "Bearer $token"; Accept = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json" } | Out-Null
    $pullable = $true
} catch { }
if (-not $pullable) {
    Write-Host "The image is not publicly pullable yet." -ForegroundColor Yellow
    Write-Host "Open https://github.com/ydvdeepesh?tab=packages -> reqagent -> Package settings -> Change visibility -> Public."
    Write-Host "(If there is no package yet, wait for the 'publish' job on main to finish.)"
    Read-Host "Press Enter once it is public" | Out-Null
}

# --- Step 2 ------------------------------------------------------------------
Step 2 "Resource group and Container Apps environment" "Registers the Container Apps providers, creates resource group '$ResourceGroup' in $Location and environment '$EnvName' (takes 2-4 minutes)."
Invoke-Az provider register --namespace Microsoft.App --wait | Out-Null
Invoke-Az provider register --namespace Microsoft.OperationalInsights --wait | Out-Null
Invoke-Az group create -n $ResourceGroup -l $Location -o none
if (Test-Az containerapp env show -n $EnvName -g $ResourceGroup) { Write-Host "Environment exists, reusing it." }
else { Invoke-Az containerapp env create -n $EnvName -g $ResourceGroup -l $Location -o none }

# --- Step 3 ------------------------------------------------------------------
Step 3 "Container app with API keys as secrets" "Creates (or updates) app '$AppName' from $Image. Keys from $EnvFile are stored as Container Apps secrets, not as plain environment variables."
$dotenv = Read-DotEnv $EnvFile
$secretMap = @{ "GROQ_API_KEY" = "groq-api-key"; "GOOGLE_API_KEY" = "google-api-key"; "LANGSMITH_API_KEY" = "langsmith-api-key" }
$secrets = @(); $envVars = @()
foreach ($k in $secretMap.Keys) {
    if ($dotenv.ContainsKey($k)) {
        $secrets += "$($secretMap[$k])=$($dotenv[$k])"
        $envVars += "$k=secretref:$($secretMap[$k])"
    }
}
foreach ($k in @("REQAGENT_LLM", "REQAGENT_MODEL", "REQAGENT_RPS", "LANGSMITH_TRACING", "LANGSMITH_PROJECT")) {
    if ($dotenv.ContainsKey($k)) { $envVars += "$k=$($dotenv[$k])" }
}
if (-not ($dotenv.ContainsKey("GROQ_API_KEY") -or $dotenv.ContainsKey("GOOGLE_API_KEY"))) {
    Write-Host "No GROQ_API_KEY or GOOGLE_API_KEY in ${EnvFile}: the app will only offer rule checks." -ForegroundColor Yellow
}
Write-Host "Secrets: $(($secrets | ForEach-Object { $_.Split('=')[0] }) -join ', ')"
if (Test-Az containerapp show -n $AppName -g $ResourceGroup) {
    Write-Host "App exists: updating secrets, settings and image."
    if ($secrets.Count) { Invoke-Az containerapp secret set -n $AppName -g $ResourceGroup --secrets @secrets -o none }
    $updateArgs = @("containerapp", "update", "-n", $AppName, "-g", $ResourceGroup, "--image", $Image, "-o", "none")
    if ($envVars.Count) { $updateArgs += @("--set-env-vars") + $envVars }
    Invoke-Az @updateArgs
} else {
    $createArgs = @("containerapp", "create", "-n", $AppName, "-g", $ResourceGroup, "--environment", $EnvName,
        "--image", $Image, "--target-port", "8000", "--ingress", "external",
        "--min-replicas", "0", "--max-replicas", "1", "--cpu", "0.5", "--memory", "1.0Gi", "-o", "none")
    if ($secrets.Count) { $createArgs += @("--secrets") + $secrets }
    if ($envVars.Count) { $createArgs += @("--env-vars") + $envVars }
    Invoke-Az @createArgs
}
$fqdn = Invoke-Az containerapp show -n $AppName -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "App URL: https://$fqdn" -ForegroundColor Green

# --- Step 4 ------------------------------------------------------------------
Step 4 "GitHub Actions login (OIDC)" "Creates app registration 'reqagent-github' that only GitHub Actions on $Repo main can use, with Contributor on '$ResourceGroup' only. No password or client secret is created."
$appId = Invoke-Az ad app list --display-name "reqagent-github" --query "[0].appId" -o tsv
if (-not $appId) {
    try { $appId = Invoke-Az ad app create --display-name "reqagent-github" --query appId -o tsv }
    catch {
        Write-Host "Could not create an app registration. University tenants often block this." -ForegroundColor Yellow
        Write-Host "Fallback: deploy by hand after each merge with:"
        Write-Host "  az containerapp update -n $AppName -g $ResourceGroup --image ghcr.io/$($Repo.ToLower()):<commit-sha>"
        Write-Host "The app itself is running at https://$fqdn"
        exit 0
    }
}
if (-not (Test-Az ad sp show --id $appId)) { Invoke-Az ad sp create --id $appId -o none }
$fedName = "github-main"
$fedExists = Invoke-Az ad app federated-credential list --id $appId --query "[?name=='$fedName'] | length(@)" -o tsv
if ($fedExists -eq "0") {
    $fedFile = New-TemporaryFile
    @{ name = $fedName; issuer = "https://token.actions.githubusercontent.com"; subject = "repo:${Repo}:ref:refs/heads/main"; audiences = @("api://AzureADTokenExchange") } |
        ConvertTo-Json | Set-Content -Path $fedFile -Encoding ascii
    Invoke-Az ad app federated-credential create --id $appId --parameters "@$fedFile" -o none
    Remove-Item $fedFile
}
$scope = "/subscriptions/$SubId/resourceGroups/$ResourceGroup"
$hasRole = Invoke-Az role assignment list --assignee $appId --scope $scope --role Contributor --query "length(@)" -o tsv
if ($hasRole -eq "0") {
    # a brand-new service principal can take a few seconds to become visible to role assignments
    Start-Sleep -Seconds 20
    Invoke-Az role assignment create --assignee $appId --role Contributor --scope $scope -o none
}

# --- Step 5 ------------------------------------------------------------------
Step 5 "GitHub secrets and variables" "Stores the three IDs (not passwords) as repo secrets and the app name and group as repo variables, which switches on the 'deploy' job in CI."
$values = [ordered]@{ AZURE_CLIENT_ID = $appId; AZURE_TENANT_ID = $TenantId; AZURE_SUBSCRIPTION_ID = $SubId }
$ghReady = $false
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $ErrorActionPreference = "Continue"; & gh auth status *> $null; $ghReady = ($LASTEXITCODE -eq 0); $ErrorActionPreference = "Stop"
}
if ($ghReady) {
    foreach ($k in $values.Keys) { & gh secret set $k --body $values[$k] --repo $Repo; if ($LASTEXITCODE) { throw "gh secret set $k failed" } }
    & gh variable set AZURE_RESOURCE_GROUP --body $ResourceGroup --repo $Repo
    & gh variable set AZURE_APP_NAME --body $AppName --repo $Repo
    Write-Host "Done: secrets and variables set on $Repo." -ForegroundColor Green
} else {
    Write-Host "GitHub CLI not available or not logged in. Add these by hand:" -ForegroundColor Yellow
    Write-Host "https://github.com/$Repo/settings/secrets/actions"
    Write-Host "  Secrets tab:"
    foreach ($k in $values.Keys) { Write-Host "    $k = $($values[$k])" }
    Write-Host "  Variables tab:"
    Write-Host "    AZURE_RESOURCE_GROUP = $ResourceGroup"
    Write-Host "    AZURE_APP_NAME = $AppName"
}

Write-Host ""
Write-Host "All set. App: https://$fqdn" -ForegroundColor Green
Write-Host "Every push to main now builds, tests on kind, publishes the image and rolls it out here."
Write-Host "Remove everything later with: az group delete -n $ResourceGroup  (and az ad app delete --id $appId)"
