"""LLM steps: judge candidate pairs, and suggest rewrites for requirements with rule findings."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .models import Finding, Requirement


class PairVerdict(BaseModel):
    label: Literal["duplicate", "conflict", "unrelated"]
    reason: str = Field(description="One sentence that names the exact words or values involved.")


class Rewrite(BaseModel):
    text: str = Field(description="The rewritten requirement.")
    reason: str = Field(description="One sentence on what changed.")


PAIR_SYSTEM = """You review pairs of system requirements for a systems engineer.
Label the pair:
- duplicate: both state the same obligation with the same values, even if worded differently.
- conflict: both constrain the same behaviour or property but disagree. This includes
  different values for the same limit, even when meeting the stricter one would also meet
  the looser one (e.g. "stop within 200 ms" vs "stop within 500 ms"): the specification is
  inconsistent and someone has to decide which value is right. It also includes
  requirements that cannot both be satisfied.
- unrelated: they constrain different behaviours or properties.
Judge only what the text says. Do not assume context that is not written."""

REWRITE_SYSTEM = """You rewrite one system requirement so it passes a requirements review.
Fix every listed finding and keep the original meaning. Use "shall", active voice, one
obligation, and measurable values. If a value is needed but not given, write [TBD: <what is
needed>] instead of inventing a number. If the requirement must be split, return the parts
as numbered sentences in one text."""


def pair_messages(a: Requirement, b: Requirement):
    return [SystemMessage(PAIR_SYSTEM), HumanMessage(f"{a.id}: {a.text}\n{b.id}: {b.text}")]


def rewrite_messages(req: Requirement, findings: list[Finding]):
    listed = "\n".join(
        f"- {f.code} at '{req.text[f.start : f.end]}': {f.message}" for f in findings
    )
    return [
        SystemMessage(REWRITE_SYSTEM),
        HumanMessage(f"{req.id}: {req.text}\nFindings:\n{listed}"),
    ]
