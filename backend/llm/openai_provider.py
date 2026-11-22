import json
import os
import re
import time
import urllib.error
import urllib.request

from .base import LLMProvider

DEFAULT_MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"
MAX_RETRIES = 3
_RETRY_DELAY_RE = re.compile(r"retry.{0,10}?(\d+(?:\.\d+)?)s", re.IGNORECASE)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def generate(
        self, *, system_prompt: str, messages: list[dict], temperature: float = 0.3, max_retries: int = MAX_RETRIES
    ) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature,
        }
        body = json.dumps(payload).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(max_retries):
            req = urllib.request.Request(
                API_URL,
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"] or ""
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"{e.code} {e.reason}: {detail}")
                if e.code not in (429, 503) or attempt >= max_retries - 1:
                    raise last_error
                match = _RETRY_DELAY_RE.search(detail)
                time.sleep(min(float(match.group(1)) + 1, 12) if match else 2**attempt)
            except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = e
                if attempt >= max_retries - 1:
                    raise
                time.sleep(2**attempt)
        raise last_error  # type: ignore[misc]
