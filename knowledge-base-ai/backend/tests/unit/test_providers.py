"""Unit tests for T063, T064, T065 — provider stubs and factory registration.

Tests verify:
- OpenAIEmbeddingProvider satisfies the EmbeddingProvider ABC (T063)
- ClaudeLLMProvider satisfies the LLMProvider ABC (T064)
- Factory correctly instantiates stub classes via string key (T065)
- Unknown provider keys still raise ValueError
"""
from __future__ import annotations

import pytest

from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.claude_llm import ClaudeLLMProvider, _SETUP_MSG as CLAUDE_MSG
from app.providers.factory import create_embedding_provider, create_llm_provider
from app.providers.openai_embedding import OpenAIEmbeddingProvider, _SETUP_MSG as OPENAI_MSG


# ---------------------------------------------------------------------------
# T063 — OpenAIEmbeddingProvider stub
# ---------------------------------------------------------------------------


class TestOpenAIEmbeddingProviderStub:
    """OpenAI embedding adapter raises NotImplementedError on every call."""

    def setup_method(self) -> None:
        self.provider = OpenAIEmbeddingProvider()

    def test_is_embedding_provider_subclass(self) -> None:
        assert isinstance(self.provider, EmbeddingProvider)

    @pytest.mark.asyncio
    async def test_embed_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            await self.provider.embed("hello world")
        assert "OpenAI" in str(exc_info.value)
        assert "OPENAI_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_batch_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            await self.provider.embed_batch(["hello", "world"])
        assert "OpenAI" in str(exc_info.value)

    def test_model_version_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            _ = self.provider.model_version
        assert "OpenAI" in str(exc_info.value)

    def test_dimensions_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            _ = self.provider.dimensions
        assert "OpenAI" in str(exc_info.value)

    def test_setup_message_mentions_pip_install(self) -> None:
        assert "pip install openai" in OPENAI_MSG

    def test_setup_message_mentions_env_key(self) -> None:
        assert "OPENAI_API_KEY" in OPENAI_MSG

    def test_setup_message_mentions_model_env_var(self) -> None:
        assert "EMBEDDING_MODEL" in OPENAI_MSG


# ---------------------------------------------------------------------------
# T064 — ClaudeLLMProvider stub
# ---------------------------------------------------------------------------


class TestClaudeLLMProviderStub:
    """Claude LLM adapter raises NotImplementedError on every call."""

    def setup_method(self) -> None:
        self.provider = ClaudeLLMProvider()

    def test_is_llm_provider_subclass(self) -> None:
        assert isinstance(self.provider, LLMProvider)

    @pytest.mark.asyncio
    async def test_generate_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            await self.provider.generate("What is the capital of France?")
        assert "Claude" in str(exc_info.value)
        assert "CLAUDE_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_with_context_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            await self.provider.generate("question", context="some context")

    @pytest.mark.asyncio
    async def test_stream_raises_not_implemented(self) -> None:
        # stream() is an async generator; calling it must raise immediately
        with pytest.raises(NotImplementedError) as exc_info:
            await self.provider.stream("hello")
        assert "Claude" in str(exc_info.value)

    def test_model_version_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            _ = self.provider.model_version
        assert "Claude" in str(exc_info.value)

    def test_setup_message_mentions_pip_install(self) -> None:
        assert "pip install anthropic" in CLAUDE_MSG

    def test_setup_message_mentions_env_key(self) -> None:
        assert "CLAUDE_API_KEY" in CLAUDE_MSG

    def test_setup_message_mentions_model_env_var(self) -> None:
        assert "LLM_MODEL" in CLAUDE_MSG


# ---------------------------------------------------------------------------
# T065 — Factory registration
# ---------------------------------------------------------------------------


