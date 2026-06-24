"""Generates vector embeddings using OpenAI, with a deterministic mock fallback when credits are unavailable."""
import hashlib
import logging

import numpy as np
import openai

from config.settings import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536  # Matches text-embedding-3-small output size


def _mock_embedding(text: str) -> list[float]:
    """Return a deterministic unit-normalised vector derived from the text hash.

    Used when OpenAI is unavailable (no credits / offline). The same text
    always produces the same vector, so ChromaDB similarity results are
    consistent within a session — but not semantically meaningful.
    """
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBEDDING_DIMENSIONS).astype(np.float64)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def get_embedding(text: str) -> list[float]:
    """Return an embedding vector for a single text string.

    Tries OpenAI first. Falls back to mock if the API call fails due to
    quota issues — logs a warning so the developer knows mock is active.
    """
    text = text.replace("\n", " ").strip()

    if settings.openai_api_key:
        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except openai.RateLimitError:
            logger.warning(
                "OpenAI quota exceeded — using mock embeddings. "
                "Add billing credits at platform.openai.com/settings/billing."
            )
        except openai.AuthenticationError:
            logger.warning("OpenAI authentication failed — using mock embeddings.")
        except Exception as exc:
            logger.warning("OpenAI embedding failed (%s) — using mock embeddings.", exc)

    return _mock_embedding(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts."""
    return [get_embedding(text) for text in texts]
