import urllib.error
import urllib.request

from mind.core.config import Config


def is_ollama_running(config: Config) -> bool:
    """Return whether the configured Ollama endpoint responds successfully."""
    try:
        with urllib.request.urlopen(config.model.base_url, timeout=2) as response:
            return response.getcode() == 200
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        return False
