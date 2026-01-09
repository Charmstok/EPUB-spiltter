from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cleaning import HeadingMatcher, parse_heading_matcher
from .rules import Rule, parse_rules


def load_clean_config(path: str | Path) -> tuple[list[Rule], HeadingMatcher]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("rules file must be a JSON object")

    rules = parse_rules(data)
    heading = data.get("heading")
    if heading is None:
        raise ValueError('Missing required "heading" section in rules.json')
    if not isinstance(heading, dict):
        raise ValueError('"heading" must be an object')
    heading_matcher = parse_heading_matcher(heading)
    return rules, heading_matcher

