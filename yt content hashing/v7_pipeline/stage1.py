from __future__ import annotations

import hashlib
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from v7_pipeline.config import (
    DOWNSCALE_H,
    DOWNSCALE_W,
    FRAME_RATE_MODE,
    OUTPUT_FRAME_RATE,
    Profile,
    SAMPLE_RATE,
    get_profile,
)
from v7_pipeline.encoder import (
    EncodeParams,
    detect_encoder,
    detect_fps_flag,
    encode_with_fallback,
)
from v7_pipeline.filters import build_filter_complex, sample_random_params
from v7_pipeline.paths import temp_work_dir
from v7_pipeline.validate import get_duration_sec, get_video_size, validate_output


def make_output_name(input_name: str, hint: str | None = None) -> str:
    """Build the output filename.

    `hint` overrides the stem taken from the input path. Callers that render
    to an internal temp file first use this so the final deliverable is named
    after the user's real video instead of leaking the temp name.
    """
    p = Path(input_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = hint or p.stem
    return f"{stem}_v7_{ts}{p.suffix}"


def safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Streamed SHA-256 — constant memory regardless of file size."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def is_audio_encode_failure(log_tail: str) -> bool:
    """Detect ffmpeg audio-encoder NaN/Inf failures from the log tail."""
    return ("NaN" in log_tail or "Inf" in log_tail) and (
        "aac" in log_tail or "[aout]" in log_tail
    )


def process_video(
    in_video: str | Path,
    out_dir: str | Path,
    *,
    profile: str | Profile = "BALANCED",
    seed: int | None = None,
    pad: bool = True,
    verify_hash: bool = True,
    name_hint: str | None = None,
    rescale: bool | None = None,
) -> str | None:
    """Stage 1 only. Returns output path or None. Never writes metadata atoms.

    `name_hint` names the output after the user's real video when the input is
    an internal temp render (see `make_output_name`).
    `rescale` controls the output canvas: default (None) keeps the classic CLI
    behaviour (landscape -> 720px tall, portrait/square -> 1280px wide, now
    with exact even rounding); `rescale=False` preserves the input dimensions
    untouched — Forge Studio passes False because the editor already rendered
    the exact export canvas, and the old forced re-scale upscaled user crops
    and drifted 1080x1920 -> 1280x2270 through the blur-border chain.
    """
    p = Path(in_video)
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        print(f"[ERR] Not found: {p}")
        return None

    prof = profile if isinstance(profile, Profile) else get_profile(profile)
    out_name = make_output_name(p.name, name_hint)
    work = temp_work_dir()
    local_in = work / p.name
    local_out = work / out_name
    final_out = od / out_name

    duration_sec = get_duration_sec(p)
    print(f"[ ] Profile: {prof.name}")
    print(f"[ ] Duration: {duration_sec:.1f}s | Size: {p.stat().st_size / 1024 / 1024:.1f} MB")

    # Preflight: refuse to start if the temp/output disk can't hold the
    # intermediate copies (source copy + encoded output + ML re-encode).
    # Failing here beats an opaque ffmpeg "No space left on device" mid-run.
    try:
        need = p.stat().st_size * 4 + 64 * 1024 * 1024  # 4x source + 64MB slack
        free = shutil.disk_usage(work).free
        if free < need:
            print(
                f"[ERR] Not enough disk space in temp dir ({work}): "
                f"need ~{need / 1024**2:.0f} MB, have {free / 1024**2:.0f} MB"
            )
            return None
    except OSError:
        pass  # can't probe disk — proceed and let ffmpeg report any failure

    try:
        shutil.copy2(str(p), str(local_in))
        print("[OK] Temp copy")

        rp = sample_random_params(prof, seed=seed)
        if not pad:
            rp.pad_bytes = 0
        print(f"[ ] Seed: {rp.seed} (use --seed {rp.seed} to reproduce this exact run)")

        scale_to: tuple[int, int] | None = None
        if rescale is not False:
            iw, ih = get_video_size(p)
            if iw > 0 and ih > 0:
                if iw > ih:  # landscape -> 720 tall, width rounded to even
                    th = DOWNSCALE_H
                    tw = int(round(iw * th / ih / 2) * 2)
                else:  # portrait / square -> 1280 wide, height rounded to even
                    tw = DOWNSCALE_W
                    th = int(round(ih * tw / iw / 2) * 2)
                scale_to = (tw, th)
                print(f"[ ] Output canvas: {tw}x{th}")
            else:
                print("[!] Could not probe dimensions; keeping source size")
        else:
            print("[ ] Output canvas: source (no rescale)")

        encoder, enc_reason = detect_encoder()
        print(f"[ ] Encoder: {encoder} ({enc_reason})")
        print(f"[ ] Config: CRF={rp.crf} GOP={rp.gop} PTS_Jitter={rp.pts_jitter:.6f}")

        fc, extra = build_filter_complex(prof, rp, scale_to=scale_to)
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
            target_bitrate=f"{rp.bitrate_mbps:.1f}M",
            sample_rate=SAMPLE_RATE,
            frame_rate_mode=FRAME_RATE_MODE,
            output_frame_rate=OUTPUT_FRAME_RATE,
            fps_flag=detect_fps_flag(),
        )

        st = time.time()
        ok, log_tail, used = encode_with_fallback(
            str(local_in), str(local_out), fc, extra, params, duration_sec
        )
        if not ok:
            if is_audio_encode_failure(log_tail):
                print(
                    f"[!] Audio encode failed (seed={rp.seed}); "
                    "retrying with simpler audio chain (pitch+EQ+comb only)..."
                )
                fc, extra = build_filter_complex(prof, rp, scale_to=scale_to, simple_audio=True)
                ok, log_tail, used = encode_with_fallback(
                    str(local_in),
                    str(local_out),
                    fc,
                    extra,
                    params,
                    duration_sec,
                )
                if not ok and is_audio_encode_failure(log_tail):
                    print(
                        f"[!] Simple audio also failed (seed={rp.seed}); "
                        "rebuilding without audio as last resort..."
                    )
                    fc, extra = build_filter_complex(prof, rp, scale_to=scale_to, include_audio=False)
                    ok, log_tail, used = encode_with_fallback(
                        str(local_in),
                        str(local_out),
                        fc,
                        extra,
                        params,
                        duration_sec,
                    )
            if not ok:
                print(f"[ERR] FFmpeg failed ({used.encoder}):\n{log_tail}")
                return None
        print(f"[OK] Encode {time.time() - st:.1f}s ({used.encoder})")

        vr = validate_output(local_out, duration_sec, require_audio=False)
        if not vr.ok:
            print(f"[ERR] Validate: {vr.message}")
            safe_unlink(local_out)
            return None
        print(f"[OK] Validated: {vr.message}")

        # Optional Stage 1.5: ML adversarial pass (no-op if deps/GPU absent)
        if getattr(prof, "ml_stage", False):
            from v7_pipeline.ml.orchestrate import run_ml_stage

            ml_out = run_ml_stage(local_out, prof, seed=rp.seed)
            if Path(ml_out) != local_out:
                safe_unlink(local_out)
                local_out = Path(ml_out)
                print("[OK] ML adversarial pass applied")

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
            ih = sha256_file(p)
            oh = sha256_file(final_out)
            print(f"[OK] SHA-256: {'CHANGED' if ih != oh else 'SAME'}")

        print(f"[SUCCESS] {final_out} ({final_out.stat().st_size / 1024 / 1024:.1f} MB)")
        print("[!] Metadata is separate — use meta_data_hashing notebook if needed.")
        return str(final_out)
    except Exception as e:
        print(f"[ERR] {e}")
        return None
    finally:
        safe_unlink(local_in)
        safe_unlink(local_out)
