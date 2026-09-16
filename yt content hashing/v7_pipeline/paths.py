from __future__ import annotations
import os
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent

def input_dir() -> Path:
    return project_root() / "input"

def output_dir() -> Path:
    return project_root() / "output"

def ensure_dirs() -> tuple[Path, Path]:
    inn, out = input_dir(), output_dir()
    inn.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    return inn, out

def temp_work_dir() -> Path:
    base = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    d = base / "hasher_v7"
    d.mkdir(parents=True, exist_ok=True)
    return d
