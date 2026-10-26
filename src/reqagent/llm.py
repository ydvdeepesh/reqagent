"""Model factory. Provider and model come from environment variables (see .env.example)."""

import os

from langchain_core.embeddings import Embeddings

DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-2.5-flash"}
KEY_VARS = {"groq": "GROQ_API_KEY", "gemini": "GOOGLE_API_KEY"}


def chat_model():
    provider = os.getenv("REQAGENT_LLM", "groq").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"REQAGENT_LLM must be one of {list(DEFAULT_MODELS)}, got {provider!r}")
    if not os.getenv(KEY_VARS[provider]):
        raise RuntimeError(
            f"{KEY_VARS[provider]} is not set. Put it in .env and run with "
            "`uv run --env-file .env reqagent ...`, or use --rules-only."
        )
    model = os.getenv("REQAGENT_MODEL", DEFAULT_MODELS[provider])
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, temperature=0, max_retries=5)
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, temperature=0, max_retries=5)


class LocalEmbeddings(Embeddings):
    """Small ONNX model run locally by fastembed: no API key, no rate limit."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
