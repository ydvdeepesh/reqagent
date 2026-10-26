from reqagent.evaluate import score_pairs, score_rules
from reqagent.models import Requirement


def test_score_rules_counts_per_code_at_requirement_level():
    examples = [
        (Requirement("A", "The UI shall be user-friendly."), {"VAGUE"}),  # tp VAGUE
        (Requirement("B", "The UI shall be comfortable."), {"VAGUE"}),  # fn VAGUE
        (Requirement("C", "The pump stops."), set()),  # fp NO_SHALL
    ]
    s = score_rules(examples)
    assert s["VAGUE"] == {"tp": 1, "fp": 0, "fn": 1, "precision": 1.0, "recall": 0.5}
    assert s["NO_SHALL"]["fp"] == 1 and s["NO_SHALL"]["precision"] == 0.0
    assert s["ALL"]["tp"] == 1 and s["ALL"]["fp"] == 1 and s["ALL"]["fn"] == 1


def test_score_pairs_ignores_order_and_needs_matching_label():
    gold = {("A", "B", "conflict"), ("C", "D", "duplicate")}
    predicted = [
        {"a": "B", "b": "A", "label": "conflict"},  # tp, reversed order
        {"a": "C", "b": "D", "label": "conflict"},  # wrong label: fp, and gold stays missed
        {"a": "E", "b": "F", "label": "duplicate"},  # fp
    ]
    candidates = [("A", "B", 0.9), ("C", "D", 0.8)]
    s = score_pairs(gold, predicted, candidates)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 2, 1)
    assert s["precision"] == round(1 / 3, 3) and s["recall"] == 0.5
    assert s["candidate_recall"] == 1.0  # both gold pairs reached the LLM


def test_labelled_set_loads_and_uses_known_codes():
    from reqagent.evaluate import load_labelled, load_pairs
    from reqagent.rules import MESSAGES

    examples = load_labelled("eval/labelled.csv")
    assert len(examples) >= 100
    assert all(codes <= set(MESSAGES) for _, codes in examples)
    ids = {r.id for r, _ in examples}
    assert all(a in ids and b in ids for a, b, _ in load_pairs("eval/pairs.csv"))


def test_langsmith_evaluators_agree_with_local_scoring():
    from reqagent.evaluate import ls_exact_match, ls_micro_prf, ls_target

    out = ls_target({"id": "A", "text": "The UI shall be user-friendly."})
    assert out == {"smells": ["VAGUE"]}
    assert ls_exact_match(out, {"smells": ["VAGUE"]})["score"] is True
    summary = ls_micro_prf([out, {"smells": []}], [{"smells": ["VAGUE"]}, {"smells": ["PASSIVE"]}])
    assert summary == [{"key": "precision", "score": 1.0}, {"key": "recall", "score": 0.5}]
