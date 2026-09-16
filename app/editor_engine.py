from __future__ import annotations

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
    """Can the optional Stage 1.5 (AI) pass actually run in this interpreter?"""
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

# Emoji / symbol glyphs do not exist in the bundled Arial/Impact fonts, so a
# caption with emoji would render hollow boxes. When a layer contains
# non-Latin glyphs we swap its fontfile to the OS emoji font if one exists.
EMOJI_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/segoeuiemoji.ttf"),       # Windows 10/11
    Path("C:/Windows/Fonts/seguiemj.ttf"),           # older Windows name
    Path("/System/Library/Fonts/Apple Color Emoji.ttc"),  # macOS
    Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
    Path("/usr/share/fonts/noto-color-emoji/NotoColorEmoji.ttf"),
    Path("/usr/share/fonts/google-noto-color-emoji-fonts/NotoColorEmoji.ttf"),
    FONTS_DIR / "NotoColorEmoji.ttf",
]


def _needs_symbol_font(text: str) -> bool:
    return any(ord(c) > 0x2190 for c in text)


def resolve_font(text: str, family: str) -> Path:
    """Pick the font file for a text layer, falling back to an emoji font."""
    base = FONT_MAP.get(family, FONT_MAP["Arial Bold"])
    if _needs_symbol_font(text):
        for candidate in EMOJI_FONT_CANDIDATES:
            if candidate.exists():
                return candidate
        print("[!] Text contains emoji/symbols but no emoji font was found; "
              "glyphs may render as boxes.")
    return base


def probe_video(video_path: str | Path) -> Dict[str, Any]:
    """Inspect video file metadata using ffprobe.

    Raises on failure. Returning made-up dimensions here used to poison every
    downstream crop calculation, so a probe failure must be loud, not silent.
    """
    p = Path(video_path)
    if not p.exists():
        raise FileNotFoundError(f"Video file not found: {p}")

    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,duration,codec_name:format=duration,size",
        "-of", "json", str(p),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0] if data.get("streams") else {}
        fmt = data.get("format", {})

        duration = 0.0
        if "duration" in stream and stream["duration"] not in (None, "N/A"):
            duration = float(stream["duration"])
        elif "duration" in fmt and fmt["duration"] not in (None, "N/A"):
            duration = float(fmt["duration"])

        fps = 30.0
        r_fps = stream.get("r_frame_rate", "30/1")
        if "/" in r_fps:
            num, den = r_fps.split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)

        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        if width <= 0 or height <= 0:
            raise ValueError("ffprobe reported no usable video dimensions")

        return {
            "width": width,
            "height": height,
            "duration": round(duration, 2),
            "fps": fps,
            "codec": stream.get("codec_name", "unknown"),
            "size_bytes": int(fmt.get("size", p.stat().st_size)),
        }
    except Exception as e:
        raise RuntimeError(f"Could not probe '{p.name}': {e}") from e


# ==========================================================================
# Export canvas - the fix for "my 9:16 crop exports at a random resolution"
# ==========================================================================
EXPORT_CANVASES: Dict[str, Dict[str, Tuple[int, int]]] = {
    "9:16": {"1080p": (1080, 1920), "720p": (720, 1280)},
    "4:5": {"1080p": (1080, 1350), "720p": (720, 900)},
    "1:1": {"1080p": (1080, 1080), "720p": (720, 720)},
    "4:3": {"1080p": (1440, 1080), "720p": (960, 720)},
    "16:9": {"1080p": (1920, 1080), "720p": (1280, 720)},
}

ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "9:16": (9, 16),
    "4:5": (4, 5),
    "1:1": (1, 1),
    "4:3": (4, 3),
    "16:9": (16, 9),
}

EXPORT_RESOLUTIONS = ("1080p", "720p", "source")


def _even(v: float) -> int:
    v = max(2, int(round(v)))
    return v - (v % 2)


