from reqagent.llm import chat_model


def test_groq_model_is_rate_limited_and_uses_low_reasoning(monkeypatch):
    monkeypatch.setenv("REQAGENT_LLM", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.delenv("REQAGENT_RPS", raising=False)
    m = chat_model()
    assert m.rate_limiter.requests_per_second == 0.2
    assert m.reasoning_effort == "low"


def test_rate_can_be_set_from_env(monkeypatch):
    monkeypatch.setenv("REQAGENT_LLM", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    monkeypatch.setenv("REQAGENT_RPS", "0.5")
    assert chat_model().rate_limiter.requests_per_second == 0.5
