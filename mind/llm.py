from ollama import Client


from mind.config import Config
from mind.prompt import build_messages


def ask(config: Config, prompt: str) -> str:
    
    client = Client(host=config.model.base_url)

    response = client.chat(
        model=config.model.default,
        messages=build_messages(config, prompt),
    )

    res = response["message"]["content"]

    return res
