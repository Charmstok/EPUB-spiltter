from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Cut:
    end_line: int  # 1-based inclusive
    title: str | None = None
    summary: str | None = None


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


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
    system = (
        "你是一个小说文本切分器。你的任务是把输入按行编号的句子切分成多个 slice（完整小故事）。"
        "你必须严格按要求输出 JSON，不要输出任何额外文本。"
    )
    user = (
        "请把以下文本切分为若干 slice，并返回切分点。\n"
        "要求：\n"
        f"1) 每个 slice 字数（非空白字符）尽量在 {target_chars_min}～{target_chars_max} 左右，可以略有偏差。\n"
        "2) 必须在句子边界切分（只能在行与行之间切）。\n"
        "3) 只返回本次提供文本中【能组成完整 slice】的切分点；如果末尾不足以组成完整 slice，请不要切最后一段。\n"
        "4) 切分点用 end_line 表示（1-based，包含该行）。end_line 必须严格递增。\n"
        "\n"
        "输出格式（严格 JSON）：\n"
        '{"cuts":[{"end_line":123,"title":"可选","summary":"可选"}]}\n'
        "\n"
        f"本次文本从第 {start_line} 行开始，内容如下（每行格式：<line_no>\\t<sentence>）：\n"
    )
    body = "\n".join(f"{i}\t{t}" for i, t in lines)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user + body},
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
