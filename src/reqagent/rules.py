"""Deterministic requirement-smell checks.

Categories follow the INCOSE Guide to Writing Requirements; the word lists are ReqAgent's own.
"""

import re

from .models import Finding, Requirement

MODAL = r"(?:shall|must|will)"
NUMBER = r"\d"


def _words(*terms: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])(?:" + "|".join(terms) + r")(?![\w-])", re.IGNORECASE)


VAGUE = _words(
    "user-friendly",
    "easy",
    "easily",
    "simple",
    "fast",
    "quick",
    "quickly",
    "slow",
    "adequate",
    "appropriate",
    "sufficient",
    "efficient",
    "efficiently",
    "flexible",
    "robust",
    "reliable",
    "intuitive",
    "normal",
    "typical",
    "good",
    "best",
    "state-of-the-art",
    "significant",
    "several",
    "some",
    "many",
    "few",
    "approximately",
    "as needed",
    "timely",
    "seamless",
)
ESCAPE = _words(
    "if possible",
    "where possible",
    "as far as possible",
    "to the extent possible",
    "if practicable",
    "as far as practicable",
    "where feasible",
    "if feasible",
    "if necessary",
    "where necessary",
    "as appropriate",
)
OPEN = _words(r"etc\.?", "and so on", "including but not limited to", "and the like")
AND_OR = _words("and/or", "as well as")
PASSIVE = re.compile(rf"\b{MODAL}\s+(?:not\s+)?be\s+(?!able\b)(\w+(?:ed|en))\b", re.IGNORECASE)
NEGATIVE = re.compile(rf"\b{MODAL}\s+(?:not|never)\b", re.IGNORECASE)
PRONOUN = _words("it", "its", "they", "them", "their")
BOUND = _words("at least", "at most", "no more than", "no less than", "up to", "maximum", "minimum")
UNTESTABLE = _words(
    "minimi[sz]e", "maximi[sz]e", "optimi[sz]e", "optimal", "always", "as much as", "as little as"
)
SHALL = re.compile(rf"\b{MODAL}\b", re.IGNORECASE)

MESSAGES = {
    "VAGUE": "Vague or subjective term; replace it with a measurable criterion.",
    "ESCAPE": "Escape clause; it makes the requirement impossible to verify.",
    "OPEN": "Open-ended list; name every item.",
    "COMBINATOR": "Several requirements in one; split them.",
    "PASSIVE": "Passive voice without an actor; say which system or person does it.",
    "NEGATIVE": "Negative requirement; state what the system shall do instead.",
    "PRONOUN": "Pronoun; repeat the noun so the requirement stands on its own.",
    "UNBOUNDED": "Unbounded or untestable quantity; give a number with a unit.",
    "NO_SHALL": "No binding modal verb; use 'shall'.",
}


def check(req: Requirement) -> list[Finding]:
    text = req.text
    hits: list[tuple[str, int, int]] = []

    def add(code, pattern, skip_proper_names=False):
        for m in pattern.finditer(text):
            if skip_proper_names and m.group(0)[0].isupper() and m.start() > 0:
                continue  # "Fast Fourier Transform" is a name, not a vague term
            hits.append((code, m.start(), m.end()))

    add("VAGUE", VAGUE, skip_proper_names=True)
    add("ESCAPE", ESCAPE)
    add("OPEN", OPEN)
    add("COMBINATOR", AND_OR)
    shalls = list(SHALL.finditer(text))
    if len(shalls) > 1:
        hits.append(("COMBINATOR", shalls[1].start(), shalls[1].end()))
    for m in PASSIVE.finditer(text):
        if not re.search(r"\bby\b", text[m.end() :], re.IGNORECASE):
            hits.append(("PASSIVE", m.start(), m.end()))
    add("NEGATIVE", NEGATIVE)
    add("PRONOUN", PRONOUN)
    for m in BOUND.finditer(text):
        if not re.match(rf"\s*{NUMBER}", text[m.end() :]):
            hits.append(("UNBOUNDED", m.start(), m.end()))
    add("UNBOUNDED", UNTESTABLE)
    if not shalls:
        hits.append(("NO_SHALL", 0, len(text)))

    return [Finding(code, s, e, MESSAGES[code]) for code, s, e in sorted(hits, key=lambda h: h[1])]
