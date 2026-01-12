from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


Message = Mapping[str, Any]


@dataclass(frozen=True)
class ChatResult:
    content: str
    raw: dict[str, Any]
    usage: dict[str, Any] | None = None


class ChatProvider:
    def chat_completions(
        self,
        *,
        model: str,
        messages: Iterable[Message],
        max_tokens: int,
        temperature: float,
        response_format: dict[str, Any] | None,
        timeout_s: float,
    ) -> ChatResult:
        raise NotImplementedError

