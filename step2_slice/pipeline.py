from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import ProviderConfig, SliceConfig
from .providers.base import ChatProvider
from .providers.openai_compatible import OpenAICompatibleProvider
from .providers.volc_ark import VolcArkProvider
from .segmenter import Cut, build_messages, parse_cuts, validate_cuts
from .slicing import count_chars, estimate_tokens


@dataclass(frozen=True)
class SliceItem:
    slice_id: int
    source_txt: str
    start_line: int
    end_line: int
    char_len: int | None
    text: str | None
    created_at: str
    method: str  # llm | fallback | dry_run | error
    title: str | None = None
    summary: str | None = None
    provider: str | None = None
    model: str | None = None
    error: str | None = None


class SliceRunError(RuntimeError):
    def __init__(self, *, out_path: Path, message: str):
        super().__init__(message)
        self.out_path = out_path


def _timestamp_dirname() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _build_provider(cfg: ProviderConfig) -> ChatProvider:
    api_key = cfg.resolved_api_key()
    if cfg.type == "volc_ark":
        return VolcArkProvider(base_url=cfg.base_url, api_key=api_key)
    if cfg.type == "openai_compatible":
        return OpenAICompatibleProvider(base_url=cfg.base_url, api_key=api_key)
    raise ValueError(f"Unknown provider type: {cfg.type}")


def _sleep_backoff(attempt: int, *, base: float) -> None:
    time.sleep(base * (2**attempt))


def _choose_chunk_end(
    sentences: list[str],
    *,
    start_idx: int,
    chunk_input_tokens: int,
) -> int:
    tokens = 0
    end_idx = start_idx
    while end_idx < len(sentences):
        s = sentences[end_idx]
        add = estimate_tokens(s) + 1  # newline-ish overhead
        if end_idx > start_idx and tokens + add > chunk_input_tokens:
            break
        tokens += add
        end_idx += 1
    return max(end_idx, start_idx + 1)


