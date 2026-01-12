from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_provider_config, load_slice_config
from .pipeline import SliceRunError, slice_txt_to_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m step2_slice.slice",
        description="Slice Step1-cleaned txt into story slices (json) using LLM.",
    )
    p.add_argument("txt", nargs="?", help="Path to Step1 output .txt (one sentence per line)")
    p.add_argument(
        "--max-slices",
        type=int,
        default=0,
        help="Max number of slices to generate (0 means no limit).",
    )
    p.add_argument(
        "--out-dir",
        help="Output directory. Default: book/<stem>_slice/<timestamp>/",
    )
    p.add_argument(
        "--llm-config",
        default=str(Path(__file__).resolve().parent / "config" / "llm.json"),
        help="Path to llm.json (providers/base_url/api_key/model).",
    )
    p.add_argument(
        "--slice-config",
        default=str(Path(__file__).resolve().parent / "config" / "slice.json"),
        help="Path to slice.json (slice params, retry, chunk tokens).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call LLM; use deterministic slicing (for offline sanity check).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.txt:
        build_parser().error("txt is required")
    if args.max_slices < 0:
        build_parser().error("--max-slices must be >= 0")

    llm_path = Path(args.llm_config)
    slice_path = Path(args.slice_config)
    if not llm_path.exists():
        build_parser().error(f"llm config not found: {llm_path} (copy from llm.example.json)")
    if not slice_path.exists():
        build_parser().error(f"slice config not found: {slice_path} (copy from slice.example.json)")

    providers = load_provider_config(llm_path)
    slice_cfg = load_slice_config(slice_path)
    try:
        out_path = slice_txt_to_json(
            args.txt,
            providers=providers,
            slice_config=slice_cfg,
            out_dir=args.out_dir,
            max_slices=(args.max_slices or None),
            dry_run=bool(args.dry_run),
        )
    except SliceRunError as e:
        # Keep stdout machine-friendly (print output path), and stderr human-friendly.
        print(e.out_path)
        return 2
    else:
        print(out_path)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
