"""Tests for the optional ML stage. Every test here must pass on a machine
with NO torch / open_clip installed — the whole point is graceful
degradation of the base package."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np

from v7_pipeline.config import get_profile
from v7_pipeline.ml import device, ml_available
from v7_pipeline.ml.budget import clip_to_budget, ssim
from v7_pipeline.ml.orchestrate import (
    _pick_stride,
    _probe_fps,
    _reencode_with_delta,
    run_ml_stage,
)
from v7_pipeline.validate import duration_tolerance_ok, get_duration_sec


def test_ml_available_runs_without_torch():
    # On this machine torch is absent -> False; on a GPU box it may be True.
    # Either way it must return a bool and never raise.
    assert isinstance(ml_available(), bool)
    assert device() in ("cpu", "cuda")


def test_run_ml_stage_noops_when_profile_disables_it(tmp_path):
    prof = get_profile("SAFE")  # ml_stage=False
    fake = tmp_path / "in.mp4"
    fake.write_bytes(b"not a real video")
    assert run_ml_stage(fake, prof, seed=0) == fake


def test_run_ml_stage_noops_without_deps(tmp_path):
    # BALANCED has ml_stage=True, but with no torch the orchestrator must
    # return the input unchanged rather than raising.
    if ml_available():
        return  # only meaningful on dep-less machines
    prof = get_profile("BALANCED")
    fake = tmp_path / "in.mp4"
    fake.write_bytes(b"not a real video")
    assert run_ml_stage(fake, prof, seed=0) == fake


def test_ssim_identical_is_one():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
    assert ssim(frame, frame) == 1.0


def test_ssim_accepts_float_and_uint8():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
    b = a.astype(np.float32) / 255.0
    assert ssim(a, b) > 0.999


def test_clip_to_budget_respects_floor():
    rng = np.random.default_rng(2)
    src = rng.integers(0, 256, (2, 64, 64, 3), dtype=np.uint8)
    pert = np.clip(
        src.astype(int) + rng.integers(-60, 60, src.shape), 0, 255
    ).astype(np.uint8)
    out = clip_to_budget(src, pert, floor=0.98)
    assert out.shape == src.shape and out.dtype == np.uint8
    mean_ssim = float(np.mean([ssim(src[i], out[i]) for i in range(2)]))
    assert mean_ssim >= 0.98


def test_clip_to_budget_never_mutates_inputs():
    rng = np.random.default_rng(3)
    src = rng.integers(0, 256, (1, 16, 16, 3), dtype=np.uint8)
    pert = rng.integers(0, 256, (1, 16, 16, 3), dtype=np.uint8)
    src_copy, pert_copy = src.copy(), pert.copy()
    clip_to_budget(src, pert, floor=0.99)
    assert np.array_equal(src, src_copy)
    assert np.array_equal(pert, pert_copy)


def test_profile_ml_defaults():
    assert get_profile("SAFE").ml_stage is False
    assert get_profile("TOON").ml_stage is False
    for name in ("BALANCED", "AGGRESSIVE", "AIMIMIC", "MAXIMUM"):
        assert get_profile(name).ml_stage is True
    bal = get_profile("BALANCED")
    assert bal.ml_video_adv is True
    assert 0 < bal.ml_video_adv_eps <= 16
    assert bal.ml_video_adv_steps >= 1
    assert 0.9 <= bal.ml_ssim_floor <= 1.0


def test_ml_stage_field_is_overridable():
    prof = dataclasses.replace(get_profile("SAFE"), ml_stage=True)
    assert prof.ml_stage is True
    assert get_profile("SAFE").ml_stage is False  # original untouched


# --- Real-video round-trip tests (need ffmpeg + the sample fixture) --------

_SAMPLE = Path(__file__).resolve().parent.parent / "input" / "_test_sample.mp4"


def _has_ffmpeg() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


import pytest  # noqa: E402

requires_video = pytest.mark.skipif(
    not (_SAMPLE.exists() and _has_ffmpeg()),
    reason="needs input/_test_sample.mp4 and ffmpeg",
)


@requires_video
def test_probe_fps_matches_avg_frame_rate():
    # Regression: _probe_fps must return avg_frame_rate (nb_frames/duration),
    # not r_frame_rate, so the re-encoded video keeps the source duration.
    fps = _probe_fps(_sample := _SAMPLE)
    assert fps > 0
    # avg_frame_rate for a 30fps CFR sample is exactly 30
    assert abs(fps - 30.0) < 0.5


@requires_video
def test_pick_stride_consistent_with_probe_fps():
    # stride * _FRAME_SAMPLE should land near the real frame count so the
    # per-sample delta covers the whole clip without overshooting.
    stride = _pick_stride(_SAMPLE)
    fps = _probe_fps(_SAMPLE)
    dur = get_duration_sec(_SAMPLE)
    total = fps * dur
    assert stride >= 1
    # stride should be roughly total/24 (within 2x either way)
    assert 0.5 * (total / 24) <= stride <= 2.0 * (total / 24) + 1


@requires_video
def test_reencode_with_delta_preserves_duration():
    # The bug that returned None on Colab: re-encode must keep duration
    # within tolerance so post-pad validation passes.
    rng = np.random.default_rng(0)
    n = 4
    src = rng.integers(0, 256, (n, 224, 224, 3), dtype=np.uint8)
    # small perturbation so out != src
    out = np.clip(src.astype(int) + rng.integers(-6, 6, src.shape), 0, 255).astype(np.uint8)

    result = Path(_reencode_with_delta(_SAMPLE, src, out))
    assert result.exists(), "re-encode produced no file"
    src_dur = get_duration_sec(_SAMPLE)
    out_dur = get_duration_sec(result)
    assert duration_tolerance_ok(src_dur, out_dur), (
        f"duration drifted: source={src_dur:.2f}s out={out_dur:.2f}s"
    )
    if result != _SAMPLE:
        # Windows can hold the muxed file open briefly; retry the cleanup.
        import time as _t

        for _ in range(5):
            try:
                result.unlink(missing_ok=True)
                break
            except PermissionError:
                _t.sleep(0.2)