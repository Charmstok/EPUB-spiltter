from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

from .rules import Match, Rule, apply_rules


_ZERO_WIDTH = {
    "\ufeff",  # BOM
    "\u200b",  # zero width space
    "\u200c",  # zero width non-joiner
    "\u200d",  # zero width joiner
    "\u2060",  # word joiner
}

@dataclass(frozen=True)
class HeadingMatcher:
    max_len: int
    strict_chapter_title: re.Pattern[str]
    generic_heading: re.Pattern[str]
    other_headings: list[re.Pattern[str]]
    digit_only: bool = True
    skip_leading_titles: int = 0
    leading_title_max_len: int = 20

    def is_strict_chapter_title(self, line: str) -> bool:
        if not line:
            return False
        s = line.strip()
        if not s or len(s) > self.max_len:
            return False
        return bool(self.strict_chapter_title.match(s))

    def is_any_heading(self, line: str) -> bool:
        if not line:
            return False
        s = line.strip()
        if not s:
            return False
        if len(s) > self.max_len:
            return False
        if self.digit_only and s.isdigit():
            return True
        if self.generic_heading.match(s):
            return True
        return any(pat.match(s) for pat in self.other_headings)


_TITLE_LIKE_ALLOWED = re.compile(r"^[0-9A-Za-z\u4e00-\u9fff《》〈〉「」『』“”‘’·—\-？！!?… ]+$")

_OPEN_QUOTES_ONLY = re.compile(r"^[“‘「『《〈]+$")
_CLOSE_QUOTES_ONLY = re.compile(r"^[”’」』》〉】）]+$")


def looks_like_leading_title(line: str, *, max_len: int) -> bool:
    s = line.strip()
    if not s or len(s) > max_len:
        return False
    if "。" in s:
        return False
    if any(ch in "，,;；:：" for ch in s):
        return False
    return bool(_TITLE_LIKE_ALLOWED.match(s))


def _compile_pattern(entry: Any, *, default_flags: str = "") -> re.Pattern[str]:
    if isinstance(entry, str):
        return re.compile(entry, _compile_flags(default_flags))
    if isinstance(entry, dict):
        pattern = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("pattern must be a non-empty string")
        flags = entry.get("flags", default_flags)
        if flags is not None and not isinstance(flags, str):
            raise ValueError("flags must be a string")
        return re.compile(pattern, _compile_flags(flags))
    raise ValueError("pattern entry must be a string or object")


def _compile_flags(flags: str | None) -> int:
    if not flags:
        return 0
    value = 0
    for ch in flags:
        if ch == "i":
            value |= re.IGNORECASE
        elif ch == "m":
            value |= re.MULTILINE
        elif ch == "s":
            value |= re.DOTALL
        else:
            raise ValueError(f"Unsupported regex flag: {ch}")
    return value


def parse_heading_matcher(data: dict[str, Any]) -> HeadingMatcher:
    max_len = data.get("max_len", 80)
    if not isinstance(max_len, int) or max_len <= 0:
        raise ValueError("heading.max_len must be a positive integer")
    digit_only = data.get("digit_only", True)
    if not isinstance(digit_only, bool):
        raise ValueError("heading.digit_only must be a boolean")
    skip_leading_titles = data.get("skip_leading_titles", 0)
    if not isinstance(skip_leading_titles, int) or skip_leading_titles < 0:
        raise ValueError("heading.skip_leading_titles must be a non-negative integer")
    leading_title_max_len = data.get("leading_title_max_len", 20)
    if not isinstance(leading_title_max_len, int) or leading_title_max_len <= 0:
        raise ValueError("heading.leading_title_max_len must be a positive integer")

    strict = data.get("strict_chapter_title")
    generic = data.get("generic_heading")
    others = data.get("other_headings")

    if strict is None or generic is None or others is None:
        raise ValueError(
            'heading must include "strict_chapter_title", "generic_heading", and "other_headings"'
        )
    if not isinstance(others, list):
        raise ValueError("heading.other_headings must be a list")

    return HeadingMatcher(
        max_len=max_len,
        strict_chapter_title=_compile_pattern(strict),
        generic_heading=_compile_pattern(generic),
        other_headings=[_compile_pattern(e) for e in others],
        digit_only=digit_only,
        skip_leading_titles=skip_leading_titles,
        leading_title_max_len=leading_title_max_len,
    )


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in _ZERO_WIDTH:
        text = text.replace(ch, "")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")

    cleaned = []
    for ch in text:
        if ch == "\n":
            cleaned.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("C"):  # control / surrogate / unassigned
            continue
        cleaned.append(ch)
    text = "".join(cleaned)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def iter_paragraphs(text: str) -> Iterator[str]:
    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            continue
        yield s


