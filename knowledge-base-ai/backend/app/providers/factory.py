"""Provider factory — resolves embedding and LLM provider instances from config.

Constitution Principle III: All business logic obtains providers via this
factory.  Concrete provider classes are never imported directly outside of
this module and their own test files.

Usage
-----
    from app.providers.factory import create_embedding_provider, create_llm_provider

    embedding = create_embedding_provider()  # uses settings.embedding_provider
    llm = create_llm_provider()              # uses settings.llm_provider

Adding a new provider
---------------------
1. Create ``backend/app/providers/<new_provider>.py`` implementing the
   appropriate ABC from ``base.py``.
2. Register the new string key in the ``_EMBEDDING_PROVIDERS`` or
   ``_LLM_PROVIDERS`` dict below.
"""
from __future__ import annotations

from typing import cast

from app.config import settings
from app.core.logging import get_logger
from app.providers.base import EmbeddingProvider, LLMProvider

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Registry — maps config string → (module_path, class_name)
# ---------------------------------------------------------------------------

_EMBEDDING_PROVIDERS: dict[str, tuple[str, str]] = {
    "sentence-transformers": (
        "app.providers.local_embedding",
        "LocalEmbeddingProvider",
    ),
    "openai": ("app.providers.openai_embedding", "OpenAIEmbeddingProvider"),
    "ollama": ("app.providers.ollama_embedding", "OllamaEmbeddingProvider"),
}

_LLM_PROVIDERS: dict[str, tuple[str, str]] = {
    "ollama": ("app.providers.local_llm", "LocalLLMProvider"),
    "claude": ("app.providers.claude_llm", "ClaudeLLMProvider"),
}


def _load_class(module_path: str, class_name: str) -> type:
    """Dynamically import and return a class to avoid circular imports."""
    import importlib

    module = importlib.import_module(module_path)
    return cast(type, getattr(module, class_name))


def create_embedding_provider(provider: str | None = None) -> EmbeddingProvider:
    """Instantiate and return the configured :class:`EmbeddingProvider`.

    Parameters
    ----------
    provider:
        Provider key string (e.g. ``"sentence-transformers"``).  Defaults to
        ``settings.embedding_provider``.

    Raises
    ------
    ValueError
        If *provider* is not registered in ``_EMBEDDING_PROVIDERS``.
    """
    key = (provider or settings.embedding_provider).lower()
    if key not in _EMBEDDING_PROVIDERS:
        registered = list(_EMBEDDING_PROVIDERS)
        raise ValueError(
            f"Unknown embedding provider {key!r}. "
            f"Registered providers: {registered}"
        )
    module_path, class_name = _EMBEDDING_PROVIDERS[key]
    cls: type[EmbeddingProvider] = _load_class(module_path, class_name)
    instance = cls()
    log.info("embedding_provider_created", provider=key, model=settings.embedding_model)
    return instance


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    """Instantiate and return the configured :class:`LLMProvider`.

    Parameters
    ----------
    provider:
        Provider key string (e.g. ``"ollama"``).  Defaults to
        ``settings.llm_provider``.

    Raises
    ------
    ValueError
        If *provider* is not registered in ``_LLM_PROVIDERS``.
    """
    key = (provider or settings.llm_provider).lower()
    if key not in _LLM_PROVIDERS:
        registered = list(_LLM_PROVIDERS)
        raise ValueError(
            f"Unknown LLM provider {key!r}. "
            f"Registered providers: {registered}"
        )
    module_path, class_name = _LLM_PROVIDERS[key]
    cls: type[LLMProvider] = _load_class(module_path, class_name)
    instance = cls()
    log.info("llm_provider_created", provider=key, model=settings.llm_model)
    return instance
