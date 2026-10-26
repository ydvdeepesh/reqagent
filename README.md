# ReqAgent

ReqAgent reviews natural-language requirements the way a systems engineer would on a first pass. It flags quality problems (vague terms, escape clauses, passive voice and more), and will find duplicates and conflicts with an LLM and export the set as SysML v2.

Status: stage 1 of 7. The rule checks and the command-line tool work. See [docs/design.md](docs/design.md) for the full plan.

## Try it

```bash
uv sync
uv run reqagent analyze data/sample/requirements.csv --out reqagent-report
```

Input is a CSV with `id,text` columns, or a `.txt` file with one requirement per line. The tool writes `report.json` and `report.md`.

## Rule checks

| Code | Smell | Example |
|---|---|---|
| VAGUE | Vague or subjective term | "shall respond quickly" |
| ESCAPE | Escape clause | "if possible" |
| OPEN | Open-ended list | "faults, warnings, etc." |
| COMBINATOR | Several requirements in one | "and/or", two "shall"s |
| PASSIVE | Passive voice without an actor | "shall be displayed" |
| NEGATIVE | Negative requirement | "shall not" |
| PRONOUN | Pronoun instead of the noun | "its reading" |
| UNBOUNDED | Unbounded or untestable quantity | "at least" without a number, "minimize" |
| NO_SHALL | No binding modal verb | "should", or no modal at all |

The categories follow the INCOSE *Guide to Writing Requirements*. The word lists are ReqAgent's own.

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