def iter_sentences(text: str) -> Iterator[str]:
    buf: list[str] = []
    prev = ""
    pending_end = False
    close_quotes = set("”’」』》〉】）")
    for ch in text:
        if pending_end:
            if ch in close_quotes:
                buf.append(ch)
                continue
            sentence = "".join(buf).strip()
            if sentence:
                yield sentence
            buf = [ch]
            prev = ch
            pending_end = False
            continue

        if ch == "\n":
            sentence = "".join(buf).strip()
            if sentence:
                yield sentence
            buf = []
            prev = ""
            pending_end = False
            continue

        buf.append(ch)
        if ch in "。！？!?":
            pending_end = True
            prev = ""
            continue
        if ch == "…":
            if prev == "…":
                pending_end = True
                prev = ""
                continue
            prev = "…"
        else:
            prev = ch

    if pending_end:
        sentence = "".join(buf).strip()
        if sentence:
            yield sentence
        return

    tail = "".join(buf).strip()
    if tail:
        yield tail


@dataclass(frozen=True)
class CleanResult:
    lines: list[str]
    extracted: list[Match]

def _needs_space(prev: str, nxt: str) -> bool:
    if not prev or not nxt:
        return False
    a = prev[-1]
    b = nxt[0]
    return a.isascii() and b.isascii() and a.isalnum() and b.isalnum()


def clean_text_to_paragraph_lines(text: str, rules: Iterable[Rule], headings: HeadingMatcher) -> CleanResult:
    normalized = normalize_text(text)
    lines: list[str] = []
    extracted: list[Match] = []
    include = False
    skip_leading = 0

    for paragraph in iter_paragraphs(normalized):
        if headings.is_any_heading(paragraph):
            include = headings.is_strict_chapter_title(paragraph)
            skip_leading = headings.skip_leading_titles if include else 0
            continue
        if not include:
            continue
        if skip_leading > 0 and looks_like_leading_title(paragraph, max_len=headings.leading_title_max_len):
            skip_leading -= 1
            continue
        skip_leading = 0

        if lines:
            s = paragraph.lstrip()
            i = 0
            while i < len(s) and s[i] in "”’」』》〉】）":
                i += 1
            if i > 0:
                lines[-1] += s[:i]
                paragraph = s[i:].lstrip()
                if not paragraph:
                    continue

        kept: list[str] = []
        pending_prefix = ""
        for sentence in iter_sentences(paragraph):
            cleaned, matches = apply_rules(sentence.strip(), rules)
            extracted.extend(matches)
            if cleaned is None:
                continue
            cleaned = cleaned.strip()
            if not cleaned:
                continue
            if pending_prefix:
                cleaned = pending_prefix + cleaned
                pending_prefix = ""
            if _OPEN_QUOTES_ONLY.match(cleaned):
                pending_prefix += cleaned
                continue
            if _CLOSE_QUOTES_ONLY.match(cleaned) and kept:
                kept[-1] += cleaned
                continue
            kept.append(cleaned)

        if pending_prefix:
            if kept:
                kept[-1] += pending_prefix
            elif lines:
                lines[-1] += pending_prefix

        paragraph_line = ""
        for s in kept:
            if not paragraph_line:
                paragraph_line = s
            else:
                paragraph_line += (" " if _needs_space(paragraph_line, s) else "") + s
        paragraph_line = paragraph_line.strip()
        if paragraph_line:
            lines.append(paragraph_line)

    return CleanResult(lines=lines, extracted=extracted)
