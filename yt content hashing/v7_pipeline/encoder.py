from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Literal

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover - tqdm is a declared project dependency
    try:
        from tqdm import tqdm  # type: ignore
    except ImportError:

        class tqdm:  # type: ignore[no-redef]
            """No-op stand-in so a missing progress bar can never break encoding.

            A hard ImportError here used to take down the whole v7_pipeline
            import, which made callers silently skip hashing entirely.
            """

            def __init__(self, *args, **kwargs):
                self.n = 0
                self.total = kwargs.get("total", 100)

            def refresh(self) -> None:
                pass

            def close(self) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

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
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "h264_nvenc" not in r.stdout:
            return "libx264", "NVENC not in encoders list"
    except Exception as e:
        return "libx264", f"encoder list failed: {e}"

    try:
        test = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=0.1:size=320x240",
                "-frames:v",
                "1",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p4",
                "-rc",
                "constqp",
                "-qp",
                "23",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if test.returncode == 0:
            return "nvenc", "NVENC test encode succeeded"
        return "libx264", f"NVENC unavailable: {test.stderr.strip()[:80]}"
    except subprocess.TimeoutExpired:
        return "libx264", "NVENC test timed out (no GPU?)"
    except Exception as e:
        return "libx264", f"NVENC test failed: {e}"


_FPS_FLAG_CACHE: str | None = None


def detect_fps_flag() -> str:
    """Return '-fps_mode' on ffmpeg >= 5.1, '-vsync' on older builds.

    Colab/apt ffmpeg is often 4.x which rejects -fps_mode outright, so we
    probe once and cache the result.
    """
    global _FPS_FLAG_CACHE
    if _FPS_FLAG_CACHE is not None:
        return _FPS_FLAG_CACHE
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-h", "full"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        _FPS_FLAG_CACHE = "-fps_mode" if "-fps_mode" in (r.stdout + r.stderr) else "-vsync"
    except Exception:
        _FPS_FLAG_CACHE = "-vsync"  # safest fallback for old ffmpeg
    return _FPS_FLAG_CACHE


def run_ffmpeg_with_progress(
    cmd: list[str], duration_sec: float, desc: str = "Encoding"
) -> tuple[int, str]:
    cmd = cmd.copy()
    insert_at = 1 if (cmd and cmd[0] == "ffmpeg") else 0
    cmd[insert_at:insert_at] = ["-progress", "pipe:1"]
    if "-loglevel" in cmd:
        i = cmd.index("-loglevel")
        cmd[i : i + 2] = ["-loglevel", "error"]

    # Hard cap: a hung filter graph (e.g. stacked minterpolates) must not
    # block the pipeline forever. Generous so legit slow encodes still pass.
    timeout = max(600.0, duration_sec * 30)

    pbar = tqdm(
        total=100,
        desc=desc,
        unit="%",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}% [{elapsed}<{remaining}, {rate_fmt}]",
    )
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        captured: list[str] = []
        assert proc.stdout is not None
        deadline = time.monotonic() + timeout
        for line in proc.stdout:
            if time.monotonic() > deadline:
                proc.kill()
                pbar.close()
                return -1, f"ffmpeg timed out after {timeout:.0f}s ({desc})"
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
        proc.wait(timeout=60)
        pbar.n = 100
        pbar.refresh()
        pbar.close()
        return proc.returncode, "".join(captured)
    except Exception:
        pbar.close()
        if proc is not None and proc.poll() is None:
            proc.kill()
        raise


def build_encode_cmd(
    local_in: str,
    local_out: str,
    filter_complex: str,
    extra_inputs: list[str],
    params: EncodeParams,
) -> list[str]:
    """extra_inputs: flat ffmpeg args after main -i, e.g. ['-f','lavfi','-i','anoisesrc=...']"""
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        local_in,
    ]
    cmd.extend(extra_inputs)
    cmd.extend(["-filter_complex", filter_complex])
    if "[aout]" not in filter_complex:
        cmd.extend(["-map", "[vout]", "-an"])
    else:
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
    # strip copied container metadata so outputs don't carry source fingerprints
    cmd.extend(["-map_metadata", "-1", "-map_chapters", "-1"])

    if params.encoder == "nvenc":
        cmd.extend(
            [
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p4",
                "-qp",
                str(params.crf - 4),
                "-pix_fmt",
                "yuv420p",
                "-g",
                str(params.gop),
                "-b:v",
                params.target_bitrate,
                "-maxrate",
                params.target_bitrate,
                "-bufsize",
                params.target_bitrate,
            ]
        )
        if params.b_frame_inject:
            cmd.extend(["-bf", str(params.b_frames)])
            cmd.extend(
                ["-b_ref_mode", "middle" if params.b_pyramid >= 1 else "disabled"]
            )
    else:
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "fastdecode",
                "-crf",
                str(params.crf),
                "-pix_fmt",
                "yuv420p",
                "-threads",
                "0",
                "-g",
                str(params.gop),
                "-b:v",
                params.target_bitrate,
                "-maxrate",
                params.target_bitrate,
                "-bufsize",
                params.target_bitrate,
            ]
        )
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

    cmd.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(params.sample_rate),
            "-movflags",
            "+faststart",
            local_out,
        ]
    )
    return cmd


def encode_with_fallback(
    local_in: str,
    local_out: str,
    filter_complex: str,
    extra_inputs: list[str],
    params: EncodeParams,
    duration_sec: float,
) -> tuple[bool, str, EncodeParams]:
    """Returns (ok, log_tail, params_used). On NVENC fail, retries libx264 once.
    Audio-failure retry is handled by the caller (stage1) via a rebuilt graph."""
    cmd = build_encode_cmd(local_in, local_out, filter_complex, extra_inputs, params)
    ret, out = run_ffmpeg_with_progress(
        cmd, duration_sec, desc=f"Encoding ({params.encoder})"
    )
    if ret == 0:
        return True, out[-1500:], params

    if params.encoder == "nvenc":
        print("[!] NVENC failed, rebuilding with libx264 ultrafast...")
        fb = EncodeParams(**{**params.__dict__, "encoder": "libx264"})
        cmd2 = build_encode_cmd(local_in, local_out, filter_complex, extra_inputs, fb)
        ret2, out2 = run_ffmpeg_with_progress(
            cmd2, duration_sec, desc="Encoding (libx264)"
        )
        if ret2 == 0:
            return True, out2[-1500:], fb
        return False, out2[-1500:], fb
    return False, out[-1500:], params
