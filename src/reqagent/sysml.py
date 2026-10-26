"""Export requirements to SysML v2 textual notation.

Each requirement becomes a `requirement` usage with its id as short name. Duplicates and
conflicts become named `dependency` relationships; SysML v2 has no built-in relationship
for either, so the label lives in the name and the doc comment.
"""

import re

from .models import Finding, Requirement

VERB = {"duplicate": "duplicates", "conflict": "conflicts_with"}


def _block(text: str) -> str:
    return text.replace("*/", "* /")  # a literal */ would end the comment early


def _names(reqs: list[Requirement]) -> dict[str, str]:
    names, used = {}, set()
    for r in reqs:
        base = re.sub(r"\W", "_", r.id)
        if not re.match(r"[A-Za-z_]", base):
            base = f"R_{base}"
        name, n = base, 2
        while name in used:
            name, n = f"{base}_{n}", n + 1
        used.add(name)
        names[r.id] = name
    return names


def to_sysml(
    reqs: list[Requirement],
    pairs: list[dict] | None = None,
    findings: dict[str, list[Finding]] | None = None,
    rewrites: dict | None = None,
) -> str:
    names = _names(reqs)
    findings, rewrites = findings or {}, rewrites or {}
    out = ["package ReqAgentModel {"]
    for r in reqs:
        out.append(f"    requirement <'{r.id}'> {names[r.id]} {{")
        out.append(f"        doc /* {_block(r.text)} */")
        for f in findings.get(r.id, []):
            match = _block(r.text[f.start : f.end])
            out.append(f"        comment /* {f.code} '{match}': {_block(f.message)} */")
        if r.id in rewrites:
            out.append(f"        comment /* Suggested rewrite: {_block(rewrites[r.id]['text'])} */")
        out.append("    }")
    for p in pairs or []:
        a, b = names[p["a"]], names[p["b"]]
        out.append(f"    dependency {a}_{VERB[p['label']]}_{b} from {a} to {b} {{")
        out.append(f"        doc /* {p['label']}: {_block(p['reason'])} */")
        out.append("    }")
    out.append("}")
    return "\n".join(out) + "\n"
