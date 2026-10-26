## Rule checks

| Smell | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| VAGUE | 1.0 | 0.824 | 14 | 0 | 3 |
| ESCAPE | 1.0 | 1.0 | 4 | 0 | 0 |
| OPEN | 1.0 | 1.0 | 4 | 0 | 0 |
| COMBINATOR | 1.0 | 0.8 | 4 | 0 | 1 |
| PASSIVE | 1.0 | 0.727 | 8 | 0 | 3 |
| NEGATIVE | 1.0 | 1.0 | 5 | 0 | 0 |
| PRONOUN | 1.0 | 1.0 | 5 | 0 | 0 |
| UNBOUNDED | 0.5 | 0.75 | 3 | 3 | 1 |
| NO_SHALL | 1.0 | 1.0 | 5 | 0 | 0 |
| ALL | 0.945 | 0.867 | 52 | 3 | 8 |

## Duplicate and conflict pairs

- Model: Groq openai/gpt-oss-120b
- Candidate recall (gold pairs that reached the LLM): 0.941
- Precision: 0.889 · Recall: 0.941
- TP 16 · FP 2 · FN 1
- Previous prompt: Precision 0.938 · Recall 0.882 · TP 15 · FP 1 · FN 2
- Failed LLM calls (skipped): 0
