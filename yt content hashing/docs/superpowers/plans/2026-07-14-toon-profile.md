# TOON Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `TOON` profile for 2D/anime/cartoon content: lutrgb color quantization, bilateral edge-preserving smoothing, deband, vibrance, CAS line-art sharpening, manga halftone, and anime frame cadence.

**Architecture:** New `Profile` fields + `TOON` entry in `config.py`; new `RandomParams` fields populated in `sample_random_params`; toon filters injected into `fg_chain` and cadence into the video tail in `filters.py`; `cli.py` gains the choice; tests guard graph content + regression.

**Tech Stack:** Python 3.13, ffmpeg (lutrgb, bilateral, deband, vibrance, cas, geq, minterpolate), pytest.

---

### Task 1: config.py — TOON fields + profile

**Files:** Modify `v7_pipeline/config.py`

- [ ] Add fields before `# audio` comment:
```python
    ai_bg_morph: bool = True
    # ai-look stylization (used by AIMIMIC)
    bloom_enable: bool = False
    bloom_strength: float = 0.15
    sat_lift: float = 0.97
    vae_chroma: float = 0.0
    # toon (used by TOON)
    toon_quantization: bool = False
    toon_line_art: bool = False
    toon_cadence: bool = False
    toon_halftone: bool = False
    toon_bilateral: bool = False
    toon_vibrance: bool = False
    toon_deband: bool = False
    toon_levels: int = 48
    cas_strength: float = 0.7
    halftone_amp: float = 1.5
    vibrance_intensity: float = 0.15
    # audio
```

- [ ] Add `TOON` entry to `PROFILES` (after AIMIMIC, before closing `}`):
```python
    "TOON": Profile(
        name="TOON",
        toon_quantization=True,
        toon_line_art=True,
        toon_cadence=True,
        toon_halftone=True,
        toon_bilateral=True,
        toon_vibrance=True,
        toon_deband=True,
        toon_levels=48,
        cas_strength=0.7,
        halftone_amp=1.5,
        vibrance_intensity=0.15,
        chromatic_enable=True,
        chromatic_shift=1,
        grain_strength=0.0,
        ai_plastic_smoothing=False,
        ai_mimicry=False,
        dct_geq=False,
        bloom_enable=False,
        hue_spatial_drift=True,
        behavioral_pad=True,
        range_scale=1.1,
    ),
```

- [ ] Verify: `python -c "from v7_pipeline.config import get_profile as g; p=g('TOON'); print(p.name, p.toon_levels, p.cas_strength, p.grain_strength)"` -> `TOON 48 0.7 0.0`
- [ ] Commit: `git add v7_pipeline/config.py; git commit -m "feat(config): add TOON profile and toon fields"`

---

### Task 2: filters.py — RandomParams fields + populate

**Files:** Modify `v7_pipeline/filters.py`

- [ ] Add to `RandomParams` dataclass after `persp: float`:
```python
    persp: float
    toon_levels: int
    cas_strength: float
    halftone_amp: float
    vibrance_intensity: float
```

- [ ] Non-randomized branch: add before `persp=` line's closing, i.e. after `persp=3.0 if PERCEPTUAL_WARP_ENABLE else 0.0,`:
```python
            persp=3.0 if PERCEPTUAL_WARP_ENABLE else 0.0,
            toon_levels=profile.toon_levels,
            cas_strength=profile.cas_strength,
            halftone_amp=profile.halftone_amp,
            vibrance_intensity=profile.vibrance_intensity,
```

- [ ] Randomized branch: after `persp=rng.uniform(2.0, 4.0) if PERCEPTUAL_WARP_ENABLE else 0.0,`:
```python
        persp=rng.uniform(2.0, 4.0) if PERCEPTUAL_WARP_ENABLE else 0.0,
        toon_levels=profile.toon_levels,
        cas_strength=profile.cas_strength * s,
        halftone_amp=profile.halftone_amp * s * rng.uniform(0.8, 1.2),
        vibrance_intensity=profile.vibrance_intensity * s,
    )
```

- [ ] Verify: `python -c "from v7_pipeline.config import get_profile as g; from v7_pipeline.filters import sample_random_params as s; rp=s(g('TOON'), seed=1); print(rp.toon_levels, round(rp.cas_strength,3), round(rp.halftone_amp,3))"`
- [ ] Commit: `git add v7_pipeline/filters.py; git commit -m "feat(filters): add toon fields to RandomParams"`

---

### Task 3: filters.py — inject toon filters into fg_chain

**Files:** Modify `v7_pipeline/filters.py`

