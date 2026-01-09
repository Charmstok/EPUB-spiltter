from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable
from xml.etree import ElementTree as ET


class EpubError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpineItem:
    href: str
    media_type: str


def _read_xml(zipf: zipfile.ZipFile, path: str) -> ET.Element:
    try:
        data = zipf.read(path)
    except KeyError as e:
        raise EpubError(f"Missing EPUB file: {path}") from e
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise EpubError(f"Invalid XML: {path}") from e


def find_opf_path(zipf: zipfile.ZipFile) -> str:
    container = _read_xml(zipf, "META-INF/container.xml")
    rootfile = container.find(".//{*}rootfile")
    if rootfile is None:
        raise EpubError("Invalid container.xml: missing rootfile")
    opf_path = rootfile.attrib.get("full-path")
    if not opf_path:
        raise EpubError("Invalid container.xml: rootfile missing full-path")
    return opf_path


def iter_spine_items(zipf: zipfile.ZipFile, opf_path: str) -> Iterable[SpineItem]:
    opf = _read_xml(zipf, opf_path)
    opf_dir = str(PurePosixPath(opf_path).parent)
    manifest_items: dict[str, tuple[str, str]] = {}

    for item in opf.findall(".//{*}manifest/{*}item"):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        media_type = item.attrib.get("media-type", "")
        if not item_id or not href:
            continue
        manifest_items[item_id] = (href, media_type)

    spine = opf.find(".//{*}spine")
    if spine is None:
        raise EpubError("Invalid OPF: missing spine")

    for itemref in spine.findall("{*}itemref"):
        idref = itemref.attrib.get("idref")
        if not idref:
            continue
        manifest = manifest_items.get(idref)
        if not manifest:
            continue
        href, media_type = manifest
        if not href:
            continue
        resolved = posixpath.normpath(posixpath.join(opf_dir, href))
        yield SpineItem(href=resolved, media_type=media_type)


def iter_text_documents(zipf: zipfile.ZipFile) -> Iterable[str]:
    opf_path = find_opf_path(zipf)
    for item in iter_spine_items(zipf, opf_path):
        mt = (item.media_type or "").lower()
        if mt in {
            "application/xhtml+xml",
            "text/html",
            "application/html+xml",
        }:
            yield item.href
