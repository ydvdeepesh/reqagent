import json

from reqagent.cli import main


def test_analyze_writes_json_and_markdown(tmp_path):
    src = tmp_path / "reqs.csv"
    src.write_text(
        "id,text\nR1,The interface shall be user-friendly.\nR2,The pump shall stop within 200 ms.\n"
    )
    out = tmp_path / "out"
    assert main(["analyze", str(src), "--out", str(out)]) == 0

    report = json.loads((out / "report.json").read_text())
    assert [r["id"] for r in report["requirements"]] == ["R1", "R2"]
    assert report["summary"]["by_code"] == {"VAGUE": 1}
    assert report["requirements"][1]["findings"] == []
    md = (out / "report.md").read_text()
    assert "R1" in md and "VAGUE" in md