def resolve_export_canvas(
    crop_w: int,
    crop_h: int,
    resolution: str = "1080p",
    aspect: str = "auto",
) -> Tuple[int, int]:
    """Map a user crop to the exact export canvas.

    aspect "auto" buckets the crop's own aspect to the nearest platform ratio;
    an explicit aspect ("9:16" etc.) forces that canvas - the user's "apply
    9:16 to my whole canvas" control.
    "source" keeps the crop's own even dimensions (no scaling at all), unless
    an explicit aspect is set, in which case the smallest canvas of that
    ratio covering the crop is used.
    """
    res = (resolution or "1080p").lower()
    aspect = (aspect or "auto").strip()

    if res == "source":
        if aspect in ASPECT_RATIOS:
            rw, rh = ASPECT_RATIOS[aspect]
            r2 = rw / rh
            if (crop_w / max(1, crop_h)) > r2:
                return (_even(crop_w), _even(crop_w / r2))
            return (_even(crop_h * r2), _even(crop_h))
        return (_even(crop_w), _even(crop_h))

    if res not in ("1080p", "720p"):
        res = "1080p"
    if aspect in EXPORT_CANVASES:
        return EXPORT_CANVASES[aspect][res]

    r = crop_w / max(1, crop_h)
    if r < 0.65:
        bucket = "9:16"
    elif r < 0.90:
        bucket = "4:5"
    elif r < 1.15:
        bucket = "1:1"
    elif r < 1.50:
        bucket = "4:3"
    else:
        bucket = "16:9"
    return EXPORT_CANVASES[bucket][res]


def escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter (\\, :, ', %, [, ])."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ==========================================================================
# Colour grading - full CapCut-style adjust suite
# ==========================================================================
def _color_filters(cg: Optional[Dict[str, Any]]) -> List[str]:
    """Build the ordered colour/detail filter list.

    Controls (all optional, identity by default):
      sharpen 0..2.5 | brightness -1..1 | contrast 0.1..2.5 | saturation 0..3
      exposure -1..1 (gamma) | highlights -1..1 | shadows -1..1 (colorlevels)
      temperature -0.5..0.5 | tint -1..1 (colorbalance)
      fade 0..1 (curves) | grain 0..1 (noise) | vignette 0..1
    """
    cg = cg or {}
    filters: List[str] = []

    sharpen = _clip(float(cg.get("sharpen", 0.0)), 0.0, 2.5)
    if sharpen > 0.01:
        ca = sharpen * 0.4
        filters.append(f"unsharp=lx=5:ly=5:la={sharpen:.2f}:cx=5:cy=5:ca={ca:.2f}")

    shadows = _clip(float(cg.get("shadows", 0.0)), -1.0, 1.0)
    highlights = _clip(float(cg.get("highlights", 0.0)), -1.0, 1.0)
    if abs(shadows) > 0.01 or abs(highlights) > 0.01:
        rimin = -0.22 * shadows
        rimax = 1.0 - 0.25 * highlights if highlights > 0 else 1.0
        romax = 1.0 if highlights >= 0 else max(0.45, 1.0 + 0.25 * highlights)
        rimin = _clip(rimin, -0.5, 0.5)
        rimax = _clip(rimax, 0.55, 1.0)
        filters.append(
            f"colorlevels=rimin={rimin:.3f}:gimin={rimin:.3f}:bimin={rimin:.3f}"
            f":rimax={rimax:.3f}:gimax={rimax:.3f}:bimax={rimax:.3f}"
            f":romax={romax:.3f}:gomax={romax:.3f}:bomax={romax:.3f}"
        )

    brightness = _clip(float(cg.get("brightness", 0.0)), -1.0, 1.0)
    contrast = _clip(float(cg.get("contrast", 1.0)), 0.1, 2.5)
    saturation = _clip(float(cg.get("saturation", 1.0)), 0.0, 3.0)
    exposure = _clip(float(cg.get("exposure", 0.0)), -1.0, 1.0)
    gamma = _clip(2.0 ** exposure, 0.5, 2.0)
    if (
        abs(brightness) > 0.001
        or abs(contrast - 1.0) > 0.001
        or abs(saturation - 1.0) > 0.001
        or abs(exposure) > 0.01
    ):
        filters.append(
            f"eq=brightness={brightness:.3f}:contrast={contrast:.3f}"
            f":saturation={saturation:.3f}:gamma={gamma:.3f}"
        )

    temperature = _clip(float(cg.get("temperature", 0.0)), -0.5, 0.5)
    tint = _clip(float(cg.get("tint", 0.0)), -1.0, 1.0)
    if abs(temperature) > 0.01 or abs(tint) > 0.01:
        rs, rm, rh = temperature * 0.30, temperature * 0.34, temperature * 0.22
        bs, bm, bh = -rs, -rm, -rh
        gs, gm, gh = tint * 0.16, tint * 0.30, tint * 0.14
        filters.append(
            f"colorbalance=rs={rs:.3f}:rm={rm:.3f}:rh={rh:.3f}"
            f":bs={bs:.3f}:bm={bm:.3f}:bh={bh:.3f}"
            f":gs={gs:.3f}:gm={gm:.3f}:gh={gh:.3f}"
        )

    fade = _clip(float(cg.get("fade", 0.0)), 0.0, 1.0)
    if fade > 0.01:
        y0 = 0.16 * fade
        y2 = 1.0 - 0.08 * fade
        filters.append(f"curves=master='0/{y0:.3f} 0.5/0.5 1/{y2:.3f}'")

    grain = _clip(float(cg.get("grain", 0.0)), 0.0, 1.0)
    if grain > 0.01:
        strength = max(1, int(round(grain * 28)))
        filters.append(f"noise=alls={strength}:allf=t+u")

    vignette = _clip(float(cg.get("vignette", 0.0)), 0.0, 1.0)
    if vignette > 0.01:
        angle = 1.5708 - vignette * 1.1708  # 1 -> 0.40 rad (strong)
        filters.append(f"vignette=angle={angle:.4f}:mode=forward")

    return filters


# ==========================================================================
# Mask chains - multiple regions, blur or pixelate
# ==========================================================================
def _mask_graph(
    masks: Optional[List[Dict[str, Any]]],
    frame_w: int,
    frame_h: int,
    in_tag: str,
) -> Tuple[str, str]:
    """Chain any number of blur/pixelate masks. Returns (graph, out_tag)."""
    active = [m for m in (masks or []) if m and m.get("enabled", True)]
    graph = ""
    last = in_tag
    for idx, m in enumerate(active):
        mw = int(m.get("width", 160))
        mh = int(m.get("height", 80))
        mx = int(m.get("x", 50))
        my = int(m.get("y", 50))
        intensity = int(m.get("blur", 20))  # blur radius OR pixel block size
        mode = str(m.get("mode", "blur")).lower()

        mw = max(4, min(frame_w, mw))
        mh = max(4, min(frame_h, mh))
        mw -= mw % 2
        mh -= mh % 2
        mx = max(0, min(frame_w - mw, mx))
        my = max(0, min(frame_h - mh, my))

        if mode == "pixelate":
            block = max(4, min(64, intensity))
            dw = max(2, mw // block)
            dh = max(2, mh // block)
            effect = (
                f"crop={mw}:{mh}:{mx}:{my},"
                f"scale={dw}:{dh}:flags=neighbor,"
                f"scale={mw}:{mh}:flags=neighbor"
            )
        else:
            radius = max(2, min(50, intensity))
            effect = (
                f"crop={mw}:{mh}:{mx}:{my},"
                f"boxblur=luma_radius={radius}:luma_power=2"
            )

        graph += (
            f";{last}split=2[m{idx}_base][m{idx}_src];"
            f"[m{idx}_src]{effect}[m{idx}_fx];"
            f"[m{idx}_base][m{idx}_fx]overlay={mx}:{my}[m{idx}_out]"
        )
        last = f"[m{idx}_out]"

    return graph, last


# ==========================================================================
# Text layers - multi-line, per-layer timing, emoji fallback
# ==========================================================================
def _text_filters(
    text_layers: Optional[List[Dict[str, Any]]],
    frame_w: int,
    frame_h: int,
) -> List[str]:
    filters: List[str] = []
    for layer in text_layers or []:
        raw = (layer.get("text") or "").strip()
        if not raw:
            continue

        font_family = layer.get("font_family", "Arial Bold")
        font_path = resolve_font(raw, font_family)
        font_path_str = str(font_path).replace("\\", "/").replace(":", "\\:")

        font_size = max(8, int(layer.get("font_size", 36)))
        font_color = str(layer.get("color", "#FFFFFF")).replace("#", "")
        stroke_w = max(0, int(layer.get("stroke_width", 2)))
        stroke_color = str(layer.get("stroke_color", "#000000")).replace("#", "")

        tx = max(0, min(frame_w - 8, int(layer.get("x", 50))))
        ty = max(0, min(frame_h - 8, int(layer.get("y", 50))))

        enable = ""
        start = layer.get("start")
        end = layer.get("end")
        if start is not None or end is not None:
            s = float(start) if start is not None else 0.0
            if end is not None and float(end) > s:
                enable = f":enable='between(t,{s:.3f},{float(end):.3f})'"
            elif s > 0:
                enable = f":enable='gte(t,{s:.3f})'"

        lines = raw.splitlines() or [raw]
        line_h = int(round(font_size * 1.28))
        for li, line in enumerate(lines):
            if not line.strip():
                continue
            txt = escape_drawtext(line.strip())
            y = ty + li * line_h

            dt = (
                f"drawtext=fontfile='{font_path_str}':text='{txt}':"
                f"fontsize={font_size}:fontcolor=0x{font_color}:"
                f"x={tx}:y={y}"
            )
            if stroke_w > 0:
                dt += f":borderw={stroke_w}:bordercolor=0x{stroke_color}"
            if layer.get("bg_enabled", False):
                bg_col = str(layer.get("bg_color", "#000000")).replace("#", "")
                bg_alpha = _clip(float(layer.get("bg_opacity", 0.6)), 0.0, 1.0)
                dt += f":box=1:boxcolor=0x{bg_col}@{bg_alpha:.2f}:boxborderw=8"
            dt += enable
            filters.append(dt)

    return filters


def build_filter_chain(
    width: int,
    height: int,
    crop: Optional[Dict[str, Any]] = None,
    color_grade: Optional[Dict[str, Any]] = None,
    masks: Optional[List[Dict[str, Any]]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
    export: Optional[Dict[str, Any]] = None,
) -> Tuple[str, int, int]:
    """
    Builds the complex filter graph:
      Crop -> Canvas fit (exact export size) -> Colour suite -> Masks -> Text.
    Returns (filter_complex_string, final_w, final_h).

    Canvas fit modes (export.fit):
      "cover"   - CapCut "Fill": scale to cover the canvas, centre-crop excess.
      "contain" - CapCut "Fit": scale to fit inside the canvas and pad with a
                  blurred copy of the frame (blurred bars, no content lost).
    Mask and text coordinates arrive in CROP space; they are scaled by the
    same factor the content frame was, so the preview matches the export.
    """
    # 1. Crop rectangle (clamped, even)
    if crop and crop.get("enabled", True):
        cw = int(crop.get("width", width))
        ch = int(crop.get("height", height))
        cx = int(crop.get("x", 0))
        cy = int(crop.get("y", 0))

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

    # 2. Exact export canvas
    resolution = (export or {}).get("resolution", "1080p")
    aspect = (export or {}).get("aspect", "auto")
    fit = str((export or {}).get("fit", "cover")).lower()
    canvas_w, canvas_h = resolve_export_canvas(cw, ch, resolution, aspect)

    needs_canvas = (canvas_w, canvas_h) != (cw, ch)
    use_contain = fit == "contain" and needs_canvas

    if use_contain:
        r = min(canvas_w / cw, canvas_h / ch)
        fg_w = _even(cw * r)
        fg_h = _even(ch * r)
        sx = fg_w / cw
        sy = fg_h / ch
    else:
        fg_w, fg_h = canvas_w, canvas_h
        sx = canvas_w / cw if cw else 1.0
        sy = canvas_h / ch if ch else 1.0

    def _scale_mask(m: Dict[str, Any]) -> Dict[str, Any]:
        scaled = dict(m)
        scaled["x"] = int(round(scaled.get("x", 0) * sx))
        scaled["y"] = int(round(scaled.get("y", 0) * sy))
        scaled["width"] = max(4, int(round(scaled.get("width", 160) * sx)))
        scaled["height"] = max(4, int(round(scaled.get("height", 80) * sy)))
        return scaled

    def _scale_text(layer: Dict[str, Any]) -> Dict[str, Any]:
        scaled = dict(layer)
        scaled["x"] = int(round(scaled.get("x", 0) * sx))
        scaled["y"] = int(round(scaled.get("y", 0) * sy))
        scaled["font_size"] = max(8, int(round(scaled.get("font_size", 36) * sy)))
        scaled["stroke_width"] = max(0, int(round(scaled.get("stroke_width", 0) * sy)))
        return scaled

    scaled_masks = [_scale_mask(m) for m in (masks or [])]
    scaled_text = [_scale_text(t) for t in (text_layers or [])]
    color_filters = _color_filters(color_grade)

    if use_contain:
        # --- Fit (blurred bars): grade+overlay the fitted foreground, then
        # pad it onto a blurred cover copy of itself.
        fg_linear = f"crop={cw}:{ch}:{cx}:{cy},scale={fg_w}:{fg_h}:flags=bicubic"
        if color_filters:
            fg_linear += "," + ",".join(color_filters)

        graph = f"[0:v]{fg_linear},split=2[fg_m][fg_bg];"
        graph += (
            f"[fg_bg]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=bicubic,"
            f"crop={canvas_w}:{canvas_h},boxblur=luma_radius=24:luma_power=2[bg_canvas]"
        )
        mask_graph, last = _mask_graph(scaled_masks, fg_w, fg_h, "[fg_m]")
        graph += mask_graph
        text_filters = _text_filters(scaled_text, fg_w, fg_h)
        if text_filters:
            graph += f";{last}{','.join(text_filters)}[fg_fin]"
            last = "[fg_fin]"
        graph += f";[bg_canvas]{last}overlay=(W-w)/2:(H-h)/2[v_out]"
        return graph, canvas_w, canvas_h

    # --- Fill (cover) or exact-size path
    filter_stages: List[str] = [f"crop={cw}:{ch}:{cx}:{cy}"]
    if needs_canvas:
        filter_stages.append(
            f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=bicubic"
        )
        filter_stages.append(f"crop={canvas_w}:{canvas_h}")
    filter_stages.extend(color_filters)

    combined_linear = ",".join(filter_stages)

    last_v_tag = "[v_cg]"
    complex_graph = f"[0:v]{combined_linear}{last_v_tag}"
    mask_graph, last_v_tag = _mask_graph(scaled_masks, canvas_w, canvas_h, last_v_tag)
    complex_graph += mask_graph

    text_filters = _text_filters(scaled_text, canvas_w, canvas_h)
    if text_filters:
        complex_graph += f";{last_v_tag}{','.join(text_filters)}[v_out]"
        last_v_tag = "[v_out]"

    if last_v_tag != "[v_out]":
        complex_graph += f";{last_v_tag}copy[v_out]"

    return complex_graph, canvas_w, canvas_h


def render_edit(
    input_video: str | Path,
    output_path: str | Path,
    *,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    crop: Optional[Dict[str, Any]] = None,
    color_grade: Optional[Dict[str, Any]] = None,
    masks: Optional[List[Dict[str, Any]]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
    export: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Executes FFmpeg rendering of all user edits at the exact export canvas.
    Prints `RENDER_PROGRESS <pct>` lines so callers can show real progress.
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
        masks=masks,
        text_layers=text_layers,
        export=export,
    )
    print(f"[ ] Editor render target: {fw}x{fh}")

    cmd = ["ffmpeg", "-y", "-nostats", "-loglevel", "error", "-progress", "pipe:1"]

    if trim_start > 0.05:
        cmd.extend(["-ss", f"{trim_start:.3f}"])

    cmd.extend(["-i", str(in_p)])

    eff_dur = total_dur
    if trim_end is not None and trim_end > trim_start:
        eff_dur = trim_end - trim_start
        cmd.extend(["-t", f"{eff_dur:.3f}"])

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

    print(f"[FFmpeg] Running editor render ({fw}x{fh})...")
    t0 = time.time()
    timeout = max(600.0, total_dur * 30) if total_dur > 0 else 1800.0

    proc = None
    err_tail: List[str] = []
    last_pct = -1
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        deadline = time.monotonic() + timeout
        assert proc.stdout is not None
        for line in proc.stdout:
            if time.monotonic() > deadline:
                proc.kill()
                print(f"[ERR] FFmpeg render timed out after {timeout:.0f}s")
                return False
            line_s = line.strip()
            if line_s.startswith("out_time_us=") and eff_dur > 0:
                try:
                    out_us = int(line_s.split("=", 1)[1])
                    pct = min(100, int(out_us / 1_000_000 / eff_dur * 100))
                    if pct != last_pct:
                        last_pct = pct
                        print(f"RENDER_PROGRESS {pct}", flush=True)
                except (ValueError, IndexError):
                    pass
            elif line_s == "progress=end":
                break
            elif line_s:
                err_tail.append(line_s)
                del err_tail[:-40]
        proc.wait(timeout=60)
    except Exception as e:
        if proc is not None and proc.poll() is None:
            proc.kill()
        print(f"[ERR] FFmpeg render crashed: {e}")
        return False

    if proc.returncode != 0:
        print(f"[ERR] FFmpeg render failed (code {proc.returncode}):")
        for ln in err_tail[-12:]:
            print(f"  {ln}")
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
    masks: Optional[List[Dict[str, Any]]] = None,
    text_layers: Optional[List[Dict[str, Any]]] = None,
    export: Optional[Dict[str, Any]] = None,
    apply_hashing: bool = True,
    hashing_profile: str = "BALANCED",
    seed: Optional[int] = None,
    pad_bytes: bool = True,
    on_stage: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Unified master pipeline: render edits at the exact export canvas, then
    optionally run the V7 hash with rescale disabled so the hashed output
    keeps the exact export dimensions.

    `on_stage` receives structured `[STAGE k/N] label` markers for the UI.
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

    # Legacy single-mask callers still work.
    if masks is None and mask is not None:
        masks = [mask]

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
    temp_edited = work_dir() / f"{stem}_edit_{ts}.mp4"

    source_hash = ""
    try:
        if sha256_file:
            source_hash = sha256_file(in_p)
    except Exception:
        pass

    total_stages = 3 if apply_hashing else 2
    final_output_file: Optional[Path] = None

    try:
        _stage(f"[STAGE 1/{total_stages}] Rendering edits - crop, colour, masks, text")
        try:
            render_ok = render_edit(
                in_p,
                temp_edited,
                trim_start=trim_start,
                trim_end=trim_end,
                crop=crop,
                color_grade=color_grade,
                masks=masks,
                text_layers=text_layers,
                export=export,
            )
        except Exception as e:
            return {"success": False, "error": f"Render setup failed: {e}"}

        if not render_ok or not temp_edited.exists():
            return {
                "success": False,
                "error": "Video rendering failed during editing stage.",
            }

        if apply_hashing:
            _stage(f"[STAGE 2/{total_stages}] V7 {hashing_profile} hash encode - anti-detection pass")
            print(f"[Pipeline] Passing edited video to v7_pipeline with profile: {hashing_profile}")
            hashing_out = v7_process_video(
                temp_edited,
                out_d,
                profile=hashing_profile,
                seed=seed,
                pad=pad_bytes,
                verify_hash=True,
                name_hint=stem,
                rescale=False,
            )

            if not hashing_out or not Path(hashing_out).exists():
                return {
                    "success": False,
                    "error": f"v7_pipeline processing failed for profile '{hashing_profile}'.",
                }
            final_output_file = Path(hashing_out)
            _stage(f"[STAGE {total_stages}/{total_stages}] Finalizing - validate, pad, verify hash")
        else:
            _stage(f"[STAGE {total_stages}/{total_stages}] Packaging export")
            final_output_file = out_d / f"{stem}_edited_{ts}.mp4"
            shutil.move(str(temp_edited), str(final_output_file))
    finally:
        try:
            if temp_edited.exists():
                temp_edited.unlink()
        except Exception:
            pass

    final_hash = ""
    try:
        if sha256_file and final_output_file.exists():
            final_hash = sha256_file(final_output_file)
    except Exception:
        pass

    try:
        out_info = probe_video(final_output_file)
    except Exception as e:
        return {"success": False, "error": f"Output probe failed: {e}"}

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
        "export_resolution": (export or {}).get("resolution", "1080p"),
        "engine_available": PIPELINE_AVAILABLE,
    }
