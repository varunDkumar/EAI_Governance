import json
import urllib.error
import urllib.request

from .base import LLMProvider

DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_HOST = "http://127.0.0.1:11434"


class OllamaProvider(LLMProvider):
    """Fully local, offline provider — no API key, no quota. Implements the
    same LLMProvider interface as Gemini so the rest of the backend (chat,
    memory proposal) never branches on vendor."""

    name = "ollama"

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST):
        self.model = model
        self.host = host

    def is_configured(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/version")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def generate(
        self, *, system_prompt: str, messages: list[dict], temperature: float = 0.3, max_retries: int = 1
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        last_error: Exception | None = None
        for _ in range(max_retries):
            try:
                # Local CPU inference over a long RAG context can genuinely take
                # minutes on modest hardware — this is not a hung connection.
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "")
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                last_error = e
        raise RuntimeError(f"Ollama call failed (is `ollama serve` running and is {self.model} pulled?): {last_error}")