- [ ] Insert toon block right before `fg_chain += ",format=yuv420p[sharp_foreground_fg]"`:
```python
    if profile.toon_bilateral:
        fg_chain += ",bilateral=sigmaS=8:sigmaR=0.1"
    if profile.toon_quantization:
        L = max(2, int(rp.toon_levels))
        step = 255.0 / (L - 1)
        q = f"round(val/{step:.6f})*{step:.6f}"
        fg_chain += f",lutrgb=r='{q}':g='{q}':b='{q}'"
    if profile.toon_deband:
        fg_chain += ",deband=1thr=0.02:2thr=0.02:3thr=0.02:4thr=0.02"
    if profile.toon_vibrance:
        fg_chain += f",vibrance=intensity={rp.vibrance_intensity:.4f}"
    if profile.toon_line_art:
        fg_chain += f",cas=strength={rp.cas_strength:.4f}"
    if profile.toon_halftone:
        fg_chain += (
            f",geq=lum='lum(X,Y)+{rp.halftone_amp:.4f}*sin(X*0.8+Y*0.8)'"
        )
```

- [ ] Verify graph: `python -c "from v7_pipeline.config import get_profile as g; from v7_pipeline.filters import build_filter_complex as bf, sample_random_params as s; fc,_=bf(g('TOON'), s(g('TOON'), seed=1)); print('lutrgb', 'lutrgb=' in fc); print('cas', 'cas=strength=' in fc); print('bilateral', 'bilateral=' in fc); print('vibrance', 'vibrance=' in fc); print('halftone', 'sin(X*0.8+Y*0.8)' in fc)"` -> all True
- [ ] Commit: `git add v7_pipeline/filters.py; git commit -m "feat(filters): inject toon quantize/bilateral/deband/vibrance/cas/halftone"`

---

### Task 4: filters.py — anime cadence in video tail

**Files:** Modify `v7_pipeline/filters.py`

- [ ] Insert cadence after the `vit_temporal_blend` block and before the `if profile.pts_jitter:` block:
```python
    if profile.vit_temporal_blend:
        w2 = rp.vit_blend
        w1 = 1.0 - w2
        vf_parts.append(
            f"[{vit_chain}]tmix=frames=2:weights='{w1:.4f} {w2:.4f}'[vit_blended]"
        )
        vit_chain = "vit_blended"

    if profile.toon_cadence:
        vf_parts.append(
            f"[{vit_chain}]fps=15,minterpolate=fps=30:mi_mode=dup[toon_cadence]"
        )
        vit_chain = "toon_cadence"

    if profile.pts_jitter:
```

- [ ] Verify: `python -c "from v7_pipeline.config import get_profile as g; from v7_pipeline.filters import build_filter_complex as bf, sample_random_params as s; fc,_=bf(g('TOON'), s(g('TOON'), seed=1)); print('cadence', 'minterpolate=fps=30:mi_mode=dup' in fc)"` -> True
- [ ] Commit: `git add v7_pipeline/filters.py; git commit -m "feat(filters): add anime frame cadence to TOON"`

---

### Task 5: cli.py — add TOON choice

**Files:** Modify `v7_pipeline/cli.py`

- [ ] Change choices line to:
```python
        choices=["SAFE", "BALANCED", "AGGRESSIVE", "AIMIMIC", "MAXIMUM", "TOON"],
```
- [ ] Verify: `python -m v7_pipeline --help 2>&1 | findstr TOON`
- [ ] Commit: `git add v7_pipeline/cli.py; git commit -m "feat(cli): add TOON to --profile choices"`

---

### Task 6: tests

**Files:** Modify `tests/test_filters.py`

- [ ] Append:
```python
def test_toon_graph_has_all_toon_filters():
    prof = get_profile("TOON")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "lutrgb=" in fc, "quantization missing"
    assert "bilateral=" in fc, "bilateral missing"
    assert "deband=" in fc, "deband missing"
    assert "vibrance=" in fc, "vibrance missing"
    assert "cas=strength=" in fc, "cas missing"
    assert "sin(X*0.8+Y*0.8)" in fc, "halftone missing"
    assert "minterpolate=fps=30:mi_mode=dup" in fc, "cadence missing"


def test_safe_has_no_toon_filters():
    prof = get_profile("SAFE")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "lutrgb=" not in fc
    assert "cas=strength=" not in fc
    assert "minterpolate=fps=30:mi_mode=dup" not in fc
```

- [ ] Run: `python -m pytest tests/test_filters.py -q` -> all pass
- [ ] Commit: `git add tests/test_filters.py; git commit -m "test(filters): TOON graph + SAFE regression"`

---

### Task 7: end-to-end

- [ ] Run TOON on a clip in `input/` and confirm SUCCESS + output file.
- [ ] Run SAFE as regression smoke.

---

## Self-Review Notes
- Coverage: quantization(T3), cas(T3), cadence(T4), halftone(T3), bilateral(T3), vibrance(T3), deband(T3), config(T1), randomparams(T2), cli(T5), tests(T6), e2e(T7). All spec items mapped.
- Placeholders: none.
- Type consistency: `rp.toon_levels/cas_strength/halftone_amp/vibrance_intensity` declared T2, used T3; `profile.toon_*` declared T1, used T3/T4. Names consistent.
- Regression: all toon flags default False; other profiles unaffected.
