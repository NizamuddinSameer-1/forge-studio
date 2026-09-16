"""Perceptual budget guards for the ML stage.

Pure numpy — no torch dependency — so these run anywhere and are cheap to
unit-test. SSIM here is a global-stats grayscale approximation: sufficient
for a budget guard (we only need "did the perturbation stay imperceptible"),
not a full reference implementation.
"""
from __future__ import annotations

import numpy as np

# SSIM stability constants for 8-bit content scaled to [0, 1]
_K1, _K2 = 0.01, 0.03
_C1, _C2 = _K1**2, _K2**2


def _to_gray_f(x: np.ndarray) -> np.ndarray:
    """(H,W,3) uint8/float -> (H,W) float32 in [0,1]."""
    if x.dtype == np.uint8:
        x = x.astype(np.float32) / 255.0
    else:
        x = x.astype(np.float32)
        if x.max() > 1.5:  # tolerate 0-255 floats
            x = x / 255.0
    if x.ndim == 3:
        x = 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]
    return x


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Global-stats grayscale SSIM in [-1, 1]; 1.0 means identical."""
    ga, gb = _to_gray_f(a), _to_gray_f(b)
    mu_a, mu_b = ga.mean(), gb.mean()
    var_a, var_b = ga.var(), gb.var()
    cov = ((ga - mu_a) * (gb - mu_b)).mean()
    num = (2 * mu_a * mu_b + _C1) * (2 * cov + _C2)
    den = (mu_a**2 + mu_b**2 + _C1) * (var_a + var_b + _C2)
    return float(num / den) if den else 1.0


def clip_to_budget(
    src: np.ndarray,
    pert: np.ndarray,
    floor: float,
    max_halvings: int = 8,
) -> np.ndarray:
    """Scale the perturbation down until mean SSIM(src, out) >= floor.

    src, pert: (N,H,W,3) uint8 arrays of identical shape.
    Returns a new uint8 array; never mutates inputs. If the floor is
    unreachable within max_halvings, returns the best (last) attempt.
    """
    assert src.shape == pert.shape, "src and pert must have identical shape"
    src_f = src.astype(np.float32)
    delta = pert.astype(np.float32) - src_f

    best = pert
    for _ in range(max_halvings + 1):
        out = np.clip(src_f + delta, 0, 255).astype(np.uint8)
        scores = [ssim(src[i], out[i]) for i in range(src.shape[0])]
        if float(np.mean(scores)) >= floor:
            return out
        best = out
        delta *= 0.5
    return best
