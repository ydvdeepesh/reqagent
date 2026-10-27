"""HTTP API and web page. Run with `reqagent serve`."""

import os
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .analyze import analyze
from .llm import LocalEmbeddings, chat_model
from .parse import parse

MAX_REQUIREMENTS = 200  # keeps one request inside a few minutes of free-tier LLM time
PAGE = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="ReqAgent", version="0.1.0")


class RateLimiter:
    """Sliding one-hour window per client.

    shortcut: in-memory, so each replica counts separately and a restart resets it;
    move to Redis if the app ever runs more than one replica.
    """

    def __init__(self, per_hour: int):
        self.per_hour = per_hour
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> int:
        """0 if allowed (and counted), otherwise seconds until the next free slot."""
        now = time.time() if now is None else now
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - 3600:
                q.popleft()
            if len(q) >= self.per_hour:
                return int(q[0] + 3600 - now) + 1
            q.append(now)
            return 0


# LLM runs cost free-tier quota; rule checks are cheap and stay unlimited.
LIMITER = RateLimiter(per_hour=int(os.getenv("REQAGENT_LLM_RUNS_PER_HOUR", "10")))


def client_ip(request: Request) -> str:
    # The ingress appends the real caller to X-Forwarded-For; earlier entries come from the
    # client and can be forged, so only the last one counts.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() or (
        request.client.host if request.client else "unknown"
    )


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
def analyze_endpoint(req: AnalyzeRequest, request: Request):
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
        wait = LIMITER.allow(client_ip(request))
        if wait:
            raise HTTPException(
                429,
                f"LLM analysis limit reached ({LIMITER.per_hour} per hour). "
                "Try again later or tick 'Rule checks only'.",
                headers={"Retry-After": str(wait)},
            )
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
