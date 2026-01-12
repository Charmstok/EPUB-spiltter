from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    type: str  # volc_ark | openai_compatible
    base_url: str
    model: str
    api_key: str | None = None
    api_key_env: str | None = None

    def resolved_api_key(self) -> str:
        if self.api_key is not None:
            v = str(self.api_key).strip()
            if v:
                return v
        if self.api_key_env:
            value = os.environ.get(self.api_key_env)
            if value:
                v = str(value).strip()
                if v:
                    return v
        raise ValueError(
            f"Missing api key for provider={self.name} (set api_key or env {self.api_key_env!r})"
        )


@dataclass(frozen=True)
class SliceConfig:
    provider_order: list[str]
    retry_max: int = 5
    retry_backoff_s: float = 1.0
    timeout_s: float = 120.0

    target_chars_min: int = 5000
    target_chars_max: int = 6000

    chunk_input_tokens: int = 14000
    completion_max_tokens: int = 800
    temperature: float = 0.2
    response_format: str | None = None  # "json_object" (if supported)


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_provider_config(path: str | Path) -> dict[str, ProviderConfig]:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("llm config must be a JSON object")
    providers = data.get("providers")
    if not isinstance(providers, dict):
        raise ValueError('llm config must contain {"providers": {...}}')

    out: dict[str, ProviderConfig] = {}
    for name, entry in providers.items():
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(entry, dict):
            continue
        typ = str(entry.get("type") or "")
        base_url = str(entry.get("base_url") or "")
        model = str(entry.get("model") or "")
        if not typ or not base_url or not model:
            continue
        out[name] = ProviderConfig(
            name=name,
            type=typ,
            base_url=base_url,
            model=model,
            api_key=entry.get("api_key"),
            api_key_env=entry.get("api_key_env"),
        )

    if not out:
        raise ValueError("No valid providers found in llm config")
    return out


def load_slice_config(path: str | Path) -> SliceConfig:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("slice config must be a JSON object")

    provider_order = data.get("provider_order") or []
    if isinstance(provider_order, str):
        provider_order = [provider_order]
    if not isinstance(provider_order, list) or not all(isinstance(x, str) and x for x in provider_order):
        raise ValueError("slice.provider_order must be a non-empty string list")

    retry_max = int(data.get("retry_max", 5))
    if retry_max <= 0:
        raise ValueError("slice.retry_max must be positive")
    retry_backoff_s = float(data.get("retry_backoff_s", 1.0))
    timeout_s = float(data.get("timeout_s", 120.0))

    target_chars_min = int(data.get("target_chars_min", 5000))
    target_chars_max = int(data.get("target_chars_max", 6000))
    if target_chars_min <= 0 or target_chars_max <= 0 or target_chars_min > target_chars_max:
        raise ValueError("slice.target_chars_min/max invalid")

    chunk_input_tokens = int(data.get("chunk_input_tokens", 14000))
    if chunk_input_tokens <= 0:
        raise ValueError("slice.chunk_input_tokens must be positive")
    completion_max_tokens = int(data.get("completion_max_tokens", 800))
    if completion_max_tokens <= 0:
        raise ValueError("slice.completion_max_tokens must be positive")
    temperature = float(data.get("temperature", 0.2))
    response_format = data.get("response_format")
    if response_format is not None and response_format not in ("json_object",):
        raise ValueError('slice.response_format must be "json_object" or null')

    return SliceConfig(
        provider_order=list(provider_order),
        retry_max=retry_max,
        retry_backoff_s=retry_backoff_s,
        timeout_s=timeout_s,
        target_chars_min=target_chars_min,
        target_chars_max=target_chars_max,
        chunk_input_tokens=chunk_input_tokens,
        completion_max_tokens=completion_max_tokens,
        temperature=temperature,
        response_format=response_format,
    )
