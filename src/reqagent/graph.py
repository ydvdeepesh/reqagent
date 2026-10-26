"""The ReqAgent pipeline as a LangGraph graph.

rules ──> embed ──> candidates ──> review_pairs ──> END
  └────────────────> rewrite ─────────────────────> END   (optional; eval skips it)
"""

import operator
import uuid
from typing import Annotated, TypedDict

import chromadb
from chromadb.config import Settings
from langgraph.graph import END, START, StateGraph

from .models import Finding, Requirement
from .review import PairVerdict, Rewrite, pair_messages, rewrite_messages
from .rules import check

SIMILARITY = 0.75  # cosine; below this two requirements are not worth an LLM call
TOP_K = 3
CONCURRENCY = 4  # stays under Groq free-tier request limits


class State(TypedDict, total=False):
    requirements: list[Requirement]
    findings: dict[str, list[Finding]]
    vectors: list[list[float]]
    candidates: list[tuple[str, str, float]]
    pairs: list[dict]
    rewrites: Annotated[dict, operator.or_]
    errors: Annotated[list[str], operator.add]  # both LLM nodes append here


def _batch(llm, schema, prompts):
    """Run prompts in parallel; one failed call becomes an exception in its slot, not a crash."""
    # strict json_schema: tool-calling mode rejected plain-text answers, and non-strict
    # json_schema let gpt-oss echo the schema back instead of filling it in
    model = llm.with_structured_output(schema, method="json_schema", strict=True)
    return model.batch(prompts, config={"max_concurrency": CONCURRENCY}, return_exceptions=True)


def build(llm, embeddings, with_rewrite: bool = True):
    def rules(s: State):
        return {"findings": {r.id: check(r) for r in s["requirements"]}}

    def embed(s: State):
        return {"vectors": embeddings.embed_documents([r.text for r in s["requirements"]])}

    def candidates(s: State):
        reqs, vecs = s["requirements"], s["vectors"]
        if len(reqs) < 2:
            return {"candidates": []}
        client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        col = client.create_collection(f"run-{uuid.uuid4().hex}", metadata={"hnsw:space": "cosine"})
        try:
            ids = [str(i) for i in range(len(reqs))]
            col.add(ids=ids, embeddings=vecs)
            res = col.query(query_embeddings=vecs, n_results=min(TOP_K + 1, len(reqs)))
        finally:
            client.delete_collection(col.name)
        found = {}
        for i, (hits, dists) in enumerate(zip(res["ids"], res["distances"], strict=True)):
            for j, d in zip(map(int, hits), dists, strict=True):
                if i != j and 1 - d >= SIMILARITY:
                    a, b = sorted((i, j))
                    found[(a, b)] = round(1 - d, 3)
        return {
            "candidates": [(reqs[a].id, reqs[b].id, sim) for (a, b), sim in sorted(found.items())]
        }

    def review_pairs(s: State):
        by_id = {r.id: r for r in s["requirements"]}
        cands = s["candidates"]
        verdicts = _batch(
            llm, PairVerdict, [pair_messages(by_id[a], by_id[b]) for a, b, _ in cands]
        )
        pairs, errors = [], []
        for (a, b, sim), v in zip(cands, verdicts, strict=True):
            if isinstance(v, Exception):
                errors.append(f"pair {a}/{b}: {v}")
            elif v.label != "unrelated":
                pairs.append(
                    {"a": a, "b": b, "similarity": sim, "label": v.label, "reason": v.reason}
                )
        return {"pairs": pairs, "errors": errors}

    def rewrite_node(s: State):
        todo = [r for r in s["requirements"] if s["findings"][r.id]]
        out = _batch(llm, Rewrite, [rewrite_messages(r, s["findings"][r.id]) for r in todo])
        rewrites, errors = {}, []
        for r, o in zip(todo, out, strict=True):
            if isinstance(o, Exception):
                errors.append(f"rewrite {r.id}: {o}")
            else:
                rewrites[r.id] = o.model_dump()
        return {"rewrites": rewrites, "errors": errors}

    g = StateGraph(State)
    for name, fn in [
        ("rules", rules),
        ("embed", embed),
        ("candidates", candidates),
        ("review_pairs", review_pairs),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "rules")
    g.add_edge("rules", "embed")
    g.add_edge("embed", "candidates")
    g.add_edge("candidates", "review_pairs")
    g.add_edge("review_pairs", END)
    if with_rewrite:
        g.add_node("rewrite", rewrite_node)
        g.add_edge("rules", "rewrite")
        g.add_edge("rewrite", END)
    return g.compile()


def run(requirements: list[Requirement], llm, embeddings, rewrite: bool = True) -> State:
    graph = build(llm, embeddings, with_rewrite=rewrite)
    return graph.invoke({"requirements": requirements, "rewrites": {}, "errors": []})
