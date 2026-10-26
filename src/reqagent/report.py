from collections import Counter
from dataclasses import asdict

from .models import Finding, Requirement


def build(
    results: list[tuple[Requirement, list[Finding]]],
    pairs: list[dict] | None = None,
    rewrites: dict | None = None,
    errors: list[str] | None = None,
) -> dict:
    counts = Counter(f.code for _, findings in results for f in findings)
    rewrites = rewrites or {}
    return {
        "summary": {
            "requirements": len(results),
            "with_findings": sum(1 for _, f in results if f),
            "by_code": dict(sorted(counts.items())),
            "duplicates": sum(1 for p in pairs or [] if p["label"] == "duplicate"),
            "conflicts": sum(1 for p in pairs or [] if p["label"] == "conflict"),
            "llm_errors": len(errors or []),
        },
        "errors": errors or [],
        "pairs": pairs or [],
        "requirements": [
            {
                "id": r.id,
                "text": r.text,
                "findings": [asdict(f) | {"match": r.text[f.start : f.end]} for f in findings],
                "rewrite": rewrites.get(r.id),
            }
            for r, findings in results
        ],
    }


def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# ReqAgent report",
        "",
        f"{s['with_findings']} of {s['requirements']} requirements have findings.",
        "",
        "| ID | Requirement | Findings |",
        "|---|---|---|",
    ]
    for r in report["requirements"]:
        found = "<br>".join(
            f"**{f['code']}** `{f['match']}`: {f['message']}" for f in r["findings"]
        )
        text = r["text"].replace("|", "\\|")
        lines.append(f"| {r['id']} | {text} | {found or 'none'} |")
    if report["pairs"]:
        lines += ["", "## Duplicates and conflicts", "", "| Pair | Label | Similarity | Reason |"]
        lines.append("|---|---|---|---|")
        for p in report["pairs"]:
            lines.append(
                f"| {p['a']} / {p['b']} | {p['label']} | {p['similarity']} | {p['reason']} |"
            )
    rewritten = [r for r in report["requirements"] if r["rewrite"]]
    if rewritten:
        lines += ["", "## Suggested rewrites", ""]
        for r in rewritten:
            lines.append(f"- **{r['id']}**: {r['rewrite']['text']}  \n  _{r['rewrite']['reason']}_")
    return "\n".join(lines) + "\n"
