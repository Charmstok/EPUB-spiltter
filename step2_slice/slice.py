from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import load_provider_config, load_slice_config
from .pipeline import SliceRunError, slice_txt_to_json


@dataclass
class ProgressBar:
    max_slices: int | None
    total_lines: int | None
    width: int = 32
    last_render: str = ""
    last_len: int = 0

    def update(self, *, slices_written: int, cur_line: int, total_lines: int) -> None:
        if self.max_slices is not None:
            total = max(self.max_slices, 1)
            current = min(slices_written, total)
            label = f"slices {current}/{total}"
        else:
            total = max(total_lines, 1)
            current = min(cur_line, total)
            label = f"lines {current}/{total} | slices {slices_written}"

        pct = current / total
        filled = int(self.width * pct)
        bar = "#" * filled + "-" * (self.width - filled)
        render = f"[{bar}] {pct*100:6.2f}% {label}"

        if render == self.last_render:
            return
        self.last_render = render
        pad = " " * max(0, self.last_len - len(render))
        self.last_len = len(render)
        sys.stderr.write("\r" + render + pad)
        sys.stderr.flush()

    def finish(self) -> None:
        if self.last_render:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self.last_render = ""
            self.last_len = 0


def _count_non_empty_lines(path: str | Path) -> int:
    p = Path(path)
    n = 0
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


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
    max_slices = args.max_slices or None
    total_lines = None if max_slices is not None else _count_non_empty_lines(args.txt)
    progress = ProgressBar(max_slices=max_slices, total_lines=total_lines)
    progress.update(slices_written=0, cur_line=0, total_lines=total_lines or 0)

    def progress_cb(slices_written: int, cur_line: int, total: int) -> None:
        progress.update(slices_written=slices_written, cur_line=cur_line, total_lines=total)

    try:
        out_path = slice_txt_to_json(
            args.txt,
            providers=providers,
            slice_config=slice_cfg,
            out_dir=args.out_dir,
            max_slices=max_slices,
            dry_run=bool(args.dry_run),
            progress_cb=progress_cb,
        )
    except SliceRunError as e:
        # Keep stdout machine-friendly (print output path), and stderr human-friendly.
        print(e.out_path)
        return 2
    finally:
        progress.finish()

    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
