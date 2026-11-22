import os
import re
import time

from .base import LLMProvider

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_RETRIES = 3
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY"))

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return self._client

    def generate(
        self, *, system_prompt: str, messages: list[dict], temperature: float = 0.3, max_retries: int = MAX_RETRIES
    ) -> str:
        from google.genai import types

        client = self._get_client()
        contents = [
            types.Content(role=("model" if m["role"] == "assistant" else "user"), parts=[types.Part(text=m["content"])])
            for m in messages
        ]
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=temperature),
                )
                return response.text or ""
            except Exception as e:  # noqa: BLE001 - retry transient errors (503/429), surface the rest
                last_error = e
                message = str(e)
                if "UNAVAILABLE" not in message and "RESOURCE_EXHAUSTED" not in message:
                    raise
                if attempt < max_retries - 1:
                    match = _RETRY_DELAY_RE.search(message)
                    # Cap the wait: respect the server's hint but don't let one
                    # call balloon past ~12s, especially for callers (like the
                    # best-effort memory proposal) that shouldn't hold up the
                    # user-facing response for too long.
                    delay = min(float(match.group(1)) + 2, 12) if match else 2**attempt
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]
