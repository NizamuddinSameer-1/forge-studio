"""Stage 1.5 orchestrator: optional ML adversarial pass over a rendered video.

Contract:
- No-op (returns the input path unchanged) when the profile doesn't enable
  the ML stage, when ML deps/GPU are absent, or when anything fails.
- Never raises into the main pipeline: the base render is always valid, so
  on any error we log and return the original file.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from v7_pipeline.ml import ml_available

log = logging.getLogger(__name__)

_FRAME_SAMPLE = 24  # frames sampled for the adversarial pass (shorts are brief)
_SAMPLE_W, _SAMPLE_H = 224, 224  # encoder-native size keeps VRAM tiny


def run_ml_stage(video_path: Path, profile, seed: int = 0) -> Path:
    """Return an adversarially-perturbed copy of video_path, or video_path.

    The perturbation is computed on a small frame sample, then re-applied by
    re-encoding the full video through the same pipeline settings. If any
    step fails, the original path is returned so the pipeline continues.
    """
    video_path = Path(video_path)
    if not getattr(profile, "ml_stage", False):
        return video_path
    if not ml_available():
        log.info("ml stage skipped: torch/device unavailable")
        return video_path

    try:
        return _run(video_path, profile, seed)
    except Exception:
        log.exception("ml stage failed; returning unmodified video")
        return video_path


def _run(video_path: Path, profile, seed: int) -> Path:
    import numpy as np

    from v7_pipeline.ml.video_adv import perturb_frames

    frames = _decode_sample(video_path)
    if frames.size == 0:
        return video_path

    out = perturb_frames(
        frames,
        eps=getattr(profile, "ml_video_adv_eps", 6.0),
        steps=getattr(profile, "ml_video_adv_steps", 10),
        ssim_floor=getattr(profile, "ml_ssim_floor", 0.98),
        seed=seed,
    )
    if np.array_equal(out, frames):
        log.info("ml stage produced no change; keeping original")
        return video_path

    return _reencode_with_delta(video_path, frames, out)


def _decode_sample(video_path: Path):
    """Decode up to _FRAME_SAMPLE evenly-spaced frames as (N,224,224,3) uint8."""
    import numpy as np

    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video_path),
        "-vf", f"select='not(mod(n\\,{_pick_stride(video_path)}))',scale={_SAMPLE_W}:{_SAMPLE_H}",
        "-frames:v", str(_FRAME_SAMPLE),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros((0, _SAMPLE_H, _SAMPLE_W, 3), dtype=np.uint8)
    raw = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = raw.size // (_SAMPLE_H * _SAMPLE_W * 3)
    return raw[: n * _SAMPLE_H * _SAMPLE_W * 3].reshape(n, _SAMPLE_H, _SAMPLE_W, 3)


def _pick_stride(video_path: Path) -> int:
    """Rough frame-count probe so the sample spans the whole clip.

    Uses avg_frame_rate * duration (not nb_frames) so the stride matches the
    same timeline _probe_fps encodes at — nb_frames can disagree with the
    container duration on VFR sources, which would misalign the per-sample
    delta with the frames it covers.
    """
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate:format=duration",
        "-of", "default=noprint_wrappers=1", str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        vals = dict(
            line.split("=", 1)
            for line in proc.stdout.splitlines()
            if "=" in line
        )
        num, den = vals["avg_frame_rate"].split("/")[:2]
        fps = float(num) / float(den)
        total = int(round(fps * float(vals["duration"])))
        return max(1, total // _FRAME_SAMPLE)
    except Exception:
        return 10  # safe default for ~30fps shorts


def _reencode_with_delta(video_path: Path, src_frames, out_frames) -> Path:
    """Re-encode the full video with the adversarial perturbation applied.

    The PGD solution is computed on 224x224 frame samples. We stream the
    full-resolution decode -> delta apply -> encode frame-by-frame so peak
    RAM stays ~2 frames instead of the whole clip (a 60s 1080x1920 short
    would otherwise need ~22 GB and OOM the Colab kernel).

    Frames are matched to samples by index: sample i covers source frames
    [i*stride, (i+1)*stride). Audio is copied through unchanged.
    """
    import numpy as np

    stride = _pick_stride(video_path)
    delta = out_frames.astype(np.int16) - src_frames.astype(np.int16)  # (N,224,224,3)

    w, h = _probe_size(video_path)
    if w <= 0 or h <= 0:
        return video_path

    tmp = Path(tempfile.mkstemp(suffix=".mp4", prefix="mlstage_")[1])
    ok = _stream_apply_and_encode(video_path, delta, w, h, stride, tmp)
    if not ok:
        tmp.unlink(missing_ok=True)
        return video_path
    return tmp


def _probe_size(video_path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        w, h = proc.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return 0, 0


def _frame_count(video_path: Path) -> int:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames", "-of", "csv=p=0", str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        return int(proc.stdout.strip())
    except Exception:
        return 0


def _stream_apply_and_encode(
    video_path: Path, delta, w: int, h: int, stride: int, out_path: Path
) -> bool:
    """Decode -> apply upsampled delta -> encode, one frame at a time.

    Peak memory is ~2 full-res frames + the (N,224,224,3) delta, instead of
    the entire decoded clip. Returns True only if the muxed output exists.
    """
    import numpy as np

    fps = _probe_fps(video_path) or 30.0
    frame_bytes = h * w * 3
    n_samples = delta.shape[0]

    # Precompute nearest-neighbour upsample index maps (same for every frame).
    ys = (np.arange(h) * (_SAMPLE_H / h)).astype(np.intp).clip(0, _SAMPLE_H - 1)
    xs = (np.arange(w) * (_SAMPLE_W / w)).astype(np.intp).clip(0, _SAMPLE_W - 1)

    dec_cmd = [
        "ffmpeg", "-v", "error", "-i", str(video_path),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    silent = out_path.with_suffix(".silent.mp4")
    enc_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        str(silent),
    ]

    dec = enc = None
    try:
        dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE)
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
        assert dec.stdout is not None and enc.stdin is not None

        i = 0
        while True:
            buf = dec.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break  # clean EOF or truncated tail
            frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
            sample_idx = min(i // max(stride, 1), n_samples - 1)
            d_full = delta[sample_idx][ys][:, xs]  # (H,W,3) int16
            out = np.clip(frame.astype(np.int16) + d_full, 0, 255).astype(np.uint8)
            enc.stdin.write(out.tobytes())
            i += 1

        enc.stdin.close()
        if i == 0:
            return False
        if enc.wait(timeout=900) != 0 or not silent.exists():
            return False
    except (BrokenPipeError, OSError, subprocess.SubprocessError):
        return False
    finally:
        for p in (dec, enc):
            if p is not None and p.poll() is None:
                p.kill()
        if dec is not None and dec.stdout is not None:
            dec.stdout.close()

    # Mux with original audio (if any). No -shortest: the video now matches
    # the source duration, and -shortest would hide a short video by
    # truncating the audio to it instead of letting validation catch it.
    cmd2 = [
        "ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(video_path),
        "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "copy",
        str(out_path),
    ]
    proc2 = subprocess.run(cmd2, capture_output=True, timeout=300)
    silent.unlink(missing_ok=True)
    return proc2.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


def _probe_fps(video_path: Path) -> float:
    """Output fps that preserves the source duration.

    avg_frame_rate is exactly nb_frames/duration, so writing the decoded
    frames at that rate reproduces the source timeline. r_frame_rate can be
    HIGHER than the true rate (it's the lowest rate that can represent all
    timestamps accurately) — using it shortens the video (11.65s source came
    out as 10.80s on Colab and failed post-pad validation).
    """
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate,r_frame_rate",
        "-of", "csv=p=0", str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        parts = proc.stdout.strip().split(",")
        for rate in parts:  # avg first, r_frame_rate as fallback
            num, den = rate.split("/")[:2]
            fps = float(num) / float(den)
            if fps > 0:
                return fps
    except Exception:
        pass
    return 0.0
