import csv
import io

from .models import Requirement


def parse(content: str, filename: str) -> list[Requirement]:
    """CSV (needs a `text` column, optional `id`) or plain text with one requirement per line."""
    if filename.lower().endswith(".csv"):
        return _parse_csv(content)
    lines = [line.strip() for line in content.splitlines()]
    return [Requirement(f"R{i}", t) for i, t in enumerate(filter(None, lines), 1)]


def _parse_csv(content: str) -> list[Requirement]:
    reader = csv.DictReader(io.StringIO(content))
    fields = {(f or "").strip().lower(): f for f in reader.fieldnames or []}
    if "text" not in fields:
        raise ValueError(f"CSV needs a 'text' column, found: {list(fields)}")
    reqs = []
    for row in reader:
        text = (row.get(fields["text"]) or "").strip()
        if not text:
            continue
        rid = (row.get(fields["id"]) or "").strip() if "id" in fields else ""
        reqs.append(Requirement(rid or f"R{len(reqs) + 1}", text))
    return reqs
