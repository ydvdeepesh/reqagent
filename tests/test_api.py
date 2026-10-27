import pytest
from fakes import BagOfWords, FakeLLM
from fastapi.testclient import TestClient

from reqagent import api
from reqagent.review import PairVerdict, Rewrite

TEXTS = ["The pump shall stop within 200 ms.", "The pump shall stop within 500 ms."]


def answer(schema, prompt):
    if schema is PairVerdict:
        return PairVerdict(label="conflict", reason="200 ms vs 500 ms")
    return Rewrite(text="The display shall [TBD].", reason="vague")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "get_llm", lambda: FakeLLM(answer))
    monkeypatch.setattr(api, "get_embeddings", lambda: BagOfWords(TEXTS))
    return TestClient(api.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<textarea" in r.text


def test_analyze_plain_text_with_llm(client):
    body = {"content": "\n".join(TEXTS) + "\nThe display shall be user-friendly.\n"}
    r = client.post("/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["report"]["summary"]["conflicts"] == 1
    assert data["report"]["requirements"][2]["rewrite"]["text"] == "The display shall [TBD]."
    assert "_conflicts_with_" in data["sysml"]


def test_analyze_csv_rules_only_needs_no_llm(monkeypatch):
    def boom():
        raise AssertionError("LLM must not be created")

    monkeypatch.setattr(api, "get_llm", boom)
    monkeypatch.setattr(api, "get_embeddings", boom)
    body = {
        "content": "id,text\nA,The UI shall be fast.\n",
        "filename": "x.csv",
        "rules_only": True,
    }
    r = TestClient(api.app).post("/analyze", json=body)
    assert r.status_code == 200
    assert r.json()["report"]["summary"]["by_code"] == {"VAGUE": 1}


def test_bad_input_is_a_400_not_a_500(client):
    r = client.post("/analyze", json={"content": "id,description\nA,x\n", "filename": "x.csv"})
    assert r.status_code == 400 and "text" in r.json()["detail"]


def test_too_many_requirements_rejected(client):
    body = {"content": "\n".join(f"Req {i} shall work." for i in range(api.MAX_REQUIREMENTS + 1))}
    assert client.post("/analyze", json=body).status_code == 413


def test_missing_api_key_is_a_503(monkeypatch):
    monkeypatch.setenv("REQAGENT_LLM", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    api.get_llm.cache_clear()
    r = TestClient(api.app).post("/analyze", json={"content": TEXTS[0]})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_embedding_model_failure_is_a_503(monkeypatch):
    def offline():
        raise ValueError("Could not download model from HuggingFace: 403 Forbidden")

    monkeypatch.setattr(api, "get_llm", lambda: FakeLLM(answer))
    monkeypatch.setattr(api, "get_embeddings", offline)
    r = TestClient(api.app).post("/analyze", json={"content": TEXTS[0]})
    assert r.status_code == 503 and "Embedding model" in r.json()["detail"]


def test_llm_runs_are_limited_per_client(client, monkeypatch):
    monkeypatch.setattr(api, "LIMITER", api.RateLimiter(per_hour=2))
    body = {"content": TEXTS[0]}
    assert client.post("/analyze", json=body).status_code == 200
    assert client.post("/analyze", json=body).status_code == 200
    r = client.post("/analyze", json=body)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # rules-only stays open
    assert client.post("/analyze", json=body | {"rules_only": True}).status_code == 200
    # another caller (last X-Forwarded-For entry, added by the ingress) has its own budget
    other = {"X-Forwarded-For": "198.51.100.7"}
    assert client.post("/analyze", json=body, headers=other).status_code == 200
    assert client.post("/analyze", json=body, headers=other).status_code == 200
    # a forged first entry does not buy that caller a fresh budget
    forged = {"X-Forwarded-For": "1.2.3.4, 198.51.100.7"}
    assert client.post("/analyze", json=body, headers=forged).status_code == 429


def test_rate_limiter_window_slides():
    lim = api.RateLimiter(per_hour=1)
    assert lim.allow("a", now=0) == 0
    assert lim.allow("a", now=10) > 0  # seconds to wait
    assert lim.allow("a", now=3601) == 0