def _heuristic_cut_end(
    sentences: list[str],
    *,
    start_idx: int,
    target_min: int,
    target_max: int,
) -> int:
    total = 0
    end_idx = start_idx
    best: int | None = None
    best_over = 10**18
    while end_idx < len(sentences):
        total += count_chars(sentences[end_idx])
        if total >= target_min:
            over = abs(total - ((target_min + target_max) // 2))
            if total <= target_max and over < best_over:
                best = end_idx
                best_over = over
            if total > target_max:
                break
        end_idx += 1
    if best is not None:
        return best
    return min(end_idx, len(sentences) - 1)


def slice_txt_to_json(
    txt_path: str | Path,
    *,
    providers: dict[str, ProviderConfig],
    slice_config: SliceConfig,
    out_dir: str | Path | None = None,
    max_slices: int | None = None,
    dry_run: bool = False,
) -> Path:
    txt_path = Path(txt_path)
    sentences = [line.strip() for line in txt_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not sentences:
        raise ValueError(f"Empty input: {txt_path}")
    if max_slices is not None and max_slices <= 0:
        raise ValueError("max_slices must be positive or None")

    stem = txt_path.stem
    out_base = Path(out_dir) if out_dir else (Path("book") / f"{stem}_slice" / _timestamp_dirname())
    out_base.mkdir(parents=True, exist_ok=True)
    out_json = out_base / "slices.json"
    meta_path = out_base / "run.json"

    meta_path.write_text(
        json.dumps(
            {
                "source_txt": str(txt_path),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "slice_config": asdict(slice_config),
                "provider_order": slice_config.provider_order,
                "dry_run": dry_run,
                "max_slices": max_slices,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if dry_run:
        provider_clients: dict[str, tuple[ChatProvider, ProviderConfig]] = {}
    else:
        ordered_cfgs: list[tuple[str, ProviderConfig]] = []
        for name in slice_config.provider_order:
            cfg = providers.get(name)
            if cfg is None:
                raise ValueError(f"provider not found in llm config: {name}")
            ordered_cfgs.append((name, cfg))
        provider_clients = {name: (_build_provider(cfg), cfg) for name, cfg in ordered_cfgs}

    def iter_provider_order() -> list[str]:
        if not provider_clients:
            raise ValueError("No providers available (check slice.provider_order and llm config)")
        return list(provider_clients.keys())

    slice_id = 1
    cur = 0
    run_error: str | None = None
    with out_json.open("w", encoding="utf-8") as f:
        f.write("[\n")
        first_item = True

        def write_item(item: SliceItem) -> None:
            nonlocal first_item
            payload = {k: v for k, v in asdict(item).items() if v is not None}
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            rendered = "\n".join("  " + line for line in rendered.splitlines())
            if first_item:
                first_item = False
            else:
                f.write(",\n")
            f.write(rendered)

        stop = False
        while cur < len(sentences) and not stop:
            if max_slices is not None and slice_id > max_slices:
                break
            if dry_run:
                end_idx = _heuristic_cut_end(
                    sentences,
                    start_idx=cur,
                    target_min=slice_config.target_chars_min,
                    target_max=slice_config.target_chars_max,
                )
                text = "\n".join(sentences[cur : end_idx + 1])
                item = SliceItem(
                    slice_id=slice_id,
                    source_txt=str(txt_path),
                    start_line=cur + 1,
                    end_line=end_idx + 1,
                    char_len=count_chars(text),
                    text=text,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    method="dry_run",
                )
                write_item(item)
                slice_id += 1
                cur = end_idx + 1
                continue

            chunk_end = _choose_chunk_end(sentences, start_idx=cur, chunk_input_tokens=slice_config.chunk_input_tokens)
            lines = [(i + 1, sentences[i]) for i in range(cur, chunk_end)]
            messages = build_messages(
                start_line=cur + 1,
                lines=lines,
                target_chars_min=slice_config.target_chars_min,
                target_chars_max=slice_config.target_chars_max,
            )
            response_format = {"type": slice_config.response_format} if slice_config.response_format else None

            cuts: list[Cut] = []
            last_error: Exception | None = None
            last_provider: str | None = None
            last_model: str | None = None
            used_provider: str | None = None
            used_model: str | None = None

            for provider_name in iter_provider_order():
                client, pcfg = provider_clients[provider_name]
                for attempt in range(slice_config.retry_max):
                    try:
                        result = client.chat_completions(
                            model=pcfg.model,
                            messages=messages,
                            max_tokens=slice_config.completion_max_tokens,
                            temperature=slice_config.temperature,
                            response_format=response_format,
                            timeout_s=slice_config.timeout_s,
                        )
                        parsed = parse_cuts(result.content)
                        cuts = validate_cuts(cuts=parsed, min_line=cur + 1, max_line=chunk_end)
                        used_provider = provider_name
                        used_model = pcfg.model
                        last_error = None
                        break
                    except Exception as e:  # noqa: BLE001
                        last_provider = provider_name
                        last_model = pcfg.model
                        last_error = e
                        if attempt < slice_config.retry_max - 1:
                            _sleep_backoff(attempt, base=slice_config.retry_backoff_s)
                if cuts:
                    break

            if not cuts:
                item = SliceItem(
                    slice_id=slice_id,
                    source_txt=str(txt_path),
                    start_line=cur + 1,
                    end_line=chunk_end,
                    char_len=None,
                    text=None,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    method="error",
                    provider=last_provider,
                    model=last_model,
                    error=str(last_error) if last_error is not None else "LLM returned no valid cuts",
                )
                write_item(item)
                run_error = item.error
                stop = True
                continue

            # 应用切割；如果模型在此部分拒绝切割，请确保进度
            progressed = False
            for cut in cuts:
                end_idx = cut.end_line - 1
                if end_idx < cur:
                    continue
                text = "\n".join(sentences[cur : end_idx + 1])
                char_len = count_chars(text)
                if char_len < slice_config.target_chars_min:
                    # 这个切分点太靠前了，继续尝试后面的切分点（更长，可能达标）
                    continue
                if char_len > slice_config.target_chars_max:
                    # 已经超过上限，后面的 end_line 只会更长，直接终止
                    break
                item = SliceItem(
                    slice_id=slice_id,
                    source_txt=str(txt_path),
                    start_line=cur + 1,
                    end_line=end_idx + 1,
                    char_len=char_len,
                    text=text,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    method="llm",
                    title=cut.title,
                    summary=cut.summary,
                    provider=used_provider,
                    model=used_model,
                )
                write_item(item)
                slice_id += 1
                if max_slices is not None and slice_id > max_slices:
                    stop = True
                cur = end_idx + 1
                progressed = True
                if stop:
                    break

            if not progressed:
                item = SliceItem(
                    slice_id=slice_id,
                    source_txt=str(txt_path),
                    start_line=cur + 1,
                    end_line=chunk_end,
                    char_len=None,
                    text=None,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    method="error",
                    provider=used_provider,
                    model=used_model,
                    error=(
                        "LLM returned cuts but none could be applied: "
                        f"no candidate end_line produced char_len within "
                        f"[{slice_config.target_chars_min}, {slice_config.target_chars_max}] "
                        "under current counting rules"
                    ),
                )
                write_item(item)
                run_error = item.error
                stop = True

        f.write("\n]\n")

    if run_error:
        # Also surface the error in terminal output (stderr), while keeping output JSON written.
        print(f"slice error: {run_error}", file=sys.stderr)
        print(f"output: {out_json}", file=sys.stderr)
        raise SliceRunError(out_path=out_json, message=run_error)

    return out_json


def slice_txt_to_jsonl(*args: Any, **kwargs: Any) -> Path:
    # Backward-compatible alias (older docs wrote JSONL).
    return slice_txt_to_json(*args, **kwargs)
