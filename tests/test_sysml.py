from reqagent.models import Finding, Requirement
from reqagent.sysml import to_sysml

REQS = [
    Requirement("PUMP-1", "The pump shall stop within 200 ms."),
    Requirement("PUMP-13", "The pump shall stop within 500 ms."),
    Requirement("7", "The display shall be user-friendly. See */ comment."),
]


def test_requirements_become_requirement_usages_with_doc():
    out = to_sysml(REQS)
    assert out.startswith("package ReqAgentModel {")
    assert "requirement <'PUMP-1'> PUMP_1 {" in out
    assert "doc /* The pump shall stop within 200 ms. */" in out
    assert out.count("{") == out.count("}")


def test_names_are_valid_identifiers():
    out = to_sysml(REQS)
    assert "requirement <'7'> R_7 {" in out  # identifiers can't start with a digit


def test_colliding_names_get_a_suffix():
    out = to_sysml([Requirement("A-1", "x shall y."), Requirement("A_1", "x shall z.")])
    assert "<'A-1'> A_1 {" in out and "<'A_1'> A_1_2 {" in out


def test_comment_terminator_in_text_is_escaped():
    out = to_sysml(REQS)
    assert "See * / comment." in out
    assert out.count("/*") == out.count("*/")


def test_pairs_become_named_dependencies_with_reason():
    pairs = [{"a": "PUMP-1", "b": "PUMP-13", "label": "conflict", "reason": "200 ms vs 500 ms"}]
    out = to_sysml(REQS, pairs=pairs)
    assert "dependency PUMP_1_conflicts_with_PUMP_13 from PUMP_1 to PUMP_13 {" in out
    assert "doc /* conflict: 200 ms vs 500 ms */" in out


def test_findings_and_rewrite_become_comments():
    start = REQS[2].text.index("user-friendly")
    findings = {"7": [Finding("VAGUE", start, start + len("user-friendly"), "Vague term.")]}
    rewrites = {"7": {"text": "The display shall [TBD].", "reason": "vague"}}
    out = to_sysml(REQS, findings=findings, rewrites=rewrites)
    assert "comment /* VAGUE 'user-friendly': Vague term. */" in out
    assert "comment /* Suggested rewrite: The display shall [TBD]. */" in out
