from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

from mind.core.config import Config


def tool_internet_github_zen(config: Config, args: dict[str, Any]) -> str:
    """Fetch a short random phrase from GitHub's public Zen API."""
    url = "https://api.github.com/zen"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "mind-local",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace").strip()
        return (
            f"Error: GitHub Zen API returned HTTP {error.code} "
            f"{error.reason}. Response body: {error_body}"
        )
    except urllib.error.URLError as error:
        return f"Error: Could not reach GitHub Zen API: {error.reason}"
    except TimeoutError:
        return "Error: GitHub Zen API request timed out."

    if not body:
        return "Error: GitHub Zen API returned an empty response."

    return f"GitHub Zen: {body}"
