import pytest

from reqagent.models import Requirement
from reqagent.rules import check


def codes(text):
    return {f.code for f in check(Requirement("R1", text))}


CLEAN = "The pump controller shall stop the pump within 200 ms of a stop command."


def test_clean_requirement_has_no_findings():
    assert codes(CLEAN) == set()


@pytest.mark.parametrize(
    "code, text",
    [
        ("VAGUE", "The interface shall be user-friendly for operators."),
        ("VAGUE", "The system shall respond quickly to the operator."),
        ("ESCAPE", "The logger shall store all events if possible."),
        ("OPEN", "The display shall show speed, altitude, etc."),
        ("COMBINATOR", "The operator shall start and/or stop the pump."),
        ("COMBINATOR", "The system shall log errors. The system shall send alerts."),
        ("PASSIVE", "The warning shall be displayed within 2 s."),
        ("NEGATIVE", "The valve shall not open during startup."),
        ("PRONOUN", "The sensor shall report its status every 10 s."),
        ("UNBOUNDED", "The battery shall last at least a full shift."),
        ("UNBOUNDED", "The system shall minimize energy use."),
        ("NO_SHALL", "The pump stops within 200 ms."),
        ("NO_SHALL", "The pump should stop within 200 ms."),
    ],
)
def test_smell_detected(code, text):
    assert code in codes(text)


@pytest.mark.parametrize(
    "code, text",
    [
        ("PASSIVE", "The report shall be approved by the safety manager."),  # actor named
        ("PASSIVE", "The operator shall be able to stop the pump."),
        ("UNBOUNDED", "The battery shall last at least 8 hours."),  # bounded by a number
        ("VAGUE", "The system shall use the Fast Fourier Transform."),  # proper name, capitalised
        ("PRONOUN", "The system shall reject commands that lack a checksum."),
    ],
)
def test_no_false_positive(code, text):
    assert code not in codes(text)


def test_finding_points_at_the_matched_text():
    text = "The interface shall be user-friendly."
    (f,) = [f for f in check(Requirement("R1", text)) if f.code == "VAGUE"]
    assert text[f.start : f.end].lower() == "user-friendly"
    assert f.message
