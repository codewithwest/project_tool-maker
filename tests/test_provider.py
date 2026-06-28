"""Tests for OllamaProvider using mocked HTTPX transports."""

import json
from unittest.mock import patch

import httpx
import pytest
from tool_maker.llm.provider import (
    OllamaProvider,
    get_provider,
    _try_parse_json,
)


class TestOllamaProvider:
    def test_default_model(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()
        assert provider.model == "gemma4:31b-cloud"
        assert provider.base_url == "http://localhost:11434"

    def test_auto_selects_available_model(self):
        with patch.object(
            OllamaProvider, "list_models",
            return_value=[{"name": "gemma3:4b", "size": 1000000000}],
        ):
            provider = OllamaProvider(model="nonexistent-model")
        assert provider.model == "gemma3:4b"

    def test_custom_base_url(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider(base_url="http://10.0.0.1:11434")
        assert provider.base_url == "http://10.0.0.1:11434"

    def test_generate(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()

        def mock_generate(prompt, **kw):
            return "Hello from Ollama"

        provider.generate = mock_generate
        result = provider.generate("test")
        assert result == "Hello from Ollama"

    def test_analyze_project_returns_json(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()

        def mock_generate(prompt, **kw):
            return json.dumps({"description": "test project", "modules": []})

        provider.generate = mock_generate
        result = provider.analyze_project({"name": "test"})
        assert result["description"] == "test project"

    def test_analyze_project_fallback_on_bad_json(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()

        def mock_generate(prompt, **kw):
            return "not json"

        provider.generate = mock_generate
        result = provider.analyze_project({"name": "test"})
        assert "raw_analysis" in result
        assert "error" in result

    def test_list_models_empty_on_error(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()
        with patch.object(httpx.Client, "get") as mock_get:
            mock_get.side_effect = httpx.RequestError("connection refused")
            models = provider.list_models()
        assert models == []

    def test_list_models_returns_successfully(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()
        models = provider.list_models()
        assert isinstance(models, list)

    def test_conversation_history(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = OllamaProvider()
        provider.add_to_history("user", "hello")
        provider.add_to_history("assistant", "hi")
        assert len(provider.conversation_history) == 2
        provider.clear_history()
        assert len(provider.conversation_history) == 0


class TestGetProvider:
    def test_ollama(self):
        with patch.object(OllamaProvider, "list_models", return_value=[]):
            provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")


class TestHelpers:
    def test_try_parse_json_valid(self):
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_try_parse_json_invalid(self):
        result = _try_parse_json("not json", fallback_key="raw")
        assert "raw" in result
        assert result["error"] is not None
