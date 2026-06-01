from __future__ import annotations

import json

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


def world_omens(max_items: int = 5) -> str:
    """Return a live planetary anomaly briefing.

    This tool checks public, no-auth endpoints for:
    - significant earthquakes from USGS
    - active natural events from NASA EONET
    - geomagnetic activity from NOAA SWPC

    Safety model:
    - external read only
    - no shell execution
    - no arbitrary URL input
    - no file writes
    """

    def fetch_json(url: str, timeout: int = 8):
        """Fetch JSON from a fixed trusted endpoint."""
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mind/0.1 world.omens"},
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def safe_fetch(name: str, url: str):
        """Fetch one data source without letting one failed API kill the tool."""
        try:
            return fetch_json(url)
        except Exception as exc:
            return {"_error": f"{name} unavailable: {exc}"}

    # Fixed public endpoints. No user-controlled URL input.
    earthquakes = safe_fetch(
        "USGS earthquakes",
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
    )

    eonet = safe_fetch(
        "NASA EONET",
        "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=7",
    )

    kp_index = safe_fetch(
        "NOAA SWPC K-index",
        "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
    )

    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# World Omens")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("A live briefing from public Earth and space monitoring feeds.")
    lines.append("")

    # Earthquakes
    lines.append("## Earthquakes")

    if "_error" in earthquakes:
        lines.append(f"- {earthquakes['_error']}")
    else:
        features = earthquakes.get("features", [])[:max_items]

        if not features:
            lines.append("- No significant earthquakes reported in the selected feed.")
        else:
            for feature in features:
                props = feature.get("properties", {})
                mag = props.get("mag", "unknown")
                place = props.get("place", "unknown location")
                url = props.get("url", "")
                lines.append(f"- M{mag} — {place} — {url}")

    lines.append("")

    # NASA EONET natural events
    lines.append("## Active Natural Events")

    if "_error" in eonet:
        lines.append(f"- {eonet['_error']}")
    else:
        events = eonet.get("events", [])[:max_items]

        if not events:
            lines.append("- No active EONET events found in the selected window.")
        else:
            for event in events:
                title = event.get("title", "Untitled event")
                categories = event.get("categories", [])
                category_names = ", ".join(
                    category.get("title", "unknown") for category in categories
                )

                geometry = event.get("geometry", [])
                latest = geometry[-1] if geometry else {}
                event_date = latest.get("date", "unknown date")

                lines.append(f"- {title} [{category_names}] — latest update: {event_date}")

    lines.append("")

    # NOAA space weather
    lines.append("## Space Weather")

    if "_error" in kp_index:
        lines.append(f"- {kp_index['_error']}")
    elif not isinstance(kp_index, list) or not kp_index:
        lines.append("- K-index data unavailable or empty.")
    else:
        latest = kp_index[-1]
        time_tag = latest.get("time_tag", "unknown time")
        kp = latest.get("kp_index", "unknown")

        try:
            kp_value = float(kp)
        except (TypeError, ValueError):
            kp_value = 0.0

        if kp_value >= 7:
            mood = "strong geomagnetic storm conditions"
        elif kp_value >= 5:
            mood = "geomagnetic storm threshold"
        elif kp_value >= 4:
            mood = "elevated geomagnetic activity"
        else:
            mood = "quiet to unsettled geomagnetic conditions"

        lines.append(f"- Latest Kp index: {kp} at {time_tag}")
        lines.append(f"- Interpretation: {mood}")

    lines.append("")
    lines.append("## Mind Read")
    lines.append(
        "Earth systems, infrastructure, satellites, weather, and networks all sit inside "
        "a larger physical environment. This tool gives Mind a small live window into that."
    )

    return "\n".join(lines)
