from ollama import Client

from mind.config import Config

def ask(config: Config, prompt: str) -> str:
    
    client = Client(host=config.model.base_url)

    response = client.chat(model=config.model.default, messages=[
        {
            "role": "user",
            "content": prompt,
        },
    ])

    res = response["message"]["content"]

    return res
