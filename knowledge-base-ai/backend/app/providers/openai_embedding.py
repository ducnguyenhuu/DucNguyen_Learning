"""OpenAI embedding adapter stub (T063).

This module satisfies the EmbeddingProvider ABC so the provider factory can
instantiate it via ``EMBEDDING_PROVIDER=openai`` in .env.  All methods raise
``NotImplementedError`` with clear setup instructions until a real
implementation is added.

To activate:
    1. ``pip install openai``
    2. Set ``OPENAI_API_KEY=<your-key>`` in backend/.env
    3. Set ``EMBEDDING_MODEL=text-embedding-3-small`` (or another model)
    4. Replace the ``NotImplementedError`` bodies below with real API calls.
"""
from __future__ import annotations

from app.providers.base import EmbeddingProvider

_SETUP_MSG = (
    "OpenAI embedding adapter is not yet configured. "
    "To enable it: (1) pip install openai, "
    "(2) set OPENAI_API_KEY in backend/.env, "
    "(3) set EMBEDDING_MODEL to the desired OpenAI model name "
    "(e.g. text-embedding-3-small), "
    "(4) implement the method bodies in openai_embedding.py."
)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Stub adapter for OpenAI text-embedding models.

    Raises ``NotImplementedError`` on every call to signal that the adapter
    has not been wired up with a real API key and implementation yet.
    """

    async def embed(self, text: str) -> list[float]:  # noqa: D401
        """Embed a single text string via the OpenAI Embeddings API.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple strings in a single API call.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)

    @property
    def model_version(self) -> str:
        """Return the configured OpenAI embedding model name.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)

    @property
    def dimensions(self) -> int:
        """Return the output vector size for the configured model.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)
