from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Add 'yt content hashing' to sys.path so we can import v7_pipeline
PROJECT_ROOT = Path(__file__).resolve().parent.parent
YT_HASHING_DIR = PROJECT_ROOT / "yt content hashing"
if str(YT_HASHING_DIR) not in sys.path:
    sys.path.insert(0, str(YT_HASHING_DIR))

PIPELINE_AVAILABLE = False
PIPELINE_ERROR = ""

try:
    from v7_pipeline.config import PROFILES, Profile, get_profile
    from v7_pipeline.stage1 import process_video as v7_process_video, sha256_file

    PIPELINE_AVAILABLE = True
except Exception as e:  # noqa: BLE001 - a broken engine must not kill the studio
    print(f"[WARN] Failed to import v7_pipeline: {e}")
    print("[WARN] Content hashing is UNAVAILABLE until this is fixed.")
    print("[WARN] Fix with:  pip install -r requirements.txt")
    PROFILES = {}
    v7_process_video = None
    sha256_file = None
    PIPELINE_ERROR = f"{type(e).__name__}: {e}"


def _clean_stem(name: str) -> str:
    """Drop the upload timestamp prefix (e.g. '1789241102_') for readable outputs."""
    stripped = re.sub(r"^\d{10}_", "", name)
    return stripped or name


def work_dir() -> Path:
    """Scratch space for intermediate renders.

    Deliberately outside the project folder: this project often lives inside
    OneDrive, and writing throwaway files into a synced directory invites sync
    locks and slow placeholder hydration that can stall a render.
    """
    base = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    d = base / "forge_studio_work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ml_stage_status() -> Dict[str, Any]:
    """Can the optional Stage 1.5 (AI) pass actually run in this interpreter?

    v7_pipeline.ml.ml_available() only checks for torch, so on a machine with
    torch but no open_clip it reports True and the stage is attempted, fails
    inside the CLIP encoder, and quietly returns the unmodified file. Several
    profiles advertise ml_stage=True, so we report what will really happen
    rather than letting the studio imply AI protection that isn't there.
    """
    import importlib.util

    has_torch = importlib.util.find_spec("torch") is not None
    has_open_clip = importlib.util.find_spec("open_clip") is not None
    cuda = False

    if has_torch:
        try:
            import torch  # noqa: PLC0415 - intentional lazy import

            cuda = bool(torch.cuda.is_available())
        except Exception:
            has_torch = False

    if not has_torch:
        reason = "torch is not installed for this Python"
    elif not has_open_clip:
        reason = "open_clip is not installed for this Python"
    else:
        reason = ""

    return {
        "runnable": has_torch and has_open_clip,
        "device": "cuda" if cuda else "cpu",
        "cuda": cuda,
        "torch": has_torch,
        "open_clip": has_open_clip,
        "reason": reason,
    }


def ml_profiles() -> List[str]:
    """Profile names that ask for the AI stage (and will skip it without deps)."""
    if not PROFILES:
        return []
    return [name for name, prof in PROFILES.items() if getattr(prof, "ml_stage", False)]


FONTS_DIR = Path(__file__).resolve().parent / "static" / "fonts"

FONT_MAP = {
    "Arial": FONTS_DIR / "arial.ttf",
    "Arial Bold": FONTS_DIR / "arialbd.ttf",
    "Arial Black": FONTS_DIR / "ariblk.ttf",
    "Impact": FONTS_DIR / "impact.ttf",
}


def probe_video(video_path: str | Path) -> Dict[str, Any]:
    """Inspect video file metadata using ffprobe."""
    p = Path(video_path)
    if not p.exists():
        raise FileNotFoundError(f"Video file not found: {p}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name:format=duration,size",
        "-of", "json",
        str(p),
    ]
    try:
        # A timeout matters here: without one, a wedged ffprobe hangs the
        # request (and any job) forever.
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0] if data.get("streams") else {}
        fmt = data.get("format", {})

        # Parse duration
        duration = 0.0
        if "duration" in stream and stream["duration"] not in (None, "N/A"):
            duration = float(stream["duration"])
        elif "duration" in fmt and fmt["duration"] not in (None, "N/A"):
            duration = float(fmt["duration"])

        # Parse fps
        fps = 30.0
        r_fps = stream.get("r_frame_rate", "30/1")
        if "/" in r_fps:
            num, den = r_fps.split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)

        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration": round(duration, 2),
            "fps": fps,
            "codec": stream.get("codec_name", "unknown"),
            "size_bytes": int(fmt.get("size", p.stat().st_size)),
        }
    except Exception as e:
        print(f"[WARN] ffprobe failed: {e}")
        return {
            "width": 1080,
            "height": 1920,
            "duration": 0.0,
            "fps": 30.0,
            "codec": "unknown",
            "size_bytes": p.stat().st_size,
        }


def escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    # FFmpeg drawtext requires escaping \, :, ', %, [, ]
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def build_filter_chain(
    width: int,
    height: int,
    crop: Optional[Dict[str, Any]] = None,
    color_grade: Optional[Dict[str, Any]] = None,
    mask: Optional[Dict[str, Any]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, int, int]:
    """
    Builds the complex filter string for:
    Crop -> Color grading/Sharpening -> Mask Blur -> Text layers.
    Returns (filter_complex_string, final_w, final_h).
    """
    # 1. Calculate Crop
    if crop and crop.get("enabled", True):
        cw = int(crop.get("width", width))
        ch = int(crop.get("height", height))
        cx = int(crop.get("x", 0))
        cy = int(crop.get("y", 0))

        # Clamp and make even
        cw = max(2, min(width - cx, cw))
        ch = max(2, min(height - cy, ch))
        cw = cw - (cw % 2)
        ch = ch - (ch % 2)
        cx = max(0, min(width - cw, cx))
        cy = max(0, min(height - ch, cy))
    else:
        cw = width - (width % 2)
        ch = height - (height % 2)
        cx = 0
        cy = 0

    current_w, current_h = cw, ch
    filter_stages: List[str] = []

    # Start with initial crop
    filter_stages.append(f"crop={cw}:{ch}:{cx}:{cy}")

    # 2. Color Grading & Sharpening
    cg = color_grade or {}
    sharpen = float(cg.get("sharpen", 0.0))  # 0.0 to 2.5
    brightness = float(cg.get("brightness", 0.0))  # -1.0 to 1.0 (default 0.0)
    contrast = float(cg.get("contrast", 1.0))  # 0.1 to 2.0 (default 1.0)
    saturation = float(cg.get("saturation", 1.0))  # 0.0 to 3.0 (default 1.0)
    temperature = float(cg.get("temperature", 0.0))  # -0.5 (cool) to 0.5 (warm)

    # Apply unsharp filter if sharpen > 0
    if sharpen > 0.01:
        # luma_amount: 0.0 to 2.5
        la = min(2.5, max(0.0, sharpen))
        ca = la * 0.4
        filter_stages.append(f"unsharp=lx=5:ly=5:la={la:.2f}:cx=5:cy=5:ca={ca:.2f}")

    # Apply eq filter if brightness, contrast, or saturation differ from identity
    if abs(brightness) > 0.001 or abs(contrast - 1.0) > 0.001 or abs(saturation - 1.0) > 0.001:
        b_val = max(-1.0, min(1.0, brightness))
        c_val = max(0.1, min(2.5, contrast))
        s_val = max(0.0, min(3.0, saturation))
        filter_stages.append(f"eq=brightness={b_val:.3f}:contrast={c_val:.3f}:saturation={s_val:.3f}")

    # Apply temperature / colorbalance if non-zero
    if abs(temperature) > 0.01:
        # warmth > 0: red positive, blue negative
        temp_val = max(-0.5, min(0.5, temperature))
        rs = temp_val * 0.6
        bs = -temp_val * 0.6
        filter_stages.append(f"colorbalance=rs={rs:.3f}:bs={bs:.3f}")

    # Combine the linear pre-filters
    combined_linear = ",".join(filter_stages)

    # 3. Mask Blur
    # If mask is enabled, we split, crop sub-region, blur, and overlay back
    mask_chain = ""
    last_v_tag = "[v_cg]"
    complex_graph = f"[0:v]{combined_linear}{last_v_tag}"

    if mask and mask.get("enabled", False):
        mw = int(mask.get("width", 160))
        mh = int(mask.get("height", 80))
        mx = int(mask.get("x", 50))
        my = int(mask.get("y", 50))
        blur_radius = int(mask.get("blur", 20))  # 5 to 50

        # Clamp mask coordinates within cropped canvas
        mw = max(4, min(current_w, mw))
        mh = max(4, min(current_h, mh))
        mw = mw - (mw % 2)
        mh = mh - (mh % 2)
        mx = max(0, min(current_w - mw, mx))
        my = max(0, min(current_h - mh, my))

        complex_graph += (
            f";{last_v_tag}split=2[v_base][v_to_blur];"
            f"[v_to_blur]crop={mw}:{mh}:{mx}:{my},"
            f"boxblur=luma_radius={blur_radius}:luma_power=2[v_blurred];"
            f"[v_base][v_blurred]overlay={mx}:{my}[v_masked]"
        )
        last_v_tag = "[v_masked]"

    # 4. Text Layers
    if text_layers:
        text_filters = []
        for idx, layer in enumerate(text_layers):
            if not layer.get("text", "").strip():
                continue
            txt = escape_drawtext(layer.get("text", "").strip())
            font_family = layer.get("font_family", "Arial Bold")
            font_path = FONT_MAP.get(font_family, FONT_MAP["Arial Bold"])
            # Format path for FFmpeg (escape colons and backslashes)
            font_path_str = str(font_path).replace("\\", "/").replace(":", "\\:")

            font_size = int(layer.get("font_size", 36))
            font_color = layer.get("color", "#FFFFFF").replace("#", "")
            stroke_w = int(layer.get("stroke_width", 2))
            stroke_color = layer.get("stroke_color", "#000000").replace("#", "")

            # Position
            tx = int(layer.get("x", 50))
            ty = int(layer.get("y", 50))

            dt_filter = (
                f"drawtext=fontfile='{font_path_str}':text='{txt}':"
                f"fontsize={font_size}:fontcolor=0x{font_color}:"
                f"x={tx}:y={ty}"
            )
            if stroke_w > 0:
                dt_filter += f":borderw={stroke_w}:bordercolor=0x{stroke_color}"

            if layer.get("bg_enabled", False):
                bg_col = layer.get("bg_color", "#000000").replace("#", "")
                bg_alpha = float(layer.get("bg_opacity", 0.6))
                dt_filter += f":box=1:boxcolor=0x{bg_col}@{bg_alpha:.2f}:boxborderw=8"

            text_filters.append(dt_filter)

        if text_filters:
            dt_joined = ",".join(text_filters)
            complex_graph += f";{last_v_tag}{dt_joined}[v_out]"
            last_v_tag = "[v_out]"

    # If last tag is not [v_out], map it cleanly
    if last_v_tag != "[v_out]":
        complex_graph += f";{last_v_tag}copy[v_out]"

    return complex_graph, current_w, current_h


def render_edit(
    input_video: str | Path,
    output_path: str | Path,
    *,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    crop: Optional[Dict[str, Any]] = None,
    color_grade: Optional[Dict[str, Any]] = None,
    mask: Optional[Dict[str, Any]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Executes FFmpeg rendering of all user edits:
    Trim -> Crop -> Color Grade / Sharpen -> Blur Mask -> Text Overlays.
    Outputs a clean H.264 video.
    """
    in_p = Path(input_video)
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    info = probe_video(in_p)
    width = info["width"]
    height = info["height"]
    total_dur = info["duration"]

    filter_complex, fw, fh = build_filter_chain(
        width=width,
        height=height,
        crop=crop,
        color_grade=color_grade,
        mask=mask,
        text_layers=text_layers,
    )

    cmd = ["ffmpeg", "-y"]

    # Precision trimming
    if trim_start > 0.05:
        cmd.extend(["-ss", f"{trim_start:.3f}"])

    cmd.extend(["-i", str(in_p)])

    if trim_end is not None and trim_end > trim_start:
        dur = trim_end - trim_start
        cmd.extend(["-t", f"{dur:.3f}"])

    # Filter complex
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_p),
    ])

    print(f"[FFmpeg] Running command:\n{' '.join(cmd)}")
    t0 = time.time()
    # Duration-scaled cap so a wedged ffmpeg can never hang the request forever.
    timeout = max(600.0, total_dur * 30) if total_dur > 0 else 1800.0
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[ERR] FFmpeg render timed out after {timeout:.0f}s")
        return False
    if res.returncode != 0:
        print(f"[ERR] FFmpeg render failed:\n{res.stderr[-1000:]}")
        return False

    print(f"[OK] Render complete in {time.time() - t0:.2f}s -> {out_p}")
    return True


def execute_full_pipeline(
    input_video: str | Path,
    output_dir: str | Path,
    *,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    crop: Optional[Dict[str, Any]] = None,
    color_grade: Optional[Dict[str, Any]] = None,
    mask: Optional[Dict[str, Any]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
    apply_hashing: bool = True,
    hashing_profile: str = "BALANCED",
    seed: Optional[int] = None,
    pad_bytes: bool = True,
    on_stage: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Unified master pipeline:
    1. Reads source video.
    2. Renders custom user edits (crop, trim, sharpen, color, mask, text) to temp file.
    3. If apply_hashing is True, runs v7_pipeline.stage1.process_video(...) on the edited video.
    4. Verifies SHA-256 and gathers output metrics.

    `on_stage` receives short human-readable progress messages for the UI.
    """

    def _stage(message: str) -> None:
        if on_stage is not None:
            try:
                on_stage(message)
            except Exception:
                pass

    in_p = Path(input_video)
    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)

    if not in_p.exists():
        return {"success": False, "error": f"Source video not found: {in_p.name}"}

    # Hashing was explicitly requested but the engine never loaded. Emitting an
    # unhashed file here would be a silent and dangerous failure, so refuse.
    if apply_hashing and v7_process_video is None:
        return {
            "success": False,
            "engine_available": False,
            "error": (
                "Content hashing engine unavailable - the video was NOT hashed. "
                f"Reason: {PIPELINE_ERROR or 'v7_pipeline failed to import'}. "
                "Fix it with:  pip install -r requirements.txt"
            ),
        }

    stem = _clean_stem(in_p.stem)
    ts = time.strftime("%Y%m%d_%H%M%S")
    # Intermediate render goes to scratch space, never into the outputs folder.
    temp_edited = work_dir() / f"{stem}_edit_{ts}.mp4"

    # Compute source SHA-256
    source_hash = ""
    try:
        if sha256_file:
            source_hash = sha256_file(in_p)
    except Exception:
        pass

    final_output_file: Optional[Path] = None

    try:
        # Step 1: Render the user's edits
        _stage("Rendering edits: crop, colour, mask and text overlays...")
        render_ok = render_edit(
            in_p,
            temp_edited,
            trim_start=trim_start,
            trim_end=trim_end,
            crop=crop,
            color_grade=color_grade,
            mask=mask,
            text_layers=text_layers,
        )

        if not render_ok or not temp_edited.exists():
            return {
                "success": False,
                "error": "Video rendering failed during editing stage.",
            }

        # Step 2: Content hashing pipeline
        if apply_hashing:
            _stage(f"Running v7 content hashing ({hashing_profile})...")
            print(f"[Pipeline] Passing edited video to v7_pipeline with profile: {hashing_profile}")
            hashing_out = v7_process_video(
                temp_edited,
                out_d,
                profile=hashing_profile,
                seed=seed,
                pad=pad_bytes,
                verify_hash=True,
                name_hint=stem,
            )

            if not hashing_out or not Path(hashing_out).exists():
                return {
                    "success": False,
                    "error": f"v7_pipeline processing failed for profile '{hashing_profile}'.",
                }
            final_output_file = Path(hashing_out)
            _stage("Verifying the hashed output...")
        else:
            final_output_file = out_d / f"{stem}_edited_{ts}.mp4"
            shutil.move(str(temp_edited), str(final_output_file))
    finally:
        # The intermediate render is never a deliverable, however we exit.
        try:
            if temp_edited.exists():
                temp_edited.unlink()
        except Exception:
            pass

    # Output inspection
    final_hash = ""
    try:
        if sha256_file and final_output_file.exists():
            final_hash = sha256_file(final_output_file)
    except Exception:
        pass

    out_info = probe_video(final_output_file)

    return {
        "success": True,
        "file_name": final_output_file.name,
        "file_path": str(final_output_file),
        "source_hash": source_hash,
        "output_hash": final_hash,
        "hash_changed": bool(source_hash) and source_hash != final_hash,
        "duration": out_info["duration"],
        "width": out_info["width"],
        "height": out_info["height"],
        "size_mb": round(final_output_file.stat().st_size / (1024 * 1024), 2),
        "hashing_applied": bool(apply_hashing),
        "profile_used": hashing_profile if apply_hashing else "NONE",
        "engine_available": PIPELINE_AVAILABLE,
    }
