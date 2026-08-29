"""Abstract base classes for embedding and LLM providers.

These ABCs define the interface that all provider implementations must
satisfy.  Concrete implementations live in the same package:

- ``local_embedding.py``  — sentence-transformers (nomic-embed-text)
- ``local_llm.py``        — Ollama HTTP API (Phi-3.5-mini-Instruct)
- ``openai_embedding.py`` — future: OpenAI text-embedding-3
- ``claude_llm.py``       — future: Anthropic Claude API
- ``factory.py``          — resolves provider from ``settings``

Constitution Principle III: Embedding + LLM are always accessed through
these interfaces.  Business logic never imports concrete providers directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class EmbeddingProvider(ABC):
    """Interface for generating dense vector embeddings from text.

    All implementations MUST:
    - Return vectors of exactly ``embedding_dimensions`` floats (768 for nomic).
    - Normalise vectors to unit length (required for cosine similarity).
    - Be safe to call concurrently from async code.

    Implementations MAY:
    - Cache the loaded model between calls.
    - Batch inputs for throughput efficiency.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Parameters
        ----------
        text:
            Input text to embed.  Must be non-empty.

        Returns
        -------
        list[float]
            A unit-normalized vector of length ``embedding_dimensions``.
        """

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings in a single forward pass.

        Callers should prefer this over looping ``embed()`` for performance.

        Parameters
        ----------
        texts:
            List of non-empty strings.

        Returns
        -------
        list[list[float]]
            One vector per input text, in the same order.
        """

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Identifier for the currently loaded model.

        Stored in ChromaDB vector metadata for FR-021 version tracking.
        Example: ``"nomic-embed-text-v1.5"``.
        """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Number of dimensions in each output vector (e.g. 768)."""


class LLMProvider(ABC):
    """Interface for generating text completions via a language model.

    All implementations MUST:
    - Accept arbitrary prompt strings and (optionally) a retrieved context.
    - Support both blocking ``generate()`` and async-streaming ``stream()``.
    - Propagate ``ModelUnavailableError`` on connectivity failures.
    """

    @abstractmethod
    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate a complete response to *prompt*.

        Parameters
        ----------
        prompt:
            User query or system prompt.
        context:
            Retrieved document chunks to include as grounding context.
            Implementations join prompt + context into a single model input.

        Returns
        -------
        str
            Full model response as a single string.
        """

    @abstractmethod
    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        """Stream a response to *prompt* token-by-token.

        Yields individual string tokens or text fragments as they are
        produced by the model.  The caller is responsible for concatenating
        the full response for storage.

        Parameters
        ----------
        prompt:
            User query or system prompt.
        context:
            Retrieved document chunks to include as grounding context.

        Yields
        ------
        str
            Incremental text fragments.
        """

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Identifier for the currently loaded model.

        Example: ``"phi3.5:3.8b-mini-instruct-q4_K_M"``.
        """
