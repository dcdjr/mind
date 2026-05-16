import urllib.request
import urllib.error

from mind.config import Config


def is_ollama_running(config: Config) -> bool:
    try:
        # Ollama listens on 11434 by default
        with urllib.request.urlopen(config.model.base_url, timeout=2) as response:
            return response.getcode() == 200
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        return False

