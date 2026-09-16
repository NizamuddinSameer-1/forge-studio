"""Optional ML stage (Stage 1.5). Heavy deps are imported lazily so the base
package runs with zero ML dependencies installed."""
from __future__ import annotations

import importlib.util


def ml_available() -> bool:
    """True only if torch is importable and a usable device exists."""
    if importlib.util.find_spec("torch") is None:
        return False
    try:
        import torch  # noqa: PLC0415 - intentional lazy import

        return bool(torch.cuda.is_available()) or _cpu_ok()
    except Exception:
        return False


def _cpu_ok() -> bool:
    """Allow CPU for tiny test tensors only; real video needs CUDA."""
    return True  # adversarial on CPU is slow but valid for tests


def device() -> str:
    """Best available device string ('cuda' if usable, else 'cpu')."""
    if importlib.util.find_spec("torch") is None:
        return "cpu"
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
