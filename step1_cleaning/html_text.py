from __future__ import annotations

import html
from html.parser import HTMLParser


_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "hr",
    "li",
    "ul",
    "ol",
    "table",
    "tr",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
}


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._chunks: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "head"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth > 0:
            return
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "head"}:
            if self._ignore_depth > 0:
                self._ignore_depth -= 1
            return
        if self._ignore_depth > 0:
            return
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return
        if data:
            self._chunks.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._ignore_depth > 0:
            return
        self._chunks.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self._ignore_depth > 0:
            return
        self._chunks.append(html.unescape(f"&#{name};"))

    def get_text(self) -> str:
        return "".join(self._chunks)


def html_to_text(html_bytes: bytes) -> str:
    text = html_bytes.decode("utf-8", errors="replace")
    parser = HTMLTextExtractor()
    parser.feed(text)
    parser.close()
    return parser.get_text()
