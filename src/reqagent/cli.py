import argparse
import json
import sys
from pathlib import Path

from . import report
from .parse import parse
from .rules import check


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reqagent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="check a requirements file (.csv with id,text or .txt)")
    an.add_argument("file", type=Path)
    an.add_argument("--out", type=Path, default=Path("reqagent-report"))
    args = ap.parse_args(argv)

    reqs = parse(args.file.read_text(encoding="utf-8"), args.file.name)
    rep = report.build([(r, check(r)) for r in reqs])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (args.out / "report.md").write_text(report.to_markdown(rep), encoding="utf-8")
    s = rep["summary"]
    print(f"{s['with_findings']}/{s['requirements']} requirements with findings: {s['by_code']}")
    print(f"Report written to {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
