"""Score ReqAgent against the hand-labelled set in eval/."""

import csv

from .models import Requirement
from .rules import MESSAGES, check


def load_labelled(path: str) -> list[tuple[Requirement, set[str]]]:
    with open(path, encoding="utf-8", newline="") as f:
        return [
            (Requirement(r["id"], r["text"]), set(r["smells"].split())) for r in csv.DictReader(f)
        ]


def load_pairs(path: str) -> set[tuple[str, str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return {(*sorted((r["a"], r["b"])), r["label"]) for r in csv.DictReader(f)}


def _prf(tp: int, fp: int, fn: int) -> dict:
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
    }


def score_rules(examples: list[tuple[Requirement, set[str]]]) -> dict[str, dict]:
    """Per smell code, counted per requirement; a code found twice in one counts once."""
    counts = {c: [0, 0, 0] for c in MESSAGES}
    for req, gold in examples:
        found = {f.code for f in check(req)}
        for c in MESSAGES:
            counts[c][0] += c in found and c in gold
            counts[c][1] += c in found and c not in gold
            counts[c][2] += c in gold and c not in found
    scores = {c: _prf(*v) for c, v in counts.items()}
    scores["ALL"] = _prf(*(sum(v[i] for v in counts.values()) for i in range(3)))
    return scores


def score_pairs(gold: set, predicted: list[dict], candidates: list[tuple]) -> dict:
    pred = {(*sorted((p["a"], p["b"])), p["label"]) for p in predicted}
    tp = len(pred & gold)
    reached = {tuple(sorted((a, b))) for a, b, _ in candidates}
    out = _prf(tp, len(pred - gold), len(gold - pred))
    out["candidate_recall"] = round(sum((a, b) in reached for a, b, _ in gold) / len(gold), 3)
    return out


def to_markdown(rules: dict, pairs: dict | None) -> str:
    lines = [
        "## Rule checks",
        "",
        "| Smell | Precision | Recall | TP | FP | FN |",
        "|---|---|---|---|---|---|",
    ]
    for code, s in rules.items():
        lines.append(
            f"| {code} | {s['precision']} | {s['recall']} | {s['tp']} | {s['fp']} | {s['fn']} |"
        )
    if pairs:
        lines += ["", "## Duplicate and conflict pairs", ""]
        lines.append(
            f"- Candidate recall (gold pairs that reached the LLM): {pairs['candidate_recall']}"
        )
        lines.append(f"- Precision: {pairs['precision']} · Recall: {pairs['recall']}")
        lines.append(f"- TP {pairs['tp']} · FP {pairs['fp']} · FN {pairs['fn']}")
    return "\n".join(lines) + "\n"


# LangSmith experiment: the labelled set becomes a dataset, each rules run an experiment.
DATASET = "reqagent-smells"


def ls_target(inputs: dict) -> dict:
    return {"smells": sorted({f.code for f in check(Requirement(inputs["id"], inputs["text"]))})}


def ls_exact_match(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "exact_match", "score": outputs["smells"] == reference_outputs["smells"]}


def ls_micro_prf(outputs: list[dict], reference_outputs: list[dict]) -> list[dict]:
    tp = fp = fn = 0
    for o, r in zip(outputs, reference_outputs, strict=True):
        got, want = set(o["smells"]), set(r["smells"])
        tp, fp, fn = tp + len(got & want), fp + len(got - want), fn + len(want - got)
    s = _prf(tp, fp, fn)
    return [{"key": "precision", "score": s["precision"]}, {"key": "recall", "score": s["recall"]}]


def to_langsmith(examples: list[tuple[Requirement, set[str]]]):
    from langsmith import Client, evaluate

    client = Client()
    if not client.has_dataset(dataset_name=DATASET):
        client.create_dataset(
            DATASET, description="Hand-labelled requirement smells (eval/labelled.csv)"
        )
        client.create_examples(
            dataset_name=DATASET,
            examples=[
                {"inputs": {"id": r.id, "text": r.text}, "outputs": {"smells": sorted(g)}}
                for r, g in examples
            ],
        )
    return evaluate(
        ls_target,
        data=DATASET,
        evaluators=[ls_exact_match],
        summary_evaluators=[ls_micro_prf],
        experiment_prefix="rules",
        client=client,
    )
