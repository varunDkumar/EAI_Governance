from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Vendor-neutral interface. Any provider (Gemini today, Ollama later)
    implements this so the rest of the backend never branches on vendor."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def generate(
        self, *, system_prompt: str, messages: list[dict], temperature: float = 0.3, max_retries: int = 3
    ) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...]"""
        ...
