"""HTTP API and web page. Run with `reqagent serve`."""

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .analyze import analyze
from .llm import LocalEmbeddings, chat_model
from .parse import parse

MAX_REQUIREMENTS = 200  # keeps one request inside a few minutes of free-tier LLM time
PAGE = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="ReqAgent", version="0.1.0")


class AnalyzeRequest(BaseModel):
    content: str = Field(
        max_length=200_000, description="CSV (id,text) or one requirement per line"
    )
    filename: str = Field("input.txt", description="ends in .csv for CSV input")
    rules_only: bool = False


@lru_cache
def get_llm():
    return chat_model()


@lru_cache
def get_embeddings():
    return LocalEmbeddings()  # loads the ONNX model once per process


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE.read_text(encoding="utf-8")


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    try:
        reqs = parse(req.content, req.filename)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not reqs:
        raise HTTPException(400, "No requirements found.")
    if len(reqs) > MAX_REQUIREMENTS:
        raise HTTPException(413, f"At most {MAX_REQUIREMENTS} requirements per request.")
    if req.rules_only:
        rep, sysml = analyze(reqs)
    else:
        try:
            llm = get_llm()
        except (RuntimeError, ValueError) as e:
            raise HTTPException(503, str(e)) from e
        try:
            embeddings = get_embeddings()
        except Exception as e:  # fastembed raises plain exceptions when the download fails
            raise HTTPException(503, f"Embedding model could not be loaded: {e}") from e
        rep, sysml = analyze(reqs, llm=llm, embeddings=embeddings)
    return {"report": rep, "sysml": sysml}
