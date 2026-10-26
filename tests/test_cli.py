import json

from reqagent.cli import main


def test_analyze_writes_json_and_markdown(tmp_path):
    src = tmp_path / "reqs.csv"
    src.write_text(
        "id,text\nR1,The interface shall be user-friendly.\nR2,The pump shall stop within 200 ms.\n"
    )
    out = tmp_path / "out"
    assert main(["analyze", str(src), "--out", str(out), "--rules-only"]) == 0

    report = json.loads((out / "report.json").read_text())
    assert [r["id"] for r in report["requirements"]] == ["R1", "R2"]
    assert report["summary"]["by_code"] == {"VAGUE": 1}
    assert report["requirements"][1]["findings"] == []
    md = (out / "report.md").read_text()
    assert "R1" in md and "VAGUE" in md


def test_full_run_uses_llm_and_embeddings(tmp_path, monkeypatch):
    from fakes import BagOfWords, FakeLLM

    from reqagent import cli
    from reqagent.review import PairVerdict, Rewrite

    texts = ["The pump shall stop within 200 ms.", "The pump shall stop within 500 ms."]
    src = tmp_path / "reqs.txt"
    src.write_text("\n".join(texts) + "\nThe display shall be user-friendly.\n")

    def answer(schema, prompt):
        if schema is PairVerdict:
            return PairVerdict(label="conflict", reason="200 ms vs 500 ms")
        return Rewrite(text="The display shall [TBD].", reason="vague")

    monkeypatch.setattr(cli, "chat_model", lambda: FakeLLM(answer))
    monkeypatch.setattr(cli, "LocalEmbeddings", lambda: BagOfWords(texts))
    out = tmp_path / "out"
    assert main(["analyze", str(src), "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["summary"]["conflicts"] == 1
    assert report["requirements"][2]["rewrite"]["text"] == "The display shall [TBD]."
    assert "Duplicates and conflicts" in (out / "report.md").read_text()


def test_missing_api_key_gives_a_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("REQAGENT_LLM", "groq")
    src = tmp_path / "r.txt"
    src.write_text("The pump shall stop.\n")
    assert main(["analyze", str(src), "--out", str(tmp_path / "o")]) == 2
    assert "GROQ_API_KEY" in capsys.readouterr().err
