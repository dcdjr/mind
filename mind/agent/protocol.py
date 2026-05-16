from __future__ import annotations

import json
from typing import Any


def extract_json_object(raw_output: str) -> dict[str, Any] | None:
    """Extract and parse the first JSON object from model output."""
    start = raw_output.find("{")
    end = raw_output.rfind("}")

    if start == -1 or end == -1 or end < start:
        return None

    json_text = raw_output[start : end + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed
