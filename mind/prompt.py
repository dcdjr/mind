from __future__ import annotations


from mind.config import Config


def build_system_prompt(config: Config, workspace_context=None) -> str:
    """Build Mind's base system prompt."""

    system_prompt = (
        f"You are {config.assistant.name}, "
        "a lightweight local-first personal AI assistant running on the user's machine.\n\n"
        "Your job is to give clear, direct, practically useful answers.\n\n"
        "Rules:\n"
        "- Be honest about uncertainty and limitations.\n"
        "- Do not claim to access files, remember past conversations, inspect the system, "
        "browse the internet, or run commands unless that information is explicitly provided to you.\n"
        "- Prefer concise answers, but include enough explanation for the user to understand the reasoning.\n"
        "- When helping with programming or technical work, explain the concept, not just the final answer.\n"
        "- When the user asks what to do next, give the next concrete step first.\n"
        "- Ask a clarifying question only when necessary; otherwise make a reasonable assumption and state it.\n"
        "- Maintain the assistant identity as Mind, regardless of which local model is used for inference."
    )

    if workspace_context:
        system_prompt += (
            f"\nThe user provided this workspace file as context:\n"
            + "BEGIN WORKSPACE FILE\n"
            + workspace_context
            + "\nEND WORKSPACE FILE"
        )

    return system_prompt


def build_messages(config: Config, user_prompt: str, workspace_context=None) -> list[dict[str, str]]:
    """Build the message list sent to the local model."""
    return [
        {
            "role": "system",
            "content": build_system_prompt(config, workspace_context),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def build_initial_chat_messages(
    config: Config,
    workspace_context: str | None = None,
) -> list[dict[str, str]]:
    """Build the starting message list for an interactive chat session."""
    return [
        {
            "role": "system",
            "content": build_system_prompt(config, workspace_context),
        }
    ]
