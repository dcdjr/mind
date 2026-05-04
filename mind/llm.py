from ollama import Client


from mind.config import Config
from mind.prompt import build_messages


def ask(config: Config, prompt: str, workspace_context=None) -> str:
    
    client = Client(host=config.model.base_url)

    response = client.chat(
        model=config.model.default,
        messages=build_messages(config, prompt, workspace_context),
    )

    res = response["message"]["content"]

    return res
