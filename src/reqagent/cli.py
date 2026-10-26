import argparse
import json
import sys
from pathlib import Path

from . import report
from .analyze import analyze
from .llm import LocalEmbeddings, chat_model
from .parse import parse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reqagent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="check a requirements file (.csv with id,text or .txt)")
    an.add_argument("file", type=Path)
    an.add_argument("--out", type=Path, default=Path("reqagent-report"))
    an.add_argument("--rules-only", action="store_true", help="skip embeddings and the LLM")
    ev = sub.add_parser("eval", help="score against the labelled set in eval/")
    ev.add_argument("--labelled", default="eval/labelled.csv")
    ev.add_argument("--pairs", default="eval/pairs.csv")
    ev.add_argument("--rules-only", action="store_true", help="skip the LLM pair evaluation")
    ev.add_argument("--out", type=Path, default=Path("eval/results.md"))
    ev.add_argument("--langsmith", action="store_true", help="also log a LangSmith experiment")
    sv = sub.add_parser("serve", help="run the web page and HTTP API")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    if args.cmd == "eval":
        return _eval(args)
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("reqagent.api:app", host=args.host, port=args.port)
        return 0

    reqs = parse(args.file.read_text(encoding="utf-8"), args.file.name)
    if args.rules_only:
        rep, model = analyze(reqs)
    else:
        try:
            llm = chat_model()
        except (RuntimeError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        rep, model = analyze(reqs, llm=llm, embeddings=LocalEmbeddings())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (args.out / "report.md").write_text(report.to_markdown(rep), encoding="utf-8")
    (args.out / "model.sysml").write_text(model, encoding="utf-8")
    s = rep["summary"]
    print(f"{s['with_findings']}/{s['requirements']} requirements with findings: {s['by_code']}")
    print(f"duplicates: {s['duplicates']}, conflicts: {s['conflicts']}")
    if s["llm_errors"]:
        print(f"warning: {s['llm_errors']} LLM call(s) failed, see 'errors' in report.json")
    print(f"Report written to {args.out}/")
    return 0


def _eval(args) -> int:
    from . import evaluate

    examples = evaluate.load_labelled(args.labelled)
    rules = evaluate.score_rules(examples)
    pairs = None
    if not args.rules_only:
        from .graph import run

        try:
            llm = chat_model()
        except (RuntimeError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        # the eval only scores pairs, so skip the rewrite calls
        out = run([r for r, _ in examples], llm=llm, embeddings=LocalEmbeddings(), rewrite=False)
        gold = evaluate.load_pairs(args.pairs)
        pairs = evaluate.score_pairs(gold, out["pairs"], out["candidates"])
        pairs["llm_errors"] = len(out["errors"])
        for e in out["errors"]:
            print(f"warning: {e}", file=sys.stderr)
    if args.langsmith:
        evaluate.to_langsmith(examples)
    md = evaluate.to_markdown(rules, pairs)
    args.out.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
