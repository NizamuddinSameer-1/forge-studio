from __future__ import annotations

from pathlib import Path

from v7_pipeline.paths import VIDEO_EXTS
from v7_pipeline.stage1 import process_video


def list_videos(folder: str | Path) -> list[Path]:
    p = Path(folder)
    if not p.exists():
        return []
    return sorted(
        [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTS],
        key=lambda f: f.stat().st_mtime,
    )


def should_skip_existing(input_path: Path, out_dir: Path) -> bool:
    stem = input_path.stem
    if not out_dir.exists():
        return False
    for f in out_dir.iterdir():
        if (
            f.is_file()
            and f.name.startswith(f"{stem}_v7_")
            and f.suffix.lower() in VIDEO_EXTS
        ):
            return True
    return False


def summarize(results: list[tuple[str, str | None]]) -> dict[str, int]:
    ok = sum(1 for _, r in results if r and r != "SKIP")
    skip = sum(1 for _, r in results if r == "SKIP")
    err = sum(1 for _, r in results if r is None)
    return {"ok": ok, "err": err, "skip": skip, "total": len(results)}


def process_batch(
    videos: list[Path],
    out_dir: str | Path,
    *,
    profile: str = "BALANCED",
    seed: int | None = None,
    pad: bool = True,
    skip_existing: bool = False,
) -> list[tuple[str, str | None]]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str | None]] = []
    for i, v in enumerate(videos, 1):
        print(f"\n{'=' * 60}\n[{i}/{len(videos)}] {v.name}\n{'=' * 60}")
        if skip_existing and should_skip_existing(v, out):
            print(f"[SKIP] Existing _v7_ output for stem {v.stem}")
            results.append((v.name, "SKIP"))
            continue
        try:
            r = process_video(v, out, profile=profile, seed=seed, pad=pad)
        except Exception as e:
            print(f"[ERR] Exception: {e}")
            r = None
        results.append((v.name, r))
    s = summarize(results)
    print(
        f"\n[SUMMARY] OK={s['ok']} ERR={s['err']} SKIP={s['skip']} total={s['total']}"
    )
    return results