class TestFactoryRegistration:
    """create_embedding_provider and create_llm_provider resolve stub classes."""

    def test_create_embedding_provider_openai_returns_correct_type(self) -> None:
        provider = create_embedding_provider("openai")
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_create_embedding_provider_openai_is_embedding_provider(self) -> None:
        provider = create_embedding_provider("openai")
        assert isinstance(provider, EmbeddingProvider)

    def test_create_llm_provider_claude_returns_correct_type(self) -> None:
        provider = create_llm_provider("claude")
        assert isinstance(provider, ClaudeLLMProvider)

    def test_create_llm_provider_claude_is_llm_provider(self) -> None:
        provider = create_llm_provider("claude")
        assert isinstance(provider, LLMProvider)

    def test_create_embedding_provider_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_embedding_provider("unknown-provider")

    def test_create_llm_provider_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_provider("nonexistent")

    def test_create_embedding_provider_error_lists_registered_keys(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            create_embedding_provider("bad-key")
        msg = str(exc_info.value)
        assert "sentence-transformers" in msg
        assert "openai" in msg

    def test_create_llm_provider_error_lists_registered_keys(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            create_llm_provider("bad-key")
        msg = str(exc_info.value)
        assert "ollama" in msg
        assert "claude" in msg

    def test_sentence_transformers_provider_still_registered(self) -> None:
        """Existing providers must not be broken by adding new stubs."""
        from app.providers.local_embedding import LocalEmbeddingProvider
        provider = create_embedding_provider("sentence-transformers")
        assert isinstance(provider, LocalEmbeddingProvider)

    def test_ollama_provider_still_registered(self) -> None:
        """Existing providers must not be broken by adding new stubs."""
        from app.providers.local_llm import LocalLLMProvider
        provider = create_llm_provider("ollama")
        assert isinstance(provider, LocalLLMProvider)


# ===========================================================================
# T077 — LocalEmbeddingProvider  (real implementation, mocked model)
# ===========================================================================

import json
import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ModelUnavailableError
from app.providers.local_embedding import LocalEmbeddingProvider
from app.providers.local_llm import LocalLLMProvider


def _fake_vector(length: int, val: float = 0.5) -> MagicMock:
    v = MagicMock()
    v.tolist.return_value = [val] * length
    return v


class TestLocalEmbeddingProvider:
    """Unit tests for LocalEmbeddingProvider — SentenceTransformer model injected."""

    def test_is_embedding_provider(self) -> None:
        from app.providers.base import EmbeddingProvider
        assert issubclass(LocalEmbeddingProvider, EmbeddingProvider)

    def test_model_version_returns_model_name(self) -> None:
        p = LocalEmbeddingProvider(model_name="nomic-embed-v1", dimensions=4)
        assert p.model_version == "nomic-embed-v1"

    def test_dimensions_property(self) -> None:
        p = LocalEmbeddingProvider(model_name="m", dimensions=768)
        assert p.dimensions == 768

    def test_load_model_caches_instance(self) -> None:
        p = LocalEmbeddingProvider(model_name="m", dimensions=4)
        sentinel = MagicMock()
        p._model = sentinel
        assert p._load_model() is sentinel

    def test_load_model_raises_when_sentence_transformers_missing(self) -> None:
        p = LocalEmbeddingProvider(model_name="missing", dimensions=4)
        orig = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(ModelUnavailableError):
                p._load_model()
        finally:
            if orig is not None:
                sys.modules["sentence_transformers"] = orig
            elif "sentence_transformers" in sys.modules:
                del sys.modules["sentence_transformers"]

    async def test_embed_returns_list_of_floats(self) -> None:
        p = LocalEmbeddingProvider(model_name="fake", dimensions=4)
        fake_model = MagicMock()
        fake_model.encode.return_value = _fake_vector(4, 0.5)
        p._model = fake_model

        result = await p.embed("hello world")

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(isinstance(v, float) for v in result)
        fake_model.encode.assert_called_once_with(
            "hello world",
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    async def test_embed_batch_returns_list_of_vectors(self) -> None:
        p = LocalEmbeddingProvider(model_name="fake", dimensions=4)
        # Batch encode should return an iterable of vectors
        v1, v2 = _fake_vector(4, 0.1), _fake_vector(4, 0.9)
        fake_model = MagicMock()
        fake_model.encode.return_value = [v1, v2]
        p._model = fake_model

        result = await p.embed_batch(["alpha", "beta"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.1, 0.1, 0.1]
        assert result[1] == [0.9, 0.9, 0.9, 0.9]
        fake_model.encode.assert_called_once_with(
            ["alpha", "beta"],
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

    async def test_embed_batch_single_item(self) -> None:
        p = LocalEmbeddingProvider(model_name="fake", dimensions=4)
        v = _fake_vector(4)
        fake_model = MagicMock()
        fake_model.encode.return_value = [v]
        p._model = fake_model

        result = await p.embed_batch(["only one"])

        assert len(result) == 1


# ===========================================================================
# T077 — LocalLLMProvider  (real implementation, mocked httpx)
# ===========================================================================


class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeStreamResponse:
    """Async context manager that iterates newline-delimited JSON lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        pass

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def __aenter__(self) -> "_FakeStreamResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class _FakeAsyncClientBase:
    async def __aenter__(self) -> "_FakeAsyncClientBase":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class TestLocalLLMProvider:
    """Unit tests for LocalLLMProvider — httpx mocked."""

    def test_is_llm_provider(self) -> None:
        from app.providers.base import LLMProvider
        assert issubclass(LocalLLMProvider, LLMProvider)

    def test_model_version_property(self) -> None:
        p = LocalLLMProvider(model="phi3:test", base_url="http://localhost:11434")
        assert p.model_version == "phi3:test"

    def test_build_prompt_contains_question(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        result = p._build_prompt("What is AI?", "")
        assert "What is AI?" in result

    def test_build_prompt_includes_context_section(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        result = p._build_prompt("Q", "Some context text here.")
        assert "### Relevant Document Context" in result
        assert "Some context text here." in result

    def test_build_prompt_no_context_omits_section(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        result = p._build_prompt("Q", "")
        assert "### Relevant Document Context" not in result

    async def test_generate_returns_response_text(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")

        class _FakeClient(_FakeAsyncClientBase):
            async def post(self, url: str, **kw: Any) -> _FakeResponse:
                return _FakeResponse({"response": "the answer"})

        with patch("httpx.AsyncClient", return_value=_FakeClient()):
            result = await p.generate("What is 2+2?")

        assert result == "the answer"

    async def test_generate_raises_model_unavailable_on_connect_error(self) -> None:
        import httpx as _httpx

        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = _httpx.ConnectError(
                "refused", request=MagicMock()
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ModelUnavailableError) as exc:
                await p.generate("Q")
        assert "Cannot connect" in exc.value.message

    async def test_generate_raises_model_unavailable_on_timeout(self) -> None:
        import httpx as _httpx

        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = _httpx.TimeoutException("timed out")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ModelUnavailableError) as exc:
                await p.generate("Q")
        assert "timed out" in exc.value.message

    async def test_generate_raises_on_http_status_error(self) -> None:
        import httpx as _httpx

        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        mock_req, mock_resp = MagicMock(), MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = _httpx.HTTPStatusError(
                "503", request=mock_req, response=mock_resp
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ModelUnavailableError) as exc:
                await p.generate("Q")
        assert "503" in exc.value.message

    async def test_stream_yields_tokens(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        lines = [
            json.dumps({"response": "Hello", "done": False}),
            json.dumps({"response": " world", "done": False}),
            json.dumps({"response": "!", "done": True}),
        ]

        class _FakeClient(_FakeAsyncClientBase):
            def stream(self, *a: Any, **kw: Any) -> _FakeStreamResponse:
                return _FakeStreamResponse(lines)

        with patch("httpx.AsyncClient", return_value=_FakeClient()):
            tokens = [t async for t in p.stream("prompt")]

        assert tokens == ["Hello", " world", "!"]

    async def test_stream_skips_empty_lines(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        lines = [
            "",
            "  ",
            json.dumps({"response": "good", "done": True}),
        ]

        class _FakeClient(_FakeAsyncClientBase):
            def stream(self, *a: Any, **kw: Any) -> _FakeStreamResponse:
                return _FakeStreamResponse(lines)

        with patch("httpx.AsyncClient", return_value=_FakeClient()):
            tokens = [t async for t in p.stream("q")]

        assert tokens == ["good"]

    async def test_stream_stops_at_done(self) -> None:
        p = LocalLLMProvider(model="m", base_url="http://localhost:11434")
        lines = [
            json.dumps({"response": "stop", "done": True}),
            json.dumps({"response": "never", "done": False}),
        ]

        class _FakeClient(_FakeAsyncClientBase):
            def stream(self, *a: Any, **kw: Any) -> _FakeStreamResponse:
                return _FakeStreamResponse(lines)

        with patch("httpx.AsyncClient", return_value=_FakeClient()):
            tokens = [t async for t in p.stream("q")]

        assert tokens == ["stop"]
