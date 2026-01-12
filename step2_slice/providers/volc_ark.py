from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import urljoin

from .base import ChatProvider, ChatResult, Message
from .http import HttpError, post_json


class VolcArkProvider(ChatProvider):
    def __init__(self, *, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/") + "/"
        self._api_key = api_key

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
        url = urljoin(self._base_url, "api/v3/chat/completions")
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        resp = post_json(
            url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            payload=payload,
            timeout_s=timeout_s,
        )
        try:
            data = json.loads(resp.body.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise HttpError("Invalid JSON response", status=resp.status, body=resp.body) from e

        choices = data.get("choices") or []
        if not choices:
            raise HttpError("Missing choices in response", status=resp.status, body=resp.body)
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise HttpError("Missing message.content in response", status=resp.status, body=resp.body)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ChatResult(content=content, raw=data, usage=usage)

