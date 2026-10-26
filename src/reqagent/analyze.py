from . import report
from .models import Requirement
from .rules import check
from .sysml import to_sysml


def analyze(reqs: list[Requirement], llm=None, embeddings=None) -> tuple[dict, str]:
    """Report and SysML v2 text. Without an LLM only the rule checks run."""
    if llm is None:
        findings = {r.id: check(r) for r in reqs}
        rep = report.build([(r, findings[r.id]) for r in reqs])
        return rep, to_sysml(reqs, findings=findings)
    from .graph import run

    out = run(reqs, llm=llm, embeddings=embeddings)
    results = [(r, out["findings"][r.id]) for r in reqs]
    rep = report.build(results, out["pairs"], out["rewrites"], out["errors"])
    return rep, to_sysml(reqs, out["pairs"], out["findings"], out["rewrites"])
