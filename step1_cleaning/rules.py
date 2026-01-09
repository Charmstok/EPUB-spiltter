from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Match:
    rule_name: str
    bucket: str
    text: str


@dataclass(frozen=True)
class Rule:
    name: str
    kind: str  # drop | extract | replace
    pattern: re.Pattern[str]
    bucket: str = "noise"
    replacement: str = ""

    def apply(self, text: str) -> tuple[str | None, Match | None]:
        if not text:
            return text, None
        if not self.pattern.search(text):
            return text, None

        if self.kind == "drop":
            return None, Match(rule_name=self.name, bucket=self.bucket, text=text)
        if self.kind == "extract":
            return "", Match(rule_name=self.name, bucket=self.bucket, text=text)
        if self.kind == "replace":
            new_text = self.pattern.sub(self.replacement, text)
            return new_text, Match(rule_name=self.name, bucket=self.bucket, text=text)
        raise ValueError(f"Unknown rule kind: {self.kind}")


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


def parse_rules(data: dict[str, Any]) -> list[Rule]:
    version = data.get("version", 1)
    if version != 1:
        raise ValueError(f"Unsupported rules version: {version}")
    rules_data = data.get("rules", [])
    if not isinstance(rules_data, list):
        raise ValueError("rules must be a list")

    rules: list[Rule] = []
    for entry in rules_data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "rule")
        kind = str(entry.get("kind") or "drop")
        pattern = entry.get("pattern")
        if not pattern:
            continue
        flags = _compile_flags(entry.get("flags"))
        bucket = str(entry.get("bucket") or ("solicitation" if kind == "extract" else "noise"))
        replacement = str(entry.get("replacement") or "")
        rules.append(
            Rule(
                name=name,
                kind=kind,
                pattern=re.compile(str(pattern), flags),
                bucket=bucket,
                replacement=replacement,
            )
        )
    return rules


def load_rules(path: str | Path) -> list[Rule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("rules file must be a JSON object")
    return parse_rules(data)


def apply_rules(text: str, rules: Iterable[Rule]) -> tuple[str | None, list[Match]]:
    matches: list[Match] = []
    cur: str | None = text
    for rule in rules:
        if cur is None:
            break
        cur, m = rule.apply(cur)
        if m is not None:
            matches.append(m)
    return cur, matches
