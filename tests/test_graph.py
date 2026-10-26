from fakes import BagOfWords, FakeLLM

from reqagent.graph import run
from reqagent.models import Requirement
from reqagent.review import PairVerdict, Rewrite

REQS = [
    Requirement("P1", "The pump controller shall stop the pump within 200 ms of a stop command."),
    Requirement("P2", "The pump controller shall stop the pump within 500 ms of a stop command."),
    Requirement("P3", "The display shall be user-friendly."),
    Requirement("P4", "The logger shall store each alarm with a timestamp."),
]


def answer(schema, prompt):
    if schema is PairVerdict:
        return PairVerdict(label="conflict", reason="200 ms and 500 ms limits for the same stop.")
    return Rewrite(text="The display shall [TBD: measurable usability criterion].", reason="vague")


def test_graph_finds_conflict_and_suggests_rewrite():
    llm = FakeLLM(answer)
    out = run(REQS, llm=llm, embeddings=BagOfWords([r.text for r in REQS]))

    assert [(p["a"], p["b"], p["label"]) for p in out["pairs"]] == [("P1", "P2", "conflict")]
    assert set(out["rewrites"]) == {"P3"}  # only requirements with rule findings get a rewrite
    assert out["findings"]["P3"][0].code == "VAGUE"
    # the rewrite prompt includes the rule findings, so the model knows what to fix
    assert any("VAGUE" in p and "user-friendly" in p for p in llm.prompts)


def test_unrelated_pairs_are_dropped():
    llm = FakeLLM(lambda schema, p: PairVerdict(label="unrelated", reason="different functions"))
    out = run(REQS[:2], llm=llm, embeddings=BagOfWords([r.text for r in REQS]))
    assert out["pairs"] == []


def test_dissimilar_requirements_never_reach_the_llm():
    llm = FakeLLM(answer)
    run([REQS[0], REQS[3]], llm=llm, embeddings=BagOfWords([r.text for r in REQS]))
    assert llm.prompts == []


def test_one_failed_llm_call_does_not_stop_the_run():
    def flaky(schema, prompt):
        if schema is Rewrite:
            raise ValueError("Tool choice is required, but model did not call a tool")
        return PairVerdict(label="conflict", reason="200 ms vs 500 ms")

    out = run(REQS, llm=FakeLLM(flaky), embeddings=BagOfWords([r.text for r in REQS]))
    assert [p["label"] for p in out["pairs"]] == ["conflict"]  # pair review still finished
    assert out["rewrites"] == {}
    assert len(out["errors"]) == 1 and "P3" in out["errors"][0]


def test_structured_output_uses_json_schema():
    llm = FakeLLM(answer)
    run(REQS, llm=llm, embeddings=BagOfWords([r.text for r in REQS]))
    assert llm.kwargs == {"method": "json_schema", "strict": True}


def test_rewrite_step_can_be_skipped():
    llm = FakeLLM(answer)
    out = run(REQS, llm=llm, embeddings=BagOfWords([r.text for r in REQS]), rewrite=False)
    assert out["rewrites"] == {}
    assert len(llm.prompts) == 1  # only the P1/P2 pair review
