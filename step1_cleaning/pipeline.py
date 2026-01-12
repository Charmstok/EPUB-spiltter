from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable

from .cleaning import CleanResult, HeadingMatcher, clean_text_to_paragraph_lines
from .epub import iter_text_documents
from .html_text import html_to_text
from .rules import Rule


def clean_epub_to_sentences(
    epub_path: str | Path,
    rules: Iterable[Rule] | None = None,
    headings: HeadingMatcher | None = None,
) -> CleanResult:
    epub_path = Path(epub_path)
    if rules is None:
        raise ValueError("rules is required (pass loaded rules from config file)")
    if headings is None:
        raise ValueError("headings is required (pass loaded heading matcher from config file)")
    rules_list = list(rules)
    texts: list[str] = []

    with zipfile.ZipFile(epub_path, "r") as zipf:
        for doc_path in iter_text_documents(zipf):
            try:
                doc_bytes = zipf.read(doc_path)
            except KeyError:
                continue
            texts.append(html_to_text(doc_bytes))

    return clean_text_to_paragraph_lines("\n\n".join(texts), rules_list, headings)
