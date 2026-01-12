from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_clean_config
from .pipeline import clean_epub_to_sentences


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m step1_cleaning.clean",
        description="Clean EPUB into plain paragraphs (one per line) using step1_cleaning/rule/rules.json.",
    )
    p.add_argument("epub", nargs="?", help="Path to .epub file")
    p.add_argument(
        "-o",
        "--out",
        help="Output .txt path (paragraphs, one per line). Default: book/<epub_stem>.txt",
    )
    p.add_argument(
        "--extracted-out",
        help="Optional output JSONL path to store extracted noise (e.g. solicitations)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.epub:
        build_parser().error("epub is required")

    rules_path = Path(__file__).resolve().parent / "rule" / "rules.json"
    if not rules_path.exists():
        build_parser().error(
            f"rules file not found: {rules_path} (create it first)"
        )
    rules, headings = load_clean_config(rules_path)
    result = clean_epub_to_sentences(args.epub, rules=rules, headings=headings)

    out_path = Path(args.out) if args.out else (Path("book") / (Path(args.epub).stem + ".txt"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(result.lines) + "\n", encoding="utf-8")

    if args.extracted_out:
        extracted_path = Path(args.extracted_out)
        with extracted_path.open("w", encoding="utf-8") as f:
            for m in result.extracted:
                f.write(json.dumps({"bucket": m.bucket, "rule": m.rule_name, "text": m.text}, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
