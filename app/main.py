from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

from app.editor_engine import (
    EXPORT_RESOLUTIONS,
    FONT_MAP,
    PIPELINE_AVAILABLE,
    PIPELINE_ERROR,
    PROFILES,
    execute_full_pipeline,
    ml_profiles,
    ml_stage_status,
    probe_video,
)

app = FastAPI(
    title="Custom Video Editing Micro-Studio",
    description="Video editing studio integrated with v7 content hashing pipeline",
    version="2.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_store_middleware(request: Request, call_next):
    """Keep the studio from serving a stale UI after edits to html/css/js."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# Mount static assets, uploads, and outputs
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


# ==========================================================================
# Request models
# ==========================================================================
class FetchUrlRequest(BaseModel):
    url: str = Field(..., description="YouTube, Instagram, or social media video URL")


class CropConfig(BaseModel):
    enabled: bool = True
    x: int = 0
    y: int = 0
    width: int = 1080
    height: int = 1920


class ColorGradeConfig(BaseModel):
    sharpen: float = 0.0      # 0.0 to 2.5
    brightness: float = 0.0   # -1.0 to 1.0
    contrast: float = 1.0     # 0.1 to 2.5
    saturation: float = 1.0   # 0.0 to 3.0
    temperature: float = 0.0  # -0.5 to 0.5
    # CapCut-style extended suite (all identity by default)
    exposure: float = 0.0     # -1.0 to 1.0 (gamma)
    highlights: float = 0.0   # -1.0 to 1.0 (colorlevels white point)
    shadows: float = 0.0      # -1.0 to 1.0 (colorlevels black point)
    tint: float = 0.0         # -1.0 to 1.0 (green <-> magenta)
    fade: float = 0.0         # 0.0 to 1.0 (filmic fade via curves)
    grain: float = 0.0        # 0.0 to 1.0 (film grain)
    vignette: float = 0.0     # 0.0 to 1.0 (darkened corners)


class MaskConfig(BaseModel):
    id: str = "mask_1"
    enabled: bool = True
    x: int = 50
    y: int = 50
    width: int = 200
    height: int = 100
    blur: int = 20            # blur radius, or pixel block size in pixelate mode
    mode: str = "blur"        # "blur" | "pixelate"


class TextLayer(BaseModel):
    id: str = "text_1"
    text: str = ""
    x: int = 50
    y: int = 50
    font_family: str = "Arial Bold"
    font_size: int = 36
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    bg_enabled: bool = False
    bg_color: str = "#000000"
    bg_opacity: float = 0.6
    start: Optional[float] = None  # show from (seconds); None = whole clip
    end: Optional[float] = None    # hide after (seconds); None = whole clip


class HashingConfig(BaseModel):
    enabled: bool = True
    profile: str = "BALANCED"
    seed: Optional[int] = None
    pad: bool = True


class ExportConfig(BaseModel):
    # Exact output canvas. "1080p" -> 1080x1920 for 9:16 crops (platform
    # standard), "720p" -> 720x1280, "source" -> keep the crop's own size.
    resolution: str = Field("1080p", description="1080p | 720p | source")


class ProcessVideoRequest(BaseModel):
    filename: str
    trim_start: float = 0.0
    trim_end: Optional[float] = None
    crop: Optional[CropConfig] = None
    color_grade: Optional[ColorGradeConfig] = None
    mask: Optional[MaskConfig] = None          # legacy single mask
    masks: Optional[List[MaskConfig]] = None   # preferred: any number of masks
    text_layers: Optional[List[TextLayer]] = None
    hashing: Optional[HashingConfig] = None
    export: Optional[ExportConfig] = None


class StorageClearRequest(BaseModel):
    kind: str = Field("outputs", description="'uploads', 'outputs' or 'all'")
    older_than_hours: float = Field(
        0.0, ge=0.0, description="Only delete files older than this. 0 = everything."
    )


# ==========================================================================
# Shared helpers
# ==========================================================================
def _safe_child(directory: Path, filename: str) -> Path:
    """Resolve a filename inside `directory`, refusing anything that escapes it."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    candidate = (directory / filename).resolve()
    if candidate.parent != directory.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename.")
    return candidate


def _upload_path(filename: str) -> Path:
    """Resolve an upload filename, refusing anything that escapes the folder."""
    return _safe_child(UPLOADS_DIR, filename)


def _edit_kwargs(req: ProcessVideoRequest) -> Dict[str, Any]:
    """The user's edit settings, in the shape execute_full_pipeline expects."""
    # New multi-mask list wins; fall back to the legacy single `mask` field.
    masks = None
    if req.masks is not None:
        masks = [m.model_dump() for m in req.masks if m.enabled]
    elif req.mask is not None:
        masks = [req.mask.model_dump()] if req.mask.enabled else []

    return {
        "trim_start": req.trim_start,
        "trim_end": req.trim_end,
        "crop": req.crop.model_dump() if req.crop else None,
        "color_grade": req.color_grade.model_dump() if req.color_grade else None,
        "masks": masks,
        "text_layers": [t.model_dump() for t in req.text_layers] if req.text_layers else None,
        "export": req.export.model_dump() if req.export else None,
    }


def _hash_settings(req: ProcessVideoRequest) -> tuple[bool, str, Optional[int], bool]:
    hashing = req.hashing
    return (
        hashing.enabled if hashing else True,
        hashing.profile if hashing else "BALANCED",
        hashing.seed if hashing else None,
        hashing.pad if hashing else True,
    )


def _config_signature(req: ProcessVideoRequest, apply_hashing: bool) -> str:
    """Stable fingerprint of everything that affects the rendered bytes.

    Used so an export can hand back the already-hashed file instead of
    re-rendering, and so we can tell when edits have invalidated a hash.
    """
    payload = {
        "filename": req.filename,
        "edits": _edit_kwargs(req),
        "hashing": req.hashing.model_dump() if req.hashing else None,
        "apply_hashing": apply_hashing,
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _decorate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add the browser-facing URLs to a pipeline result."""
    result["download_url"] = f"/api/download/{result['file_name']}"
    result["stream_url"] = f"/outputs/{result['file_name']}"
    return result


# ==========================================================================
# Hashing job infrastructure
#
# Hashing is the slow step, so it runs on a worker thread while the UI polls
# for progress. The pipeline's own stdout is captured line by line so the
# studio can show the real thing instead of a fake progress bar.
# ==========================================================================
JOBS: Dict[str, Dict[str, Any]] = {}
HASH_REGISTRY: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_MAX_LOG_LINES = 500
_MAX_JOBS_KEPT = 20

# A wedged job must not block the studio forever. Generous enough for a long
# encode on a slow machine, but finite.
JOB_MAX_SECONDS = float(os.environ.get("FORGE_JOB_TIMEOUT", "7200"))

# Overall-progress bands per pipeline stage, so the UI bar moves smoothly
# through "Rendering edits" -> "V7 hash encode" -> "Finalizing".
_STEP_BANDS = {
    2: {1: (0, 85), 2: (85, 100)},
    3: {1: (0, 30), 2: (30, 92), 3: (92, 100)},
}


def _band_progress(job: Dict[str, Any], pct: int) -> int:
    step = job.get("step") or {}
    bands = _STEP_BANDS.get(step.get("total", 3), _STEP_BANDS[3])
    lo, hi = bands.get(step.get("current", 1), (0, 100))
    return int(round(lo + (hi - lo) * max(0, min(100, pct)) / 100))


def _janitor() -> None:
    """Periodically fail jobs that have clearly wedged."""
    while True:
        time.sleep(30)
        now = time.time()
        with _JOBS_LOCK:
            for job in JOBS.values():
                if job["status"] != "running":
                    continue
                if now - job["started_at"] <= JOB_MAX_SECONDS:
                    continue
                job["status"] = "error"
                job["stage"] = "Timed out"
                job["error"] = (
                    f"This job ran longer than {JOB_MAX_SECONDS / 60:.0f} minutes and was "
                    "marked as failed. It may still be finishing in the background."
                )
                job["finished_at"] = now


@app.on_event("startup")
async def start_janitor() -> None:
    threading.Thread(target=_janitor, name="forge-janitor", daemon=True).start()


_STAGE_MARKER = re.compile(r"^\[STAGE (\d+)/(\d+)\]\s*(.*)$")
_RENDER_PROGRESS = re.compile(r"^RENDER_PROGRESS (\d{1,3})$")
_TQDM_PROGRESS = re.compile(r"(\d{1,3})%")


class _JobLogStream(io.TextIOBase):
    """A stdout/stderr replacement that tees every line into a job's log buffer.

    It additionally parses real progress markers into exact percentages, so
    the studio shows true progress instead of a fake indeterminate sweep:
      - `RENDER_PROGRESS n`   (editor render, band-mapped to stage 1)
      - tqdm `NN%|...` bars   (v7 hash encode, band-mapped to stage 2)
    """

    def __init__(self, job_id: str, parse_progress: bool = False):
        self.job_id = job_id
        self.parse_progress = parse_progress
        self._pending = ""

    def write(self, text: str) -> int:
        self._pending += text
        while True:
            match = re.search(r"[\r\n]", self._pending)
            if not match:
                break
            line = self._pending[: match.start()].strip()
            self._pending = self._pending[match.end():]
            if not line:
                continue

            # Real progress markers never spam the visible log.
            m = _RENDER_PROGRESS.match(line)
            if m:
                _set_progress(self.job_id, int(m.group(1)), banded=True)
                continue
            pct = _TQDM_PROGRESS.search(line)
            if self.parse_progress and pct and ("|" in line or "Encoding" in line):
                _set_progress(self.job_id, int(pct.group(1)), banded=True)
                continue

            _append_log(self.job_id, line)
            if "retrying with simpler audio chain" in line:
                # The encoder restarts from 0% on this retry. Without a stage
                # change that looks like a stall or a failure in the UI.
                _set_stage(
                    self.job_id,
                    "Audio encode failed - retrying with a simpler audio chain...",
                )
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def _set_progress(job_id: str, pct: int, banded: bool = False) -> None:
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job["progress"] = _band_progress(job, pct) if banded else max(0, min(100, pct))


def _append_log(job_id: str, line: str) -> None:
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job["logs"].append(line)
        if len(job["logs"]) > _MAX_LOG_LINES:
            del job["logs"][: len(job["logs"]) - _MAX_LOG_LINES]


def _set_stage(job_id: str, stage: str, reset_progress: bool = True) -> None:
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is not None:
            job["stage"] = stage
            if reset_progress:
                job["progress"] = None


def _on_stage(job_id: str, marker: str) -> None:
    """Pipeline stage callback: `[STAGE k/N] label` markers drive the stepper,
    plain strings just update the stage label."""
    m = _STAGE_MARKER.match(marker)
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is not None:
            if m:
                job["step"] = {
                    "current": int(m.group(1)),
                    "total": int(m.group(2)),
                    "label": m.group(3),
                }
                job["stage"] = m.group(3)
                job["progress"] = None
            else:
                job["stage"] = marker
                job["progress"] = None
            job["logs"].append(marker)


def _running_job_id() -> Optional[str]:
    for job_id, job in JOBS.items():
        if job["status"] == "running":
            return job_id
    return None


def _prune_jobs() -> None:
    finished = [
        jid for jid, job in JOBS.items() if job["status"] != "running"
    ]
    for jid in finished[:-_MAX_JOBS_KEPT]:
        JOBS.pop(jid, None)


def _create_job(kind: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "running",
            "stage": "Queued",
            "step": {"current": 0, "total": 3, "label": "Queued"},
            "progress": None,
            "logs": [],
            "result": None,
            "error": None,
            "started_at": time.time(),
            "finished_at": None,
        }
    _prune_jobs()
    return job_id


def _finish_job(job_id: str, result: Optional[Dict[str, Any]], error: Optional[str]) -> None:
    with _JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "error" if error else "done"
        job["result"] = result
        job["error"] = error
        job["finished_at"] = time.time()
        if not error:
            job["stage"] = "Complete"
            if job.get("step"):
                job["step"]["current"] = job["step"]["total"]
                job["step"]["label"] = "Complete"
            job["progress"] = 100


def _run_hash_job(
    job_id: str,
    req: ProcessVideoRequest,
    signature: str,
) -> None:
    """Worker thread: render the edits, then hand off to the v7 hash engine."""
    in_path = UPLOADS_DIR / req.filename
    apply_hashing, profile, seed, pad = _hash_settings(req)

    stream = _JobLogStream(job_id, parse_progress=True)
    progress_stream = _JobLogStream(job_id, parse_progress=True)
    previous_stdout = sys.stdout
    previous_stderr = sys.stderr
    try:
        sys.stdout = stream
        sys.stderr = progress_stream
        _on_stage(job_id, "[STAGE 0/3] Queued")

        result = execute_full_pipeline(
            input_video=in_path,
            output_dir=OUTPUTS_DIR,
            apply_hashing=apply_hashing,
            hashing_profile=profile,
            seed=seed,
            pad_bytes=pad,
            on_stage=lambda stage: _on_stage(job_id, stage),
            **_edit_kwargs(req),
        )

        if not result.get("success"):
            _finish_job(job_id, None, result.get("error", "Unknown pipeline error"))
            return

        _decorate(result)
        result["signature"] = signature
        result["hashed_at"] = time.time()

        with _JOBS_LOCK:
            HASH_REGISTRY[signature] = result

        _finish_job(job_id, result, None)
    except Exception as exc:  # noqa: BLE001 - surface anything to the UI
        _finish_job(job_id, None, f"{type(exc).__name__}: {exc}")
    finally:
        sys.stdout = previous_stdout
        sys.stderr = previous_stderr


# ==========================================================================
# Routes
# ==========================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return HTMLResponse(
        content=index_file.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/api/profiles")
async def get_hashing_profiles():
    profile_descriptions = {
        "SAFE": "Lowest strength. Barely changes anything. Safe against quality loss.",
        "BALANCED": "Default. Medium strength. Good balance of protection and video fidelity.",
        "AGGRESSIVE": "High strength. Extra jitter and shifts for stubborn duplicate detection.",
        "AIMIMIC": "High strength. Applies subtle AI-generated aesthetic (bloom, saturation lift).",
        "TOON": "Medium strength. Optimized specifically for cartoon/anime/flat graphics content.",
        "MAXIMUM": "Maximum strength. Nuclear option with all perturbations turned to max.",
    }
    names = list(PROFILES.keys()) if PROFILES else list(profile_descriptions.keys())
    ml_names = set(ml_profiles())
    profiles = [
        {
            "name": name,
            "description": profile_descriptions.get(name, "Custom V7 content hashing profile."),
            "is_default": name == "BALANCED",
            # These profiles ask for the Stage 1.5 AI pass; without the deps
            # they silently skip it, which the UI needs to say out loud.
            "uses_ml": name in ml_names,
        }
        for name in names
    ]
    return {
        "profiles": profiles,
        "fonts": list(FONT_MAP.keys()),
        "export_resolutions": list(EXPORT_RESOLUTIONS),
        "engine": {
            "available": PIPELINE_AVAILABLE,
            "error": PIPELINE_ERROR or None,
        },
        "ml_stage": ml_stage_status(),
        "ml_profiles": sorted(ml_names),
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename.")

    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    unique_name = f"{int(time.time())}_{clean_name}"
    save_path = UPLOADS_DIR / unique_name

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        meta = probe_video(save_path)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid video file: {e}")

    return {
        "success": True,
        "filename": unique_name,
        "url": f"/uploads/{unique_name}",
        "width": meta["width"],
        "height": meta["height"],
        "duration": meta["duration"],
        "fps": meta["fps"],
        "size_mb": round(meta["size_bytes"] / (1024 * 1024), 2),
    }


@app.post("/api/fetch-url")
async def fetch_url(req: FetchUrlRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    out_id = f"url_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    out_tmpl = str(UPLOADS_DIR / f"{out_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url,
    ]

    print(f"[yt-dlp] Downloading URL: {url}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Download timed out after 30 minutes.")
    if res.returncode != 0:
        print(f"[ERR] yt-dlp error:\n{res.stderr}")
        raise HTTPException(status_code=400, detail=f"Failed to download video: {res.stderr[:300]}")

    matching = list(UPLOADS_DIR.glob(f"{out_id}.*"))
    if not matching:
        raise HTTPException(status_code=500, detail="Downloaded video file was not found.")

    target_file = matching[0]
    try:
        meta = probe_video(target_file)
    except Exception as e:
        target_file.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Downloaded file is not a readable video: {e}")

    return {
        "success": True,
        "filename": target_file.name,
        "url": f"/uploads/{target_file.name}",
        "width": meta["width"],
        "height": meta["height"],
        "duration": meta["duration"],
        "fps": meta["fps"],
        "size_mb": round(meta["size_bytes"] / (1024 * 1024), 2),
    }


@app.post("/api/hash")
async def start_hash_job(req: ProcessVideoRequest):
    """Start the content hashing step. Returns a job id to poll."""
    in_path = _upload_path(req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail=f"Video '{req.filename}' not found in uploads.")

    apply_hashing, _, _, _ = _hash_settings(req)
    if apply_hashing and not PIPELINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "Content hashing engine is unavailable, so nothing was hashed. "
                f"Reason: {PIPELINE_ERROR or 'v7_pipeline failed to import'}. "
                "Fix it with:  pip install -r requirements.txt"
            ),
        )

    running = _running_job_id()
    if running:
        raise HTTPException(
            status_code=409,
            detail=f"Another job is already running ({running}). Wait for it to finish.",
        )

    signature = _config_signature(req, apply_hashing)
    job_id = _create_job("hash")

    thread = threading.Thread(
        target=_run_hash_job,
        args=(job_id, req, signature),
        name=f"hash-job-{job_id}",
        daemon=True,
    )
    thread.start()

    return {
        "success": True,
        "job_id": job_id,
        "signature": signature,
        "engine_available": PIPELINE_AVAILABLE,
    }


@app.get("/api/hash/{job_id}")
async def get_hash_job(job_id: str, since: int = 0):
    """Poll a hashing job. `since` returns only log lines the UI hasn't seen."""
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job id.")

    logs = job["logs"]
    since = max(0, min(since, len(logs)))
    elapsed = (job["finished_at"] or time.time()) - job["started_at"]

    return {
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "step": job.get("step"),
        "progress": job.get("progress"),
        "logs": logs[since:],
        "log_total": len(logs),
        "elapsed": round(elapsed, 1),
        "result": job["result"],
        "error": job["error"],
    }


@app.post("/api/export")
async def export_video(req: ProcessVideoRequest):
    """Hand back the final file.

    Hashing is its own step now, so when hashing is enabled we only reuse an
    already-hashed render that matches the current settings exactly. If the
    edits changed since hashing, we say so instead of silently re-hashing.
    """
    in_path = _upload_path(req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail=f"Video '{req.filename}' not found in uploads.")

    apply_hashing, profile, seed, pad = _hash_settings(req)

    if apply_hashing:
        if not PIPELINE_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Content hashing engine is unavailable, so nothing was hashed. "
                    f"Reason: {PIPELINE_ERROR or 'v7_pipeline failed to import'}. "
                    "Fix it with:  pip install -r requirements.txt"
                ),
            )

        signature = _config_signature(req, True)
        cached = HASH_REGISTRY.get(signature)
        if cached and Path(cached.get("file_path", "")).exists():
            return {**cached, "reused": True}

        raise HTTPException(
            status_code=409,
            detail=(
                "These edits have not been hashed yet. Run Content Hashing first, "
                "then export."
            ),
            headers={"X-Needs-Hash": "1"},
        )

    # Hashing switched off: export the edited video on its own.
    try:
        result = execute_full_pipeline(
            input_video=in_path,
            output_dir=OUTPUTS_DIR,
            apply_hashing=False,
            hashing_profile=profile,
            seed=seed,
            pad_bytes=pad,
            **_edit_kwargs(req),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering pipeline failed: {e}")

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown pipeline error"))

    return {**_decorate(result), "reused": False}


@app.post("/api/process")
async def process_video_endpoint(req: ProcessVideoRequest):
    """Synchronous one-shot render (+ optional hashing). Handy for scripting."""
    in_path = _upload_path(req.filename)
    if not in_path.exists():
        raise HTTPException(status_code=404, detail=f"Video '{req.filename}' not found in uploads.")

    apply_hashing, profile, seed, pad = _hash_settings(req)

    try:
        result = execute_full_pipeline(
            input_video=in_path,
            output_dir=OUTPUTS_DIR,
            apply_hashing=apply_hashing,
            hashing_profile=profile,
            seed=seed,
            pad_bytes=pad,
            **_edit_kwargs(req),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering pipeline failed: {e}")

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown pipeline error"))

    if apply_hashing:
        with _JOBS_LOCK:
            HASH_REGISTRY[_config_signature(req, True)] = result

    return _decorate(result)


# ==========================================================================
# Storage - uploads and outputs pile up fast with large videos
# ==========================================================================
STORAGE_KINDS = {"uploads": UPLOADS_DIR, "outputs": OUTPUTS_DIR}


def _storage_dir(kind: str) -> Path:
    directory = STORAGE_KINDS.get(kind)
    if directory is None:
        raise HTTPException(status_code=400, detail="kind must be 'uploads' or 'outputs'.")
    return directory


def _list_storage(directory: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        items.append({
            "name": path.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
        })
    items.sort(key=lambda item: item["modified"], reverse=True)
    return items


@app.get("/api/storage")
async def get_storage():
    """What is using disk, so it can be cleaned up without leaving the studio."""
    uploads = _list_storage(UPLOADS_DIR)
    outputs = _list_storage(OUTPUTS_DIR)
    with _JOBS_LOCK:
        in_use = {
            result.get("file_name")
            for result in HASH_REGISTRY.values()
            if result.get("file_name")
        }
    return {
        "uploads": uploads,
        "outputs": outputs,
        "uploads_total_mb": round(sum(i["size_mb"] for i in uploads), 2),
        "outputs_total_mb": round(sum(i["size_mb"] for i in outputs), 2),
        # Deleting these means the next export has to re-hash.
        "in_use": sorted(in_use),
    }


@app.delete("/api/storage/{kind}/{filename}")
async def delete_storage_item(kind: str, filename: str):
    """Delete one stored file. Only ever touches the two managed folders."""
    target = _safe_child(_storage_dir(kind), filename)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    size = target.stat().st_size
    try:
        target.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not delete: {e}")
    return {
        "success": True,
        "deleted": filename,
        "freed_mb": round(size / (1024 * 1024), 2),
    }


@app.post("/api/storage/clear")
async def clear_storage(req: StorageClearRequest):
    """Bulk delete, scoped to the managed folders and optionally age-limited."""
    directories = (
        [UPLOADS_DIR, OUTPUTS_DIR] if req.kind == "all" else [_storage_dir(req.kind)]
    )
    cutoff = (
        time.time() - req.older_than_hours * 3600 if req.older_than_hours > 0 else None
    )

    deleted: List[str] = []
    freed = 0
    skipped = 0
    for directory in directories:
        for path in directory.iterdir():
            if not path.is_file():
                continue
            try:
                stat = path.stat()
                if cutoff is not None and stat.st_mtime > cutoff:
                    skipped += 1
                    continue
                path.unlink()
                deleted.append(path.name)
                freed += stat.st_size
            except OSError:
                skipped += 1

    return {
        "success": True,
        "deleted_count": len(deleted),
        "deleted": deleted,
        "skipped_count": skipped,
        "freed_mb": round(freed / (1024 * 1024), 2),
    }


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = (OUTPUTS_DIR / filename).resolve()
    if file_path.parent != OUTPUTS_DIR.resolve() or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/debug/threads")
async def debug_threads():
    """Local diagnostic: dump every thread's stack.

    Handy when a job appears stuck - this shows exactly where.
    """
    frames = sys._current_frames()
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    for tid, frame in frames.items():
        stack = traceback.format_stack(frame)
        out.append({
            "thread": names.get(tid, str(tid)),
            "stack": [line.rstrip("\n") for line in stack],
        })
    return {
        "threads": out,
        "jobs": {
            jid: {
                "status": job["status"],
                "stage": job["stage"],
                "age": round(time.time() - job["started_at"], 1),
                "log_total": len(job["logs"]),
            }
            for jid, job in JOBS.items()
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("FORGE_PORT", "8000"))
    print("\n" + "=" * 60)
    print("  Custom Video Editing Micro-Studio")
    print(f"  Open in your browser: http://localhost:{port}")
    if PIPELINE_AVAILABLE:
        print(f"  Hash engine: READY ({len(PROFILES)} profiles)")
    else:
        print(f"  Hash engine: UNAVAILABLE - {PIPELINE_ERROR}")
        print("  Fix with:  pip install -r requirements.txt")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=port)
