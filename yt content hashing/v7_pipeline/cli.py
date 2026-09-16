from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from v7_pipeline.batch import list_videos, process_batch
from v7_pipeline.config import PROFILES
from v7_pipeline.paths import ensure_dirs
from v7_pipeline.stage1 import process_video


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="v7_pipeline",
        description="V7 Stage 1 local hashing (re-encode only; no metadata).",
    )
    p.add_argument(
        "--profile",
        default="BALANCED",
        choices=list(PROFILES),
    )
    p.add_argument("--input", type=str, default=None, help="Single input video path")
    p.add_argument(
        "--batch", type=str, default=None, help="Folder of videos to process sequentially"
    )
    p.add_argument("--out", type=str, default=None, help="Output directory (default: ./output)")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--no-pad", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    return p


def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        print(f"[OK] {r.stdout.splitlines()[0]}")
        return True
    except Exception:
        print("[ERR] FFmpeg not found. Install and add to PATH.")
        return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not check_ffmpeg():
        return 1
    inn, default_out = ensure_dirs()
    out = Path(args.out) if args.out else default_out
    pad = not args.no_pad

    if args.batch:
        folder = Path(args.batch)
        vids = list_videos(folder)
        if not vids:
            print(f"[ERR] No videos in {folder}")
            return 1
        process_batch(
            vids,
            out,
            profile=args.profile,
            seed=args.seed,
            pad=pad,
            skip_existing=args.skip_existing,
        )
        return 0

    if args.input:
        src = Path(args.input)
    else:
        vids = list_videos(inn)
        if not vids:
            print(f"[ERR] No videos in {inn}")
            return 1
        # latest by mtime
        src = max(vids, key=lambda f: f.stat().st_mtime)
        print(f"[OK] Latest: {src.name}")

    result = process_video(src, out, profile=args.profile, seed=args.seed, pad=pad)
    return 0 if result else 2


if __name__ == "__main__":
    sys.exit(main())
