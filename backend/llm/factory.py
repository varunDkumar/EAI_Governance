import os

from .base import LLMProvider
from .gemini import GeminiProvider
from .groq_provider import GroqProvider
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider

_provider: LLMProvider | None = None

PROVIDERS = {
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,
}


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        name = os.environ.get("LLM_PROVIDER", "gemini").lower()
        provider_cls = PROVIDERS.get(name, GeminiProvider)
        _provider = provider_cls()
    return _provider
