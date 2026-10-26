"""Fake LLM and embeddings so tests never call a real API."""

import re

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda


class FakeLLM:
    """Mimics `with_structured_output`; `answer(schema, prompt_text)` returns the schema object."""

    def __init__(self, answer):
        self.answer = answer
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        def run(messages):
            text = "\n".join(m.content for m in messages)
            self.prompts.append(text)
            return self.answer(schema, text)

        return RunnableLambda(run)


class BagOfWords(Embeddings):
    """Word-count vectors over a fixed vocabulary: similar wording gives similar vectors."""

    def __init__(self, texts: list[str]):
        self.vocab = sorted({w for t in texts for w in re.findall(r"\w+", t.lower())})

    def _vec(self, t):
        words = re.findall(r"\w+", t.lower())
        return [float(words.count(w)) for w in self.vocab]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)
