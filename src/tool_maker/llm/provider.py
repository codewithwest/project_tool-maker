"""
LLM Provider - Ollama-based provider for Tool Maker.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemma4:31b-cloud"):
        self.api_key = api_key
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text based on the prompt (sync)."""

    @abstractmethod
    async def async_generate(self, prompt: str, **kwargs) -> str:
        """Generate text based on the prompt (async)."""

    @abstractmethod
    def analyze_project(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze project info and provide insights (sync)."""

    @abstractmethod
    async def async_analyze_project(
        self, project_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze project info and provide insights (async)."""

    def add_to_history(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        self.conversation_history = []


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation.

    Communicates with a local Ollama server at the configured base URL.
    Default endpoint: http://localhost:11434
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemma4:31b-cloud",
        base_url: str = OLLAMA_DEFAULT_BASE_URL,
    ):
        super().__init__(api_key, model)
        self.base_url = base_url.rstrip("/")
        self.model = self._resolve_model(model)

    def _resolve_model(self, preferred: str) -> str:
        """Auto-select a model that actually exists on the server.

        Tries the preferred model first. Falls back to the first
        available non-embedding model if the preferred one isn't found.
        """
        try:
            models = self.list_models()
            names = [
                m["name"]
                for m in models
                if "embed" not in m["name"].lower()
            ]
            if preferred in names:
                return preferred
            if names:
                logger.info(
                    "Model '%s' not found, using '%s' instead",
                    preferred, names[0],
                )
                return names[0]
        except Exception as e:
            logger.warning("Could not resolve model: %s", e)
        return preferred

    def _chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    def _tags_url(self) -> str:
        return f"{self.base_url}/api/tags"

    def list_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from Ollama's /api/tags endpoint.

        Returns:
            List of model dicts with keys: name, modified_at, size.
            Empty list on error.
        """
        try:
            with httpx.Client() as client:
                resp = client.get(self._tags_url(), timeout=10)
                resp.raise_for_status()
                data = resp.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning("Failed to fetch models from Ollama: %s", e)
            return []

    async def async_list_models(self) -> List[Dict[str, Any]]:
        """Async version of list_models()."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self._tags_url(), timeout=10)
                resp.raise_for_status()
                data = resp.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning("Failed to fetch models from Ollama: %s", e)
            return []

    def _build_messages(self, prompt: str, **kwargs) -> List[Dict[str, str]]:
        msgs = kwargs.get("messages") or [
            {"role": "user", "content": prompt}
        ]
        return msgs

    def _build_payload(self, messages: List[Dict[str, str]], **kwargs) -> Dict:
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs.get("options", {}),
        }

    def _parse_response(self, response_data: Dict) -> str:
        return response_data["message"]["content"]

    def generate(self, prompt: str, **kwargs) -> str:
        logger.info("── LLM REQUEST ──────────────────────────────────────")
        logger.info("Model: %s", self.model)
        for line in prompt.splitlines():
            logger.info("  %s", line)
        logger.info("──────────────────────────────────────────────────")
        messages = self._build_messages(prompt, **kwargs)

        with httpx.Client() as client:
            resp = client.post(
                self._chat_url(),
                json=self._build_payload(messages, **kwargs),
                timeout=kwargs.get("timeout", 120),
            )
            resp.raise_for_status()
            response_text = self._parse_response(resp.json())

        logger.info("── LLM RESPONSE ─────────────────────────────────────")
        for line in response_text.splitlines():
            logger.info("  %s", line)
        logger.info("──────────────────────────────────────────────────")
        return response_text

    async def async_generate(self, prompt: str, **kwargs) -> str:
        logger.debug(
            "Ollama async_generate: model=%s prompt_len=%d", self.model, len(
                prompt)
        )
        messages = self._build_messages(prompt, **kwargs)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._chat_url(),
                json=self._build_payload(messages, **kwargs),
                timeout=kwargs.get("timeout", 120),
            )
            resp.raise_for_status()
            return self._parse_response(resp.json())

    def analyze_project(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        prompt = _build_analysis_prompt(project_info)
        response = self.generate(prompt)
        return _try_parse_json(response, "raw_analysis")

    async def async_analyze_project(
        self, project_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = _build_analysis_prompt(project_info)
        response = await self.async_generate(prompt)
        return _try_parse_json(response, "raw_analysis")


def _build_analysis_prompt(project_info: Dict[str, Any]) -> str:
    return (
        "Analyze the following project information and provide:\n"
        "1. A brief description of what the project does\n"
        "2. Key modules and their purposes\n"
        "3. Available capabilities and functions\n"
        "4. Suggested tools that could enhance this project\n\n"
        f"Project Information:\n{project_info}\n\n"
        "Please provide your analysis in JSON format with keys: "
        "description, modules, capabilities, suggested_tools."
    )


def _try_parse_json(
    text: str, fallback_key: str = "raw_response"
) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {fallback_key: text, "error": "Could not parse JSON response"}


def get_provider(provider_name: str, **kwargs) -> LLMProvider:
    """Factory function to get an LLM provider."""
    providers = {
        "ollama": OllamaProvider,
    }

    if provider_name.lower() not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")

    return providers[provider_name.lower()](**kwargs)
