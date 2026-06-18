import json
from typing import Any

import requests

from config import DEFAULT_MODEL, OLLAMA_URL


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = OLLAMA_URL, timeout: int = 180) -> None:
        self.model = model
        self.url = url
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        format_schema: dict[str, Any] | str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_schema is not None:
            payload["format"] = format_schema
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", "")).strip()

    def is_available(self) -> bool:
        try:
            self.generate("OK", temperature=0)
            return True
        except Exception:
            return False


def parse_json_block(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM output does not contain a JSON object.")
    return json.loads(stripped[start : end + 1])
