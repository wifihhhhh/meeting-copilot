import json
from typing import Any

from services.schema_validator import normalize_minutes


def parse_edited_json(text: str) -> dict[str, Any]:
    return normalize_minutes(json.loads(text))


def to_pretty_json(minutes: dict[str, Any]) -> str:
    if hasattr(minutes, "model_dump"):
        minutes = minutes.model_dump()
    return json.dumps(minutes, ensure_ascii=False, indent=2)
