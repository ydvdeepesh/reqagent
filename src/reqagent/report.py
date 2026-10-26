from collections import Counter
from dataclasses import asdict

from .models import Finding, Requirement


def build(results: list[tuple[Requirement, list[Finding]]]) -> dict:
    counts = Counter(f.code for _, findings in results for f in findings)
    return {
        "summary": {
            "requirements": len(results),
            "with_findings": sum(1 for _, f in results if f),
            "by_code": dict(sorted(counts.items())),
        },
        "requirements": [
            {
                "id": r.id,
                "text": r.text,
                "findings": [asdict(f) | {"match": r.text[f.start : f.end]} for f in findings],
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
    return "\n".join(lines) + "\n"
