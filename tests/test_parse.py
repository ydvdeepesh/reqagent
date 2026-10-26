from reqagent.parse import parse


def test_csv_with_id_and_text():
    reqs = parse(
        'id,text,owner\nSR-1,The pump shall stop.,bob\nSR-2,"The valve shall close, fast.",ann\n',
        "x.csv",
    )
    assert [(r.id, r.text) for r in reqs] == [
        ("SR-1", "The pump shall stop."),
        ("SR-2", "The valve shall close, fast."),
    ]


def test_csv_header_is_case_insensitive_and_skips_blank_rows():
    reqs = parse("ID,Text\nA,One shall.\n,\nB,Two shall.\n", "x.csv")
    assert [r.id for r in reqs] == ["A", "B"]


def test_plain_text_one_per_line_gets_generated_ids():
    reqs = parse("The pump shall stop.\n\n  The valve shall close.  \n", "x.txt")
    assert [(r.id, r.text) for r in reqs] == [
        ("R1", "The pump shall stop."),
        ("R2", "The valve shall close."),
    ]


def test_csv_without_text_column_raises():
    import pytest

    with pytest.raises(ValueError, match="text"):
        parse("id,description\nA,x\n", "x.csv")
