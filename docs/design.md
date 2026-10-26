# ReqAgent design

ReqAgent reviews natural-language requirements the way a systems engineer would on a first pass. It flags quality problems, finds duplicates and possible conflicts, and exports the set as SysML v2 text with trace links.

## Goals

- Rule checks for common requirement smells, with an explanation and a suggested rewrite for each finding.
- Duplicate and near-duplicate detection with embeddings.
- Conflict and gap detection by an LLM, run only on candidate pairs (not all n² pairs).
- SysML v2 textual export: one `requirement` per input, with `dependency` links for duplicates and conflicts.
- Evaluation against a hand-labelled set, tracked in LangSmith, with precision and recall reported in the README.
- Runs locally, in Docker and on Kubernetes. Deployed on Azure.

## Non-goals

User accounts, a database of projects, editing requirements in place, ReqIF round-tripping, and a full SysML v2 parser.

## Inputs

- CSV with `id,text` columns (other columns are ignored)
- Plain text, one requirement per line (ids generated as `R1`, `R2`, …)
- PURE XML (the dataset's own schema), via the import script

## Pipeline (a LangGraph graph)

```
parse → rule_checks → embed → candidate_pairs → llm_review → sysml_export → report
```

| Node | What it does | LLM? |
|---|---|---|
| parse | Normalise input into `Requirement(id, text)` | no |
| rule_checks | Deterministic smell detectors (below) | no |
| embed | Embed each requirement | embedding model |
| candidate_pairs | Pairs above a cosine similarity threshold, top-k per requirement | no |
| llm_review | For each candidate pair: duplicate / conflict / unrelated, with a reason. For each requirement with rule findings: a suggested rewrite | yes |
| sysml_export | Deterministic template into SysML v2 text | no |
| report | JSON and Markdown report | no |

The rule checks are deterministic, so they are cheap, testable and explainable. The LLM handles only what rules can't do: comparing meaning across two requirements, and proposing a rewrite.

## Rule checks (requirement smells)

These are grouped by the categories the INCOSE *Guide to Writing Requirements* uses. The word lists are ReqAgent's own; no text from the guide is copied.

| Code | Smell | Example trigger |
|---|---|---|
| VAGUE | Vague or subjective terms | user-friendly, fast, adequate, appropriate |
| ESCAPE | Escape clauses | if possible, as far as practicable, where feasible |
| OPEN | Open-ended lists | etc., and so on, including but not limited to |
| COMBINATOR | Several requirements in one | and/or, as well as, multiple "shall" |
| PASSIVE | Passive voice without an actor | shall be displayed |
| NEGATIVE | Negative requirements | shall not |
| PRONOUN | Pronouns with an unclear referent | it, this, they |
| UNBOUNDED | Unbounded or untestable quantities | maximum, minimum, at least (without a number), always, never |
| NO_SHALL | No modal verb | sentence without shall/must/will |

## Models

LangChain chat models behind one small factory, chosen by environment variable:
- Default: Groq `openai/gpt-oss-120b` (free tier)
- Fallback: Gemini
- Tests: a fake chat model with recorded answers, so CI never calls a paid or rate-limited API

Embeddings: a small local ONNX model (via fastembed) if it installs cleanly in Docker; otherwise Gemini embeddings. The vector store is ChromaDB, in memory per run.

Tracing: LangSmith, through the standard `LANGSMITH_*` environment variables. It is off when no key is set.

## Interfaces

- CLI: `reqagent analyze input.csv --out report/` writes `report.json`, `report.md` and `model.sysml`
- API: FastAPI `POST /analyze` (JSON or file upload) returns the report. `GET /health`.
- UI: a single page served by FastAPI. Paste or upload requirements and see the findings.

## Evaluation

- `eval/labelled.csv`: 101 hand-written requirements from 11 domains, each labelled with its smells, plus `eval/pairs.csv` with known duplicate and conflict pairs. A PURE sample can be added later.
- `eval/run.py`: per-smell precision and recall for the rule checks, and accuracy for the pair review. Results are uploaded to LangSmith as an experiment when a key is set.
- The README shows the latest numbers.

## Delivery

- **Tooling:** uv, ruff and pytest.
- **GitHub Actions:** lint and tests on every push. Docker image build and push to GHCR on main. A `kind` cluster smoke test that applies `deploy/k8s/` and calls `/health`.
- **Deploy:** Azure Container Apps first (cheap, close to Kubernetes). AKS optional using the same manifests.

## Stages (each one is reviewed before the next starts)

1. Scaffolding, data model, parsers, rule checks, CLI (rules only), tests, CI
2. Embeddings, candidate pairs, LLM review, LangGraph graph, LangSmith tracing
3. SysML v2 export and reports
4. Labelled eval set and evaluation script
5. FastAPI and web page
6. Docker, Kubernetes manifests, kind test in CI
7. Azure deployment

## Data and licences

- PURE (Ferrari, Spagnolo, Gnesi, RE'17; Zenodo DOI 10.5281/zenodo.1414117), listed as CC BY 4.0. Only a small attributed sample is committed. `scripts/fetch_pure.py` downloads the rest.
- No code, prompts or requirement text from any employer or NDA project.
