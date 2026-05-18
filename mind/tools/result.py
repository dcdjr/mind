from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:
    """Structured result from running one Mind tool."""

    tool_name: str
    success: bool
    output: str
    error: str | None = None

    @classmethod
    def success_result(cls, tool_name: str, output: str) -> "ToolResult":
        """Create a successful tool result."""
        return cls(
            tool_name=tool_name,
            success=True,
            output=output,
            error=None,
        )

    @classmethod
    def failure_result(cls, tool_name: str, error: str) -> "ToolResult":
        """Create a failed tool result with a user-facing error output."""
        clean_error = error.strip()

        if clean_error.startswith("Error:"):
            output = clean_error
        else:
            output = f"Error: {clean_error}"

        return cls(
            tool_name=tool_name,
            success=False,
            output=output,
            error=output,
        )
