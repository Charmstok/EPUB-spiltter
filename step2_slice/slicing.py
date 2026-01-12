from __future__ import annotations

from dataclasses import dataclass


def count_chars(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def estimate_tokens(text: str) -> int:
    cjk = 0
    ascii_like = 0
    for ch in text:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            cjk += 1
        elif ch.isspace():
            continue
        else:
            ascii_like += 1
    return cjk + (ascii_like + 3) // 4


@dataclass(frozen=True)
class SliceSpan:
    start_idx: int  # 0-based inclusive sentence index
    end_idx: int  # 0-based inclusive sentence index

