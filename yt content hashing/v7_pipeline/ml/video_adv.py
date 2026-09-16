"""Video adversarial perturbation against a CLIP/ViT surrogate encoder.

Goal: push the video's frames away from their own original embedding so
platform-side content matchers (which cluster near-duplicate embeddings)
no longer group this upload with its source — while staying inside an
L-inf bound and an SSIM floor so the change is imperceptible.

Heavy deps (torch, open_clip) are imported lazily inside functions so the
base package runs with zero ML dependencies. If deps are missing we raise
RuntimeError("ml extra not installed") and the caller falls back to the
un-perturbed video.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import numpy as np

from v7_pipeline.ml.budget import clip_to_budget

log = logging.getLogger(__name__)

_ENCODER_CACHE: dict[str, tuple] = {}

# ViT-B-32 laion2b_s34b_b79k safetensors is ~350 MB; require headroom for
# the download + torch load so we fail gracefully instead of dying mid-write.
_MIN_FREE_BYTES = 2 * 1024**3  # 2 GiB


def _prepare_cache() -> Path:
    """Pick a writable cache dir with enough free space for the CLIP weights.

    Colab's VM root disk is small and often nearly full; if the user has
    Drive mounted we prefer it so the ~350 MB download lands there instead.
    Sets HF_HOME / TORCH_HOME / XDG_CACHE_HOME so every downstream lib
    (open_clip -> huggingface_hub -> torch) uses the same location.
    Raises RuntimeError when no location has enough free space.
    """
    candidates = [
        Path("/content/drive/MyDrive/.cache/hf"),  # Colab + mounted Drive
        Path.home() / ".cache" / "hf",
    ]
    best, best_free = None, -1
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(c).free
        except OSError:
            continue
        if free > best_free:
            best, best_free = c, free
        if free >= _MIN_FREE_BYTES:
            best, best_free = c, free
            break
    if best is None or best_free < _MIN_FREE_BYTES:
        raise RuntimeError(
            f"not enough disk space for CLIP weights "
            f"(need {_MIN_FREE_BYTES / 1024**3:.1f} GiB, have "
            f"{max(best_free, 0) / 1024**3:.1f} GiB); free up space or mount Drive"
        )
    os.environ.setdefault("HF_HOME", str(best))
    os.environ.setdefault("TORCH_HOME", str(best / "torch"))
    os.environ.setdefault("XDG_CACHE_HOME", str(best.parent))
    log.info("ml cache dir: %s (%.1f GiB free)", best, best_free / 1024**3)
    return best


def _load_encoder(dev: str):
    """Load (and cache) the CLIP surrogate encoder + preprocess on device."""
    if dev in _ENCODER_CACHE:
        return _ENCODER_CACHE[dev]
    try:
        import torch
        import open_clip
    except Exception as exc:  # pragma: no cover - depends on env
        raise RuntimeError("ml extra not installed") from exc

    _prepare_cache()  # raises RuntimeError if disk is too full
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    model = model.to(dev).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    _ENCODER_CACHE[dev] = (model, preprocess, torch)
    return _ENCODER_CACHE[dev]


def _embed(model, preprocess, torch, dev: str, frames_u8: np.ndarray):
    """(N,H,W,3) uint8 -> (N,D) normalized embedding tensor on device."""
    from PIL import Image

    imgs = [preprocess(Image.fromarray(f)) for f in frames_u8]
    batch = torch.stack(imgs).to(dev)
    with torch.no_grad():
        emb = model.encode_image(batch)
    return emb / emb.norm(dim=-1, keepdim=True)


def perturb_frames(
    frames: np.ndarray,
    *,
    eps: float = 6.0,
    steps: int = 10,
    ssim_floor: float = 0.98,
    seed: int = 0,
) -> np.ndarray:
    """PGD-perturb frames away from their own CLIP embedding.

    frames: (N,H,W,3) uint8. Returns (N,H,W,3) uint8, same shape.
    eps is the L-inf bound in /255 units. A shared low-frequency temporal
    component plus a per-frame delta keeps the attack temporally smooth
    (no flicker) while still moving every frame's embedding.
    """
    if frames.size == 0:
        return frames

    from v7_pipeline.ml import device

    dev = device()
    model, preprocess, torch = _load_encoder(dev)

    src = frames.astype(np.float32) / 255.0
    src_t = torch.from_numpy(src).permute(0, 3, 1, 2).to(dev)  # N,3,H,W

    with torch.no_grad():
        ref_emb = _embed(model, preprocess, torch, dev, frames)

    eps_t = eps / 255.0
    alpha = eps_t / max(steps, 1)
    g = torch.Generator(device="cpu").manual_seed(seed)

    # shared temporal component (same direction every frame) + per-frame delta.
    # Both live inside a SINGLE L-inf eps ball: we optimise one combined
    # perturbation `delta` (initialised with a shared random direction) and
    # clamp the whole thing to +-eps_t every step, so the budget is never
    # exceeded.
    shared0 = (torch.rand((1, 3, 1, 1), generator=g) * 2 - 1).to(dev) * eps_t * 0.5
    delta = (shared0.expand_as(src_t).clone()).requires_grad_(True)

    for _ in range(steps):
        adv = torch.clamp(src_t + delta, 0.0, 1.0)
        # differentiable path: resize to encoder input and embed directly
        adv_img = torch.nn.functional.interpolate(
            adv, size=(224, 224), mode="bilinear", align_corners=False
        )
        emb = model.encode_image(_normalize(model, adv_img))
        emb = emb / emb.norm(dim=-1, keepdim=True)
        loss = (emb * ref_emb).sum(dim=-1).mean()  # cosine sim; minimize it
        loss.backward()
        with torch.no_grad():
            delta -= alpha * delta.grad.sign()
            delta.clamp_(-eps_t, eps_t)  # project combined perturbation onto eps ball
            delta.grad.zero_()

    with torch.no_grad():
        adv = torch.clamp(src_t + delta, 0.0, 1.0)
    out = (adv.permute(0, 2, 3, 1).cpu().numpy() * 255.0).round().astype(np.uint8)
    return clip_to_budget(frames, out, floor=ssim_floor)


def _normalize(model, x):
    """Apply the encoder's normalization stats to a [0,1] tensor.

    Only called after _load_encoder has succeeded, so torch is guaranteed
    importable here.
    """
    import torch

    mean = getattr(model.visual, "image_mean", None) or (0.48145466, 0.4578275, 0.40821073)
    std = getattr(model.visual, "image_std", None) or (0.26862954, 0.26130258, 0.27577711)
    m = torch.tensor(mean, device=x.device).view(1, 3, 1, 1)
    s = torch.tensor(std, device=x.device).view(1, 3, 1, 1)
    return (x - m) / s
