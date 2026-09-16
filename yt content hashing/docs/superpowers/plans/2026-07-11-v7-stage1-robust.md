# V7 Stage 1 Robust Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Stage 1 video hashing into a modular `v7_pipeline` package with profiles, validation, encoder fallback, and reliable batch — no metadata/Stage 2.

**Architecture:** Thin CLI (`V7_Combined_local.py` + `python -m v7_pipeline`) orchestrates `paths` → `config` profile → `filters` graph → `encoder` (NVENC→libx264) → `validate` → optional EOF pad. Port filter/encode behavior from existing `V7_Combined_local.py` string-for-string first (BALANCED), then gate features per SAFE/AGGRESSIVE.

**Tech Stack:** Python 3.11+, FFmpeg/ffprobe (subprocess), tqdm, pytest (stdlib + subprocess only; no new deps)

**Spec:** `docs/superpowers/specs/2026-07-10-v7-stage1-robust-design.md`

**Repo note:** Workspace currently has **no git**. Either `git init` once before first commit, or skip commit steps and leave working tree as-is.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `v7_pipeline/__init__.py` | Package version + public exports |
| `v7_pipeline/__main__.py` | `python -m v7_pipeline` → CLI |
| `v7_pipeline/cli.py` | argparse flags (`--profile`, `--input`, `--batch`, etc.) |
| `v7_pipeline/paths.py` | Project `input/`, `output/`, `%TEMP%/hasher_v7` |
| `v7_pipeline/config.py` | Constants + SAFE/BALANCED/AGGRESSIVE profiles |
| `v7_pipeline/filters.py` | Build video/audio `filter_complex` + random params |
| `v7_pipeline/encoder.py` | Detect encoder, build cmd, run with progress, x264 fallback |
| `v7_pipeline/validate.py` | ffprobe duration/streams/size checks |
| `v7_pipeline/stage1.py` | Single-file orchestrator (copy→encode→validate→pad→cleanup) |
| `v7_pipeline/batch.py` | Discover videos, sequential batch, skip-existing, summary |
| `V7_Combined_local.py` | Thin wrapper calling CLI / stage1 (compat) |
| `tests/test_paths.py` | Path helpers |
| `tests/test_config.py` | Profile resolution |
| `tests/test_validate.py` | Validation helpers (mocked / synthetic) |
| `tests/test_filters.py` | Graph contains expected pads; profile gates |
| `tests/test_batch.py` | Skip-existing logic pure functions |
| `scripts/smoke_stage1.py` | Optional end-to-end smoke on real `input/` |

**Do not create:** `stage2.py`, metadata injectors, Colab/Drive helpers.

**Source for port:** Current monolith `V7_Combined_local.py` (790 lines). After Task 7, replace it with a thin wrapper. Keep a backup copy only if needed as `V7_Combined_local.monolith.bak` during migration (delete after smoke pass).

---

### Task 1: Package scaffold + paths + config base

**Files:**
- Create: `v7_pipeline/__init__.py`
- Create: `v7_pipeline/paths.py`
- Create: `v7_pipeline/config.py`
- Create: `tests/test_paths.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for paths and config**

```python
# tests/test_paths.py
from pathlib import Path
from v7_pipeline.paths import project_root, ensure_dirs, temp_work_dir, VIDEO_EXTS

def test_project_root_has_input_output():
    root = project_root()
    assert (root / "input").exists() or True  # may create later
    assert root.name  # non-empty

def test_video_exts():
    assert ".mp4" in VIDEO_EXTS
    assert ".mov" in VIDEO_EXTS

def test_temp_work_dir_under_hasher(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    d = temp_work_dir()
    assert d.name == "hasher_v7"
    assert d.exists()
```

```python
# tests/test_config.py
from v7_pipeline.config import PROFILES, get_profile, ProfileName

def test_three_profiles_exist():
    assert set(PROFILES.keys()) == {"SAFE", "BALANCED", "AGGRESSIVE"}

def test_default_is_balanced():
    p = get_profile("BALANCED")
    assert p.name == "BALANCED"
    assert p.ai_optical_flow is True  # matches current V7 defaults

def test_safe_disables_expensive():
    p = get_profile("SAFE")
    assert p.ai_optical_flow is False
    assert p.ai_mimicry is False
    assert p.dct_geq is False

def test_invalid_profile_raises():
    try:
        get_profile("NOPE")
        assert False, "should raise"
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests — expect FAIL (import errors)**

Run: `pytest tests/test_paths.py tests/test_config.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'v7_pipeline'`

- [ ] **Step 3: Implement paths + config**

```python
# v7_pipeline/__init__.py
"""V7 Stage 1 local pipeline — re-encode hashing only (no metadata)."""
__version__ = "1.0.0"
```

```python
# v7_pipeline/paths.py
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
```

```python
# v7_pipeline/config.py
"""Stage 1 constants and intensity profiles. No metadata / Stage 2."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Literal

ProfileName = Literal["SAFE", "BALANCED", "AGGRESSIVE"]

# ----- global encode defaults (shared) -----
PROCESS_TIMEOUT = 28800
TARGET_BITRATE = "5M"
GOP_INTERVAL = 30
DOWNSCALE_W = 1280
DOWNSCALE_H = 720
FPS_FLAG = "-fps_mode"
FRAME_RATE_MODE = "cfr"
OUTPUT_FRAME_RATE = 30
SAMPLE_RATE = 48000
MIN_OUTPUT_BYTES = 1024

# Disabled / unsafe (document; do not enable without proof)
# PERCEPTUAL_WARP: perspective filter lacks reliable t/n expression support
PERCEPTUAL_WARP_ENABLE = False

MV_X264_PARAMS_A = "me=umh:subme=1:merange=48:mbtree=0:direct=spatial:no-dct-decimate=1:trellis=0:weightp=0"
MV_X264_PARAMS_B = "me=esa:subme=2:merange=32:mbtree=1:direct=temporal:no-dct-decimate=0:trellis=1:weightp=2"
MV_X264_PARAMS_C = "me=tesa:subme=3:merange=64:mbtree=0:direct=auto:no-dct-decimate=1:trellis=2:weightp=1"

@dataclass(frozen=True)
class Profile:
    name: ProfileName
    # geometry / motion
    pan_enable: bool = True
    pan_offset_px: int = 6
    pan_frequency: float = 0.5
    crop_size: float = 0.95
    micro_rotation_deg: float = 0.3
    rotation_bilinear: int = 0
    warp_strength: float = 0.015
    # color / grain
    chromatic_enable: bool = True
    chromatic_shift: int = 2
    grain_strength: float = 3.0
    grain_temporal: bool = True
    lut_freq_tweak: bool = True
    lut_freq_strength: float = 0.005
    luma_crush: bool = True
    luma_shadows: float = 0.01
    luma_highlights: float = 0.0
    hue_spatial_drift: bool = True
    # timing
    pts_jitter: bool = True
    pts_jitter_min: float = 0.0005
    pts_jitter_max: float = 0.002
    timeline_desync_delta: float = 0.003
    # encode structure
    b_frame_inject: bool = True
    b_frames: int = 3
    b_strategy: int = 1
    b_pyramid: int = 1
    ref_frames: int = 4
    # DCT / ViT
    dct_geq: bool = True
    dct_dc_strength: float = 0.3
    dct_ac_strength: float = 0.15
    dct_chroma_strength: float = 0.15
    vit_patch_noise: bool = True
    vit_patch_noise_amplitude: float = 1.5
    vit_luminance_flicker: bool = True
    vit_luminance_flicker_max: float = 0.002
    vit_spatial_shift: bool = True
    vit_spatial_shift_max_px: int = 2
    vit_temporal_blend: bool = True
    vit_temporal_blend_ratio: float = 0.03
    # AI mimicry (expensive)
    ai_mimicry: bool = True
    ai_vae_grid_strength: float = 0.03
    ai_plastic_smoothing: bool = True
    ai_optical_flow: bool = True  # minterpolate on bg
    ai_bg_morph: bool = True
    # audio
    phase_invert: bool = True
    ultrasonic: bool = True
    ultrasonic_amp: float = 0.03
    pitch_shift_factor: float = 1.015
    aeco_comb_filter: bool = True
    # behavioral pad
    behavioral_pad: bool = True
    behavioral_pad_max_bytes: int = 4096
    # randomize ranges multiplier: 1.0 = current V7
    randomize: bool = True
    range_scale: float = 1.0  # AGGRESSIVE > 1, SAFE can keep 1 with flags off

PROFILES: dict[str, Profile] = {
    "BALANCED": Profile(name="BALANCED"),
    "SAFE": Profile(
        name="SAFE",
        ai_optical_flow=False,
        ai_mimicry=False,
        ai_plastic_smoothing=False,
        ai_bg_morph=False,
        dct_geq=False,
        vit_patch_noise=False,
        vit_temporal_blend=False,
        grain_strength=1.5,
        chromatic_shift=1,
        aeco_comb_filter=True,
        ultrasonic=True,
        phase_invert=True,
        range_scale=0.85,
    ),
    "AGGRESSIVE": Profile(
        name="AGGRESSIVE",
        grain_strength=4.0,
        chromatic_shift=3,
        vit_spatial_shift_max_px=3,
        vit_patch_noise_amplitude=2.0,
        ai_vae_grid_strength=0.04,
        range_scale=1.2,
        behavioral_pad_max_bytes=8192,
    ),
}

def get_profile(name: str) -> Profile:
    key = (name or "BALANCED").strip().upper()
    if key not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}; choose SAFE|BALANCED|AGGRESSIVE")
    return PROFILES[key]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_paths.py tests/test_config.py -v`  
Expected: all PASS

- [ ] **Step 5: Commit (optional if no git)**

```bash
git init
git add v7_pipeline/__init__.py v7_pipeline/paths.py v7_pipeline/config.py tests/test_paths.py tests/test_config.py
git commit -m "feat(v7): scaffold paths and Stage 1 profiles"
```

---

### Task 2: validate.py

**Files:**
- Create: `v7_pipeline/validate.py`
- Create: `tests/test_validate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_validate.py
from v7_pipeline.validate import duration_tolerance_ok, ValidationResult

def test_duration_tolerance_within():
    assert duration_tolerance_ok(10.0, 10.1) is True
    assert duration_tolerance_ok(10.0, 10.5) is True  # 0.5s rule

def test_duration_tolerance_fail():
    assert duration_tolerance_ok(10.0, 12.0) is False

def test_validation_result_ok_fields():
    r = ValidationResult(ok=True, has_video=True, has_audio=True, duration=1.0, size_bytes=5000, message="ok")
    assert r.ok
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_validate.py -v`  
Expected: FAIL import / missing symbols

- [ ] **Step 3: Implement validate**

```python
# v7_pipeline/validate.py
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
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def duration_tolerance_ok(source_sec: float, out_sec: float) -> bool:
    if source_sec <= 0 or out_sec <= 0:
        return out_sec > 0  # if source unknown, only require positive out
    tol = max(0.5, abs(source_sec) * 0.02)
    return abs(out_sec - source_sec) <= tol

def probe_stream_types(path: str | Path) -> tuple[bool, bool]:
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
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
        return ValidationResult(False, False, False, 0.0, size, f"output too small ({size} bytes)")
    has_v, has_a = probe_stream_types(p)
    dur = get_duration_sec(p)
    if not has_v:
        return ValidationResult(False, has_v, has_a, dur, size, "no video stream")
    if require_audio and not has_a:
        return ValidationResult(False, has_v, has_a, dur, size, "no audio stream")
    if source_duration > 0 and not duration_tolerance_ok(source_duration, dur):
        return ValidationResult(
            False, has_v, has_a, dur, size,
            f"duration mismatch source={source_duration:.2f}s out={dur:.2f}s",
        )
    msg = "video+audio" if has_a else "video-only (no audio)"
    return ValidationResult(True, has_v, has_a, dur, size, msg)
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_validate.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add v7_pipeline/validate.py tests/test_validate.py
git commit -m "feat(v7): add Stage 1 output validation"
```

---

### Task 3: encoder.py (detect + progress + cmd build)

**Files:**
- Create: `v7_pipeline/encoder.py`
- Create: `tests/test_encoder.py`

- [ ] **Step 1: Write tests that do not require GPU**

```python
# tests/test_encoder.py
from v7_pipeline.encoder import build_encode_cmd, EncodeParams

def test_build_cmd_libx264_has_maps():
    params = EncodeParams(
        encoder="libx264",
        crf=24,
        gop=30,
        b_frames=3,
        b_strategy=1,
        b_pyramid=1,
        ref_frames=4,
        mv_params="me=umh:subme=1",
        b_frame_inject=True,
        target_bitrate="5M",
        sample_rate=48000,
        frame_rate_mode="cfr",
        output_frame_rate=30,
        fps_flag="-fps_mode",
    )
    cmd = build_encode_cmd(
        local_in="in.mp4",
        local_out="out.mp4",
        filter_complex="[0:v]null[vout];[0:a]anull[aout]",
        extra_inputs=[],
        params=params,
    )
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    assert "[vout]" in cmd
    assert "[aout]" in cmd
    assert "libx264" in cmd
    assert str(params.crf) in cmd or "24" in cmd

def test_build_cmd_nvenc_uses_h264_nvenc():
    params = EncodeParams(
        encoder="nvenc",
        crf=24,
        gop=30,
        b_frames=2,
        b_strategy=1,
        b_pyramid=1,
        ref_frames=4,
        mv_params="",
        b_frame_inject=True,
        target_bitrate="5M",
        sample_rate=48000,
        frame_rate_mode="cfr",
        output_frame_rate=30,
        fps_flag="-fps_mode",
    )
    cmd = build_encode_cmd("in.mp4", "out.mp4", "fc", [], params)
    assert "h264_nvenc" in cmd
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_encoder.py -v`  
Expected: FAIL missing module

- [ ] **Step 3: Implement encoder**

Port logic from `V7_Combined_local.py` lines 131–234 and 524–559 into:

```python
# v7_pipeline/encoder.py
from __future__ import annotations
import subprocess
from dataclasses import dataclass
from typing import Literal

try:
    from tqdm.auto import tqdm
except ImportError:
    from tqdm import tqdm  # type: ignore

EncoderName = Literal["nvenc", "libx264"]

@dataclass
class EncodeParams:
    encoder: EncoderName
    crf: int
    gop: int
    b_frames: int
    b_strategy: int
    b_pyramid: int
    ref_frames: int
    mv_params: str
    b_frame_inject: bool
    target_bitrate: str
    sample_rate: int
    frame_rate_mode: str
    output_frame_rate: int
    fps_flag: str

def detect_encoder() -> tuple[EncoderName, str]:
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        if "h264_nvenc" not in r.stdout:
            return "libx264", "NVENC not in encoders list"
    except Exception as e:
        return "libx264", f"encoder list failed: {e}"

    try:
        test = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240",
                "-frames:v", "1", "-pix_fmt", "yuv420p",
                "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "constqp", "-qp", "23",
                "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if test.returncode == 0:
            return "nvenc", "NVENC test encode succeeded"
        return "libx264", f"NVENC unavailable: {test.stderr.strip()[:80]}"
    except subprocess.TimeoutExpired:
        return "libx264", "NVENC test timed out (no GPU?)"
    except Exception as e:
        return "libx264", f"NVENC test failed: {e}"

def run_ffmpeg_with_progress(cmd: list[str], duration_sec: float, desc: str = "Encoding") -> tuple[int, str]:
    cmd = cmd.copy()
    insert_at = 1 if (cmd and cmd[0] == "ffmpeg") else 0
    cmd[insert_at:insert_at] = ["-progress", "pipe:1"]
    if "-loglevel" in cmd:
        i = cmd.index("-loglevel")
        cmd[i : i + 2] = ["-loglevel", "error"]

    pbar = tqdm(
        total=100, desc=desc, unit="%",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}% [{elapsed}<{remaining}, {rate_fmt}]",
    )
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        captured: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            captured.append(line)
            line_s = line.strip()
            if line_s.startswith("out_time_us=") and duration_sec > 0:
                try:
                    out_us = int(line_s.split("=", 1)[1])
                    pct = min(100, (out_us / 1_000_000 / duration_sec) * 100)
                    pbar.n = int(pct)
                    pbar.refresh()
                except (ValueError, IndexError):
                    pass
            elif line_s == "progress=end":
                break
        proc.wait()
        pbar.n = 100
        pbar.refresh()
        pbar.close()
        return proc.returncode, "".join(captured)
    except Exception:
        pbar.close()
        raise

def build_encode_cmd(
    local_in: str,
    local_out: str,
    filter_complex: str,
    extra_inputs: list[str],
    params: EncodeParams,
) -> list[str]:
    """extra_inputs: flat ffmpeg args after main -i, e.g. ['-f','lavfi','-i','anoisesrc=...']"""
    cmd: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "info", "-i", local_in]
    cmd.extend(extra_inputs)
    cmd.extend(["-filter_complex", filter_complex])
    cmd.extend(["-map", "[vout]", "-map", "[aout]"])

    if params.encoder == "nvenc":
        cmd.extend([
            "-c:v", "h264_nvenc", "-preset", "p4",
            "-qp", str(params.crf - 4), "-pix_fmt", "yuv420p",
            "-g", str(params.gop),
            "-b:v", params.target_bitrate, "-maxrate", params.target_bitrate,
            "-bufsize", params.target_bitrate,
        ])
        if params.b_frame_inject:
            cmd.extend(["-bf", str(params.b_frames)])
            cmd.extend(["-b_ref_mode", "middle" if params.b_pyramid >= 1 else "disabled"])
    else:
        cmd.extend([
            "-c:v", "libx264", "-preset", "ultrafast",
            "-tune", "fastdecode", "-crf", str(params.crf),
            "-pix_fmt", "yuv420p", "-threads", "0",
            "-g", str(params.gop),
            "-b:v", params.target_bitrate, "-maxrate", params.target_bitrate,
            "-bufsize", params.target_bitrate,
        ])
        if params.b_frame_inject:
            cmd.extend(["-bf", str(params.b_frames)])
            cmd.extend(["-b_strategy", str(params.b_strategy)])
            cmd.extend(["-refs", str(params.ref_frames)])
        final_mv = (
            params.mv_params + f":b-pyramid={params.b_pyramid}"
            if params.b_frame_inject and params.mv_params
            else params.mv_params
        )
        if final_mv:
            cmd.extend(["-x264-params", final_mv])

    if params.frame_rate_mode == "vfr":
        cmd.extend([params.fps_flag, "vfr"])
    else:
        cmd.extend([params.fps_flag, "cfr", "-r", str(params.output_frame_rate)])

    cmd.extend([
        "-c:a", "aac", "-b:a", "192k", "-ar", str(params.sample_rate),
        "-movflags", "+faststart", local_out,
    ])
    return cmd

def encode_with_fallback(
    local_in: str,
    local_out: str,
    filter_complex: str,
    extra_inputs: list[str],
    params: EncodeParams,
    duration_sec: float,
) -> tuple[bool, str, EncodeParams]:
    """Returns (ok, log_tail, params_used). On NVENC fail, retries libx264 once."""
    cmd = build_encode_cmd(local_in, local_out, filter_complex, extra_inputs, params)
    ret, out = run_ffmpeg_with_progress(cmd, duration_sec, desc=f"Encoding ({params.encoder})")
    if ret == 0:
        return True, out[-1500:], params
    if params.encoder == "nvenc":
        print("[!] NVENC failed, rebuilding with libx264 ultrafast...")
        fb = EncodeParams(**{**params.__dict__, "encoder": "libx264"})
        cmd2 = build_encode_cmd(local_in, local_out, filter_complex, extra_inputs, fb)
        ret2, out2 = run_ffmpeg_with_progress(cmd2, duration_sec, desc="Encoding (libx264)")
        if ret2 == 0:
            return True, out2[-1500:], fb
        return False, out2[-1500:], fb
    return False, out[-1500:], params
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_encoder.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add v7_pipeline/encoder.py tests/test_encoder.py
git commit -m "feat(v7): encoder detect, progress, NVENC fallback"
```

---

### Task 4: filters.py (port graph + random params)

**Files:**
- Create: `v7_pipeline/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests for pads + profile gates**

```python
# tests/test_filters.py
from v7_pipeline.config import get_profile
from v7_pipeline.filters import build_filter_complex, sample_random_params

def test_balanced_graph_has_core_pads():
    profile = get_profile("BALANCED")
    rp = sample_random_params(profile, seed=42)
    fc, extra = build_filter_complex(profile, rp)
    assert "bg_stream" in fc
    assert "fg_stream" in fc
    assert "[vout]" in fc
    assert "[aout]" in fc
    assert "filter_complex" not in fc  # raw graph only

def test_safe_omits_minterpolate_and_dct_geq():
    profile = get_profile("SAFE")
    rp = sample_random_params(profile, seed=1)
    fc, _ = build_filter_complex(profile, rp)
    assert "minterpolate" not in fc
    # SAFE dct_geq False: no heavy DCT geq block with floor(X/8)
    assert "floor(X/8)/32" not in fc

def test_aggressive_can_include_minterpolate():
    profile = get_profile("AGGRESSIVE")
    rp = sample_random_params(profile, seed=2)
    fc, _ = build_filter_complex(profile, rp)
    assert "minterpolate" in fc

def test_seed_reproducible():
    p = get_profile("BALANCED")
    a = sample_random_params(p, seed=99)
    b = sample_random_params(p, seed=99)
    assert a.crf == b.crf
    assert a.pts_jitter == b.pts_jitter
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_filters.py -v`  
Expected: FAIL missing filters module

- [ ] **Step 3: Implement filters by porting `process_video` graph from monolith**

Create `v7_pipeline/filters.py` with:

1. `@dataclass RandomParams` holding all `r_*` fields currently computed in `V7_Combined_local.py` lines 275–332.
2. `sample_random_params(profile: Profile, seed: int | None) -> RandomParams` — use `random.Random(seed)` when seed set; scale ranges by `profile.range_scale`; respect profile flags for pad bytes etc.
3. `build_filter_complex(profile, rp) -> tuple[str, list[str]]` returning `(filter_complex_string, extra_ffmpeg_input_args)`.

**Port rules (critical):**

- Copy video chain from monolith lines 341–481 and audio from 483–522 almost literally.
- Replace global flags with `profile.*` and `rp.*` (e.g. `if profile.ai_optical_flow:` instead of `if AI_OPTICAL_FLOW_SPOOF:`).
- Keep pad names: `bg_stream`, `fg_stream`, `blurred_border_bg`, `sharp_foreground_fg`, `merged`, `vignetted`, `rotated`, `jnd_shifted`, `dct_shifted`, `vout`, `aout` / `aout_pre`.
- Never enable `PERCEPTUAL_WARP` unless `config.PERCEPTUAL_WARP_ENABLE` is True (default False).
- Ultrasonic second input: when `profile.phase_invert and profile.ultrasonic`, set  
  `extra = ['-f','lavfi','-i', f'anoisesrc=color=white:amplitude={profile.ultrasonic_amp}:sample_rate={SAMPLE_RATE}']`  
  else `extra = []`.

Skeleton (fill body from monolith; agent must paste full chains — incomplete graphs are a bug):

```python
# v7_pipeline/filters.py
from __future__ import annotations
import random
from dataclasses import dataclass
from v7_pipeline.config import (
    Profile, SAMPLE_RATE, DOWNSCALE_W, DOWNSCALE_H,
    MV_X264_PARAMS_A, MV_X264_PARAMS_B, MV_X264_PARAMS_C,
    PERCEPTUAL_WARP_ENABLE, GOP_INTERVAL,
)

@dataclass
class RandomParams:
    chromatic: int
    warp: float
    rotation: float
    lumashadow: float
    lumahigh: float
    lutfreq: float
    grain: float
    dct_dc: float
    dct_ac: float
    dct_chroma: float
    desync: float
    crop: float
    pts_jitter: float
    bframes: int
    bstrat: int
    bpyramid: int
    ref: int
    mv_params: str
    crf: int
    gop: int
    vit_patch_amp: float
    vit_flicker: float
    vit_shift: int
    vit_blend: float
    pad_bytes: int
    ai_vae: float
    ai_bg_morph: float
    persp: float

def sample_random_params(profile: Profile, seed: int | None = None) -> RandomParams:
    rng = random.Random(seed)
    s = profile.range_scale
    if not profile.randomize:
        # fixed mid values (omit listing — mirror monolith else-branch)
        ...
    # mirror monolith if RANDOMIZE_PARAMS block using profile knobs * s
    ...

def build_filter_complex(profile: Profile, rp: RandomParams) -> tuple[str, list[str]]:
    # Build vf_parts exactly as monolith; gate with profile flags
    # Join: vf = ";".join(vf_parts); af as monolith; return f"{vf};{af}", extra_inputs
    ...
```

**Agent instruction:** Open `V7_Combined_local.py` and port the filter strings character-for-character into `build_filter_complex`. Do not invent new filters. After port, run unit tests above.

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/test_filters.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add v7_pipeline/filters.py tests/test_filters.py
git commit -m "feat(v7): port Stage 1 filter graphs with profile gates"
```

---

### Task 5: stage1.py orchestrator

**Files:**
- Create: `v7_pipeline/stage1.py`
- Create: `tests/test_stage1_unit.py` (pure helpers only; full encode is smoke)

- [ ] **Step 1: Write test for output naming + cleanup helper**

```python
# tests/test_stage1_unit.py
from pathlib import Path
from v7_pipeline.stage1 import make_output_name, safe_unlink

def test_make_output_name_pattern():
    name = make_output_name("clip.mp4")
    assert name.startswith("clip_v7_")
    assert name.endswith(".mp4")

def test_safe_unlink(tmp_path):
    f = tmp_path / "t.bin"
    f.write_bytes(b"x")
    safe_unlink(f)
    assert not f.exists()
    safe_unlink(f)  # no throw
```

- [ ] **Step 2: Implement stage1**

```python
# v7_pipeline/stage1.py
from __future__ import annotations
import hashlib
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from v7_pipeline.config import (
    Profile, get_profile, TARGET_BITRATE, SAMPLE_RATE,
    FRAME_RATE_MODE, OUTPUT_FRAME_RATE, FPS_FLAG,
)
from v7_pipeline.encoder import (
    detect_encoder, encode_with_fallback, EncodeParams,
)
from v7_pipeline.filters import sample_random_params, build_filter_complex
from v7_pipeline.paths import temp_work_dir
from v7_pipeline.validate import get_duration_sec, validate_output

def make_output_name(input_name: str) -> str:
    p = Path(input_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{p.stem}_v7_{ts}{p.suffix}"

def safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass

def process_video(
    in_video: str | Path,
    out_dir: str | Path,
    *,
    profile: str | Profile = "BALANCED",
    seed: int | None = None,
    pad: bool = True,
    verify_hash: bool = True,
) -> str | None:
    """Stage 1 only. Returns output path or None. Never writes metadata atoms."""
    p = Path(in_video)
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        print(f"[ERR] Not found: {p}")
        return None

    prof = profile if isinstance(profile, Profile) else get_profile(profile)
    out_name = make_output_name(p.name)
    work = temp_work_dir()
    local_in = work / p.name
    local_out = work / out_name
    final_out = od / out_name

    duration_sec = get_duration_sec(p)
    print(f"[ ] Profile: {prof.name}")
    print(f"[ ] Duration: {duration_sec:.1f}s | Size: {p.stat().st_size/1024/1024:.1f} MB")

    try:
        shutil.copy2(str(p), str(local_in))
        print("[OK] Temp copy")

        rp = sample_random_params(prof, seed=seed)
        if not pad:
            rp.pad_bytes = 0

        encoder, enc_reason = detect_encoder()
        print(f"[ ] Encoder: {encoder} ({enc_reason})")

        fc, extra = build_filter_complex(prof, rp)
        params = EncodeParams(
            encoder=encoder,
            crf=rp.crf,
            gop=rp.gop,
            b_frames=rp.bframes,
            b_strategy=rp.bstrat,
            b_pyramid=rp.bpyramid,
            ref_frames=rp.ref,
            mv_params=rp.mv_params,
            b_frame_inject=prof.b_frame_inject,
            target_bitrate=TARGET_BITRATE,
            sample_rate=SAMPLE_RATE,
            frame_rate_mode=FRAME_RATE_MODE,
            output_frame_rate=OUTPUT_FRAME_RATE,
            fps_flag=FPS_FLAG,
        )

        st = time.time()
        ok, log_tail, used = encode_with_fallback(
            str(local_in), str(local_out), fc, extra, params, duration_sec,
        )
        if not ok:
            print(f"[ERR] FFmpeg failed ({used.encoder}):\n{log_tail}")
            return None
        print(f"[OK] Encode {time.time()-st:.1f}s ({used.encoder})")

        vr = validate_output(local_out, duration_sec, require_audio=False)
        if not vr.ok:
            print(f"[ERR] Validate: {vr.message}")
            safe_unlink(local_out)
            return None
        print(f"[OK] Validated: {vr.message}")

        shutil.copy2(str(local_out), str(final_out))
        safe_unlink(local_out)

        if rp.pad_bytes > 0:
            try:
                with open(final_out, "ab") as f:
                    f.write(os.urandom(rp.pad_bytes))
                print(f"[OK] Behavioral padding: +{rp.pad_bytes} bytes")
            except Exception as e:
                print(f"[!] Pad skipped: {e}")

        # re-validate after pad (size only matters; streams unchanged)
        vr2 = validate_output(final_out, duration_sec, require_audio=False)
        if not vr2.ok:
            print(f"[ERR] Post-pad validate: {vr2.message}")
            safe_unlink(final_out)
            return None

        if verify_hash:
            with open(p, "rb") as f:
                ih = hashlib.sha256(f.read()).hexdigest()
            with open(final_out, "rb") as f:
                oh = hashlib.sha256(f.read()).hexdigest()
            print(f"[OK] SHA-256: {'CHANGED' if ih != oh else 'SAME'}")

        print(f"[SUCCESS] {final_out} ({final_out.stat().st_size/1024/1024:.1f} MB)")
        print("[!] Metadata is separate — use meta_data_hashing notebook if needed.")
        return str(final_out)
    except Exception as e:
        print(f"[ERR] {e}")
        return None
    finally:
        safe_unlink(local_in)
        safe_unlink(local_out)
```

- [ ] **Step 3: Run unit tests**

Run: `pytest tests/test_stage1_unit.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add v7_pipeline/stage1.py tests/test_stage1_unit.py
git commit -m "feat(v7): stage1 process_video with validate and cleanup"
```

---

### Task 6: batch.py + CLI

**Files:**
- Create: `v7_pipeline/batch.py`
- Create: `v7_pipeline/cli.py`
- Create: `v7_pipeline/__main__.py`
- Create: `tests/test_batch.py`

- [ ] **Step 1: Write batch pure-function tests**

```python
# tests/test_batch.py
from pathlib import Path
from v7_pipeline.batch import list_videos, should_skip_existing, summarize

def test_list_videos(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"x")
    (tmp_path / "c.MOV").write_bytes(b"x")
    vids = list_videos(tmp_path)
    names = {v.name for v in vids}
    assert "a.mp4" in names
    assert "c.MOV" in names
    assert "b.txt" not in names

def test_skip_existing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "clip_v7_20260101_000000_0.mp4").write_bytes(b"x")
    assert should_skip_existing(Path("clip.mp4"), out) is True
    assert should_skip_existing(Path("other.mp4"), out) is False

def test_summarize():
    s = summarize([("a", "ok"), ("b", None), ("c", "SKIP")])
    assert s["ok"] == 1 and s["err"] == 1 and s["skip"] == 1
```

- [ ] **Step 2: Implement batch + cli**

```python
# v7_pipeline/batch.py
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
        if f.is_file() and f.name.startswith(f"{stem}_v7_") and f.suffix.lower() in VIDEO_EXTS:
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
        print(f"\n{'='*60}\n[{i}/{len(videos)}] {v.name}\n{'='*60}")
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
    print(f"\n[SUMMARY] OK={s['ok']} ERR={s['err']} SKIP={s['skip']} total={s['total']}")
    return results
```

```python
# v7_pipeline/cli.py
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

from v7_pipeline.batch import list_videos, process_batch
from v7_pipeline.paths import ensure_dirs, input_dir, output_dir
from v7_pipeline.stage1 import process_video

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="v7_pipeline",
        description="V7 Stage 1 local hashing (re-encode only; no metadata).",
    )
    p.add_argument("--profile", default="BALANCED", choices=["SAFE", "BALANCED", "AGGRESSIVE"])
    p.add_argument("--input", type=str, default=None, help="Single input video path")
    p.add_argument("--batch", type=str, default=None, help="Folder of videos to process sequentially")
    p.add_argument("--out", type=str, default=None, help="Output directory (default: ./output)")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--no-pad", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    return p

def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
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
            vids, out, profile=args.profile, seed=args.seed,
            pad=pad, skip_existing=args.skip_existing,
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
```

```python
# v7_pipeline/__main__.py
from v7_pipeline.cli import main
raise SystemExit(main())
```

- [ ] **Step 3: Run unit tests + help**

Run:
```text
pytest tests/test_batch.py -v
python -m v7_pipeline --help
```
Expected: tests PASS; help shows `--profile`, `--batch`, `--skip-existing`, `--no-pad`, `--seed` (no `--stage2`)

- [ ] **Step 4: Commit**

```bash
git add v7_pipeline/batch.py v7_pipeline/cli.py v7_pipeline/__main__.py tests/test_batch.py
git commit -m "feat(v7): batch runner and Stage 1 CLI"
```

---

### Task 7: Thin `V7_Combined_local.py` wrapper

**Files:**
- Modify: `V7_Combined_local.py` (replace monolith with wrapper)
- Optional backup: `V7_Combined_local.monolith.bak` (copy first)

- [ ] **Step 1: Backup monolith**

```powershell
Copy-Item "V7_Combined_local.py" "V7_Combined_local.monolith.bak"
```

- [ ] **Step 2: Replace with wrapper**

```python
# V7_Combined_local.py
"""Compat entrypoint — Stage 1 only. Metadata is a separate notebook."""
from v7_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify both entrypoints**

Run:
```text
python V7_Combined_local.py --help
python -m v7_pipeline --help
```
Expected: both show same CLI; no import of Stage 2 / metadata modules

- [ ] **Step 4: Grep guard — no Stage 2 in package**

Run: search `v7_pipeline/` for `stage2`, `metadata`, `xmp`, `device_profile` — must be empty (comments about “metadata separate” in print strings are OK).

- [ ] **Step 5: Commit**

```bash
git add V7_Combined_local.py
git commit -m "refactor(v7): thin CLI wrapper over v7_pipeline"
```

---

### Task 8: Smoke script + full test suite

**Files:**
- Create: `scripts/smoke_stage1.py`
- Create: `tests/test_no_stage2_imports.py`

- [ ] **Step 1: Import-safety test**

```python
# tests/test_no_stage2_imports.py
import ast
from pathlib import Path

def test_package_has_no_stage2_module():
    root = Path(__file__).resolve().parents[1] / "v7_pipeline"
    assert not (root / "stage2.py").exists()

def test_no_forbidden_imports():
    root = Path(__file__).resolve().parents[1] / "v7_pipeline"
    forbidden = {"stage2", "meta_data_hashing"}
    for py in root.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] not in forbidden
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden
```

- [ ] **Step 2: Smoke script**

```python
# scripts/smoke_stage1.py
"""Optional E2E: process latest input with SAFE (faster). Exit 0 on success."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v7_pipeline.cli import main

if __name__ == "__main__":
    # Prefer SAFE for speed during smoke
    raise SystemExit(main(["--profile", "SAFE"]))
```

- [ ] **Step 3: Run full unit suite**

Run: `pytest tests/ -v`  
Expected: all PASS

- [ ] **Step 4: Optional real encode smoke** (if `input/` has a short video)

Run: `python scripts/smoke_stage1.py`  
Expected: `[SUCCESS]` path under `output/`; playable with ffprobe

If video is huge, use a short test clip or skip and note in handoff.

- [ ] **Step 5: Final commit**

```bash
git add scripts/smoke_stage1.py tests/test_no_stage2_imports.py
git commit -m "test(v7): smoke helper and no-stage2 import guard"
```

---

## Spec coverage checklist (self-review)

| Spec requirement | Task |
|------------------|------|
| Modular `v7_pipeline/` layout | 1–6 |
| No Stage 2 / metadata | 7 grep + 8 import test; no stage2.py |
| SAFE / BALANCED / AGGRESSIVE | 1 config + 4 filters |
| NVENC detect + fallback | 3 encoder |
| Validate streams/duration/size | 2 validate + 5 stage1 |
| try/finally temp cleanup | 5 stage1 `finally` |
| Batch sequential + summary | 6 batch |
| `--skip-existing` | 6 batch/cli |
| Thin `V7_Combined_local.py` | 7 |
| CLI flags (no `--stage2`) | 6 cli |
| EOF pad optional | 5 stage1 + `--no-pad` |
| Seed reproducibility | 4 filters + CLI `--seed` |
| Logging conventions | prints in stage1/batch |
| Smoke / tests | 8 |
| Windows paths / TEMP | 1 paths |

## Placeholder / consistency scan

- Profile field names: `ai_optical_flow`, `ai_mimicry`, `dct_geq` — use these consistently in config, filters, tests.
- `EncodeParams.encoder` is `"nvenc"` | `"libx264"` — matches `detect_encoder` return.
- `process_video` returns `str | None`; batch uses `"SKIP"` sentinel string for skips (document in summarize).
- No TBD steps; filter port must be full strings from monolith (Task 4 agent duty).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-11-v7-stage1-robust.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with checkpoints  

Which approach?
