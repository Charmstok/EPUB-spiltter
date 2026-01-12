from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Cut:
    end_line: int  # 1-based inclusive
    title: str | None = None
    summary: str | None = None


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompt.md"


@lru_cache(maxsize=1)
def _load_prompt_sections() -> tuple[str, str]:
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"prompt file not found: {_PROMPT_PATH}")

    system_lines: list[str] = []
    user_lines: list[str] = []
    current: str | None = None
    for raw in _PROMPT_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        if line.strip() == "## system":
            current = "system"
            continue
        if line.strip() == "## user":
            current = "user"
            continue
        if current == "system":
            system_lines.append(line)
        elif current == "user":
            user_lines.append(line)

    system = "\n".join(system_lines).strip()
    user = "\n".join(user_lines).strip()
    if not system or not user:
        raise ValueError(f"prompt.md must contain both '## system' and '## user' sections: {_PROMPT_PATH}")
    return system, user


def _render_user_prompt(
    template: str,
    *,
    start_line: int,
    target_chars_min: int,
    target_chars_max: int,
) -> str:
    return (
        template.replace("{{start_line}}", str(start_line))
        .replace("{{target_chars_min}}", str(target_chars_min))
        .replace("{{target_chars_max}}", str(target_chars_max))
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    s = text.strip()
    if not s:
        raise ValueError("empty model response")
    try:
        value = json.loads(s)
        if isinstance(value, dict):
            return value
    except Exception:  # noqa: BLE001
        pass

    m = _JSON_OBJECT_RE.search(s)
    if not m:
        raise ValueError("no json object found in model response")
    value = json.loads(m.group(0))
    if not isinstance(value, dict):
        raise ValueError("model response json is not an object")
    return value


def build_messages(
    *,
    start_line: int,
    lines: list[tuple[int, str]],
    target_chars_min: int,
    target_chars_max: int,
) -> list[dict[str, str]]:
    system, user_template = _load_prompt_sections()
    user = _render_user_prompt(
        user_template,
        start_line=start_line,
        target_chars_min=target_chars_min,
        target_chars_max=target_chars_max,
    )
    body = "\n".join(f"{i}\t{t}" for i, t in lines)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user.rstrip() + "\n" + body},
    ]


def parse_cuts(text: str) -> list[Cut]:
    obj = _extract_json_object(text)
    raw_cuts = obj.get("cuts")
    if raw_cuts is None:
        raise ValueError('missing required field "cuts"')
    if not isinstance(raw_cuts, list):
        raise ValueError('"cuts" must be a list')

    cuts: list[Cut] = []
    for entry in raw_cuts:
        if not isinstance(entry, dict):
            continue
        end_line = entry.get("end_line")
        if not isinstance(end_line, int):
            continue
        title = entry.get("title")
        summary = entry.get("summary")
        cuts.append(
            Cut(
                end_line=end_line,
                title=title if isinstance(title, str) and title.strip() else None,
                summary=summary if isinstance(summary, str) and summary.strip() else None,
            )
        )
    if not cuts:
        return []

    cuts = sorted(cuts, key=lambda c: c.end_line)
    deduped: list[Cut] = []
    prev = None
    for c in cuts:
        if prev is None or c.end_line > prev:
            deduped.append(c)
            prev = c.end_line
    return deduped


def validate_cuts(
    *,
    cuts: Iterable[Cut],
    min_line: int,
    max_line: int,
) -> list[Cut]:
    out: list[Cut] = []
    prev = min_line - 1
    for c in cuts:
        if c.end_line <= prev:
            continue
        if c.end_line < min_line or c.end_line > max_line:
            continue
        out.append(c)
        prev = c.end_line
    return out
