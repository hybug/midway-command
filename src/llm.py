"""Kimi (Moonshot AI) API client with tool use support.

Uses OpenAI-compatible API via the openai package.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable
import json

from openai import OpenAI

from src.config import MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MODEL, MAX_TOKENS


@dataclass
class ToolCall:
    """Record of a tool call made by the LLM."""
    name: str
    input: dict
    result: Optional[str] = None


@dataclass
class ChatResult:
    """Result of a chat interaction."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class LLMClient:
    """Kimi API client (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str = MOONSHOT_API_KEY,
        base_url: str = MOONSHOT_BASE_URL,
        model: str = MODEL,
    ):
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY not set. Check .env file.")
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "User-Agent": "claude-code/1.0",
            },
        )
        self.model = model

    def _normalize_messages(
        self, messages: list[dict], system_prompt: Optional[str]
    ) -> list[dict]:
        """Prepend system message if provided."""
        normalized = []
        if system_prompt:
            normalized.append({"role": "system", "content": system_prompt})
        for msg in messages:
            normalized.append(msg)
        return normalized

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        tool_handlers: Optional[dict[str, Callable]] = None,
        max_tool_calls: int = 10,
    ) -> ChatResult:
        """Chat with Kimi, handling tool use loops.

        Args:
            messages: Conversation history (excluding system).
            system_prompt: System prompt text.
            tools: List of tool definitions (OpenAI format).
            tool_handlers: Dict mapping tool_name -> handler function.
            max_tool_calls: Safety limit to prevent infinite loops.

        Returns:
            ChatResult with text response and metadata.
        """
        chat_messages = self._normalize_messages(messages, system_prompt)
        result = ChatResult()
        total_tool_calls = 0

        while total_tool_calls < max_tool_calls:
            kwargs = {
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "messages": chat_messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            # Track token usage
            if response.usage:
                result.input_tokens += response.usage.prompt_tokens
                result.output_tokens += response.usage.completion_tokens

            # Check for tool calls
            if choice.finish_reason == "tool_calls" and message.tool_calls:
                tool_results = []

                for tc in message.tool_calls:
                    total_tool_calls += 1
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}

                    call_record = ToolCall(name=tool_name, input=tool_input)

                    handler = (
                        tool_handlers.get(tool_name) if tool_handlers else None
                    )
                    if handler:
                        try:
                            call_result = handler(**tool_input)
                            call_record.result = str(call_result)
                        except Exception as e:
                            call_record.result = f"Error: {e}"
                    else:
                        call_record.result = (
                            f"Error: No handler for tool '{tool_name}'"
                        )

                    result.tool_calls.append(call_record)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": call_record.result,
                    })

                # Append assistant's tool_calls request
                # Note: Kimi Code requires reasoning_content on tool call messages
                chat_messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "reasoning_content": "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                })

                # Append tool results
                for tr in tool_results:
                    chat_messages.append(tr)

                continue

            # No tool calls - return text
            result.text = message.content or ""
            return result

        # Safety limit reached
        result.text = "[Error: Maximum tool call limit reached]"
        return result


# Global client instance
_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
