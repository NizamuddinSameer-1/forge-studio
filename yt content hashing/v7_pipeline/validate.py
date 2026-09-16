from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from v7_pipeline.config import MIN_OUTPUT_BYTES


@dataclass
class ValidationResult:
    ok: bool
    has_video: bool
    has_audio: bool
    duration: float
    size_bytes: int
    message: str


def get_duration_sec(path: str | Path) -> float:
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def get_video_size(path: str | Path) -> tuple[int, int]:
    """(width, height) of the first video stream, or (0, 0) on failure."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return 0, 0


def duration_tolerance_ok(source_sec: float, out_sec: float) -> bool:
    if source_sec <= 0 or out_sec <= 0:
        return out_sec > 0  # if source unknown, only require positive out
    tol = max(0.5, abs(source_sec) * 0.02)
    return abs(out_sec - source_sec) <= tol


def probe_stream_types(path: str | Path) -> tuple[bool, bool]:
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        has_v = any(x == "video" for x in lines)
        has_a = any(x == "audio" for x in lines)
        return has_v, has_a
    except Exception:
        return False, False


def validate_output(
    out_path: str | Path,
    source_duration: float,
    *,
    require_audio: bool = False,
    min_bytes: int = MIN_OUTPUT_BYTES,
) -> ValidationResult:
    p = Path(out_path)
    if not p.exists():
        return ValidationResult(False, False, False, 0.0, 0, "output missing")
    size = p.stat().st_size
    if size < min_bytes:
        return ValidationResult(
            False, False, False, 0.0, size, f"output too small ({size} bytes)"
        )
    has_v, has_a = probe_stream_types(p)
    dur = get_duration_sec(p)
    if not has_v:
        return ValidationResult(False, has_v, has_a, dur, size, "no video stream")
    if require_audio and not has_a:
        return ValidationResult(False, has_v, has_a, dur, size, "no audio stream")
    if source_duration > 0 and not duration_tolerance_ok(source_duration, dur):
        return ValidationResult(
            False,
            has_v,
            has_a,
            dur,
            size,
            f"duration mismatch source={source_sec:.2f}s out={dur:.2f}s",
        )
    msg = "video+audio" if has_a else "video-only (no audio)"
    return ValidationResult(True, has_v, has_a, dur, size, msg)
