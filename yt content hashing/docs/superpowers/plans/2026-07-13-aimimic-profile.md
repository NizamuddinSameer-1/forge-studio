# AIMIMIC Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `AIMIMIC` profile that stylizes video output to look "AI-generated" (stronger-but-subtle): plastic smoothing, an 8x8 VAE block grid with chroma offset, a soft bloom/glow, and a slight saturation lift.

**Architecture:** New `Profile` in `config.py` plus three new `Profile` fields and three new `RandomParams` fields feed small additions to `build_filter_complex` in `filters.py`. No change to orchestration/encoding. `cli.py` gains the new choice. A unit test guards graph content for both AIMIMIC and the regression (SAFE must be unchanged).

**Tech Stack:** Python 3.13, ffmpeg filter_complex (hqdn3d, geq, gblur, add, eq), pytest.

---

## File Structure

- Modify: `v7_pipeline/config.py` — new `Profile` fields (defaults) + `AIMIMIC` entry in `PROFILES`.
- Modify: `v7_pipeline/filters.py` — `RandomParams` fields; populate in `sample_random_params`; stronger `hqdn3d`; VAE grid chroma; saturation lift; bloom filter.
- Modify: `v7_pipeline/cli.py` — add `"AIMIMIC"` to `--profile` choices.
- Create: `tests/test_filters.py` — graph-content unit tests.

---

### Task 1: Add `AIMIMIC` profile + new `Profile` fields (`config.py`)

**Files:**
- Modify: `v7_pipeline/config.py`

- [ ] **Step 1: Add new `Profile` fields (insert before the `# audio` comment)**

Locate:
```python
    ai_bg_morph: bool = True
    # audio
```
Replace with:
```python
    ai_bg_morph: bool = True
    # ai-look stylization (used by AIMIMIC)
    bloom_enable: bool = False
    bloom_strength: float = 0.15
    sat_lift: float = 0.97
    vae_chroma: float = 0.0
    # audio
```

- [ ] **Step 2: Add `AIMIMIC` to `PROFILES` (insert before `def get_profile`)**

Locate:
```python
def get_profile(name: str) -> Profile:
```
Insert above it:
```python
    "AIMIMIC": Profile(
        name="AIMIMIC",
        ai_mimicry=True,
        ai_vae_grid_strength=0.08,
        ai_plastic_smoothing=True,
        ai_optical_flow=True,
        ai_bg_morph=True,
        dct_geq=True,
        vit_patch_noise=True,
        vit_luminance_flicker=True,
        vit_spatial_shift=True,
        vit_temporal_blend=True,
        chromatic_enable=True,
        hue_spatial_drift=True,
        grain_strength=3.0,
        bloom_enable=True,
        bloom_strength=0.15,
        sat_lift=1.06,
        vae_chroma=0.01,
        range_scale=1.1,
        behavioral_pad=True,
        behavioral_pad_max_bytes=4096,
    ),
```

- [ ] **Step 3: Sanity check the profile loads**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -c "from v7_pipeline.config import get_profile as g; p=g('AIMIMIC'); print(p.name, p.bloom_enable, p.sat_lift, p.vae_chroma)"
```
Expected: `AIMIMIC True 1.06 0.01`

- [ ] **Step 4: Commit**
```bash
git add v7_pipeline/config.py
git commit -m "feat(config): add AIMIMIC profile and ai-look fields"
```

---

### Task 2: Add new `RandomParams` fields + populate them (`filters.py`)

**Files:**
- Modify: `v7_pipeline/filters.py`

- [ ] **Step 1: Add fields to `RandomParams` dataclass**

Locate:
```python
    ai_vae: float
    ai_bg_morph: float
    persp: float
```
Replace with:
```python
    ai_vae: float
    ai_bg_morph: float
    bloom: float
    sat_lift: float
    vae_chroma: float
    persp: float
```

- [ ] **Step 2: Populate in the non-randomized branch of `sample_random_params`**

Locate:
```python
            ai_vae=profile.ai_vae_grid_strength * s * rng.uniform(0.8, 1.2),
            ai_bg_morph=0.002,
            persp=3.0 if PERCEPTUAL_WARP_ENABLE else 0.0,
```
Replace with:
```python
            ai_vae=profile.ai_vae_grid_strength * s * rng.uniform(0.8, 1.2),
            ai_bg_morph=0.002,
            bloom=profile.bloom_strength,
            sat_lift=profile.sat_lift,
            vae_chroma=profile.vae_chroma,
            persp=3.0 if PERCEPTUAL_WARP_ENABLE else 0.0,
```

- [ ] **Step 3: Populate in the randomized branch of `sample_random_params`**

Locate:
```python
        ai_vae=profile.ai_vae_grid_strength * s * rng.uniform(0.8, 1.2),
        ai_bg_morph=rng.uniform(0.001, 0.003) * s,
        persp=rng.uniform(2.0, 4.0) if PERCEPTUAL_WARP_ENABLE else 0.0,
    )
```
Replace with:
```python
        ai_vae=profile.ai_vae_grid_strength * s * rng.uniform(0.8, 1.2),
        ai_bg_morph=rng.uniform(0.001, 0.003) * s,
        bloom=profile.bloom_strength * s * rng.uniform(0.8, 1.2),
        sat_lift=profile.sat_lift * s,
        vae_chroma=profile.vae_chroma * s,
        persp=rng.uniform(2.0, 4.0) if PERCEPTUAL_WARP_ENABLE else 0.0,
    )
```

- [ ] **Step 4: Sanity check params populate**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -c "from v7_pipeline.config import get_profile as g; from v7_pipeline.filters import sample_random_params as s; rp=s(g('AIMIMIC'), seed=1); print(rp.bloom, round(rp.sat_lift,3), round(rp.vae_chroma,4))"
```
Expected: `0.15 1.166 0.011` (sat_lift and vae_chroma scaled by range_scale 1.1)

- [ ] **Step 5: Commit**
```bash
git add v7_pipeline/filters.py
git commit -m "feat(filters): add bloom/sat_lift/vae_chroma to RandomParams"
```

---

### Task 3: Apply the AI-look filters in `build_filter_complex` (`filters.py`)

**Files:**
- Modify: `v7_pipeline/filters.py`

- [ ] **Step 1: Strengthen plastic smoothing (`hqdn3d`)**

Locate:
```python
    if profile.ai_plastic_smoothing:
        # Aggressively smooth temporal noise -> "AI plastic" texture
        fg_chain += ",hqdn3d=luma_spatial=6:chroma_spatial=4:luma_tmp=8:chroma_tmp=6"
```
Replace with:
```python
    if profile.ai_plastic_smoothing:
        # Aggressively smooth temporal noise -> "AI plastic" texture
        fg_chain += ",hqdn3d=luma_spatial=8:chroma_spatial=6:luma_tmp=10:chroma_tmp=8"
```

- [ ] **Step 2: Add chroma offset to the VAE grid**

Locate:
```python
    if profile.ai_mimicry:
        # Inject 8x8 VAE decoder grid (static block luminance shift = AI fingerprint)
        fg_chain += (
            f",geq=lum='lum(X,Y)+{rp.ai_vae}"
            f"*sin(2*PI*floor(X/8)/8)*sin(2*PI*floor(Y/8)/8)'"
        )
```
Replace with:
```python
    if profile.ai_mimicry:
        # Inject 8x8 VAE decoder grid (block luminance + chroma shift = AI fingerprint)
        fg_chain += (
            f",geq=lum='lum(X,Y)+{rp.ai_vae}"
            f"*sin(2*PI*floor(X/8)/8)*sin(2*PI*floor(Y/8)/8)':"
            f"cb='cb(X,Y)+{rp.vae_chroma}*sin(2*PI*floor(X/8)/8)':"
            f"cr='cr(X,Y)+{rp.vae_chroma}*sin(2*PI*floor(Y/8)/8)'"
        )
```

- [ ] **Step 3: Use `sat_lift` for the saturation eq**

Locate:
```python
    fg_chain += (
        ",gblur=sigma=0.5"
        ",eq=saturation=0.97:brightness=0.003:gamma=0.997"
    )
```
Replace with:
```python
    fg_chain += (
        ",gblur=sigma=0.5"
        f",eq=saturation={rp.sat_lift}:brightness=0.003:gamma=0.997"
    )
```

- [ ] **Step 4: Insert bloom/glow after the overlay, feed into vignette**

Locate:
```python
    vf_parts.append(
        f"[blurred_border_bg][sharp_foreground_fg]overlay="
        f"x='(W-w)/2+{pan_off}*sin(t*{pan_freq})':"
        f"y='(H-h)/2+{pan_off}*sin(t*{pan_freq})'[merged]"
    )

    vf_parts.append(
        f"[merged]vignette=angle='PI/12+0.02*sin(t*{pan_freq})'[vignetted]"
    )
```
Replace with:
```python
    vf_parts.append(
        f"[blurred_border_bg][sharp_foreground_fg]overlay="
        f"x='(W-w)/2+{pan_off}*sin(t*{pan_freq})':"
        f"y='(H-h)/2+{pan_off}*sin(t*{pan_freq})'[merged]"
    )

    if profile.bloom_enable:
        b = rp.bloom
        vf_parts.append(
            f"[merged]gblur=sigma=10[bloomg];"
            f"[merged][bloomg]add={b:.3f}:{b:.3f}:{b:.3f}[bloomed]"
        )
        bloom_src = "[bloomed]"
    else:
        bloom_src = "[merged]"

    vf_parts.append(
        f"{bloom_src}vignette=angle='PI/12+0.02*sin(t*{pan_freq})'[vignetted]"
    )
```

- [ ] **Step 5: Sanity check the AIMIMIC graph string**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -c "from v7_pipeline.config import get_profile as g; from v7_pipeline.filters import build_filter_complex as bf, sample_random_params as s; fc,_=bf(g('AIMIMIC'), s(g('AIMIMIC'), seed=1)); print('bloom' , 'add=' in fc); print('sat', 'saturation=1.166' in fc); print('vae', '0.011*sin' in fc)"
```
Expected: `bloom True`, `sat True`, `vae True` (values scaled by range_scale 1.1: bloom 0.15→0.165? note bloom uses rng so may vary; sat 1.06*1.1=1.166; vae_chroma 0.01*1.1=0.011)

- [ ] **Step 6: Commit**
```bash
git add v7_pipeline/filters.py
git commit -m "feat(filters): apply AI-look bloom, sat lift, VAE chroma, stronger hqdn3d"
```

---

### Task 4: Expose `AIMIMIC` in the CLI (`cli.py`)

**Files:**
- Modify: `v7_pipeline/cli.py`

- [ ] **Step 1: Add the choice**

Locate:
```python
        choices=["SAFE", "BALANCED", "AGGRESSIVE"],
```
Replace with:
```python
        choices=["SAFE", "BALANCED", "AGGRESSIVE", "AIMIMIC"],
```

- [ ] **Step 2: Verify argparse accepts it**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -m v7_pipeline --profile AIMIMIC --help 2>&1 | findstr AIMIMIC
```
Expected: line listing `AIMIMIC` among choices.

- [ ] **Step 3: Commit**
```bash
git add v7_pipeline/cli.py
git commit -m "feat(cli): add AIMIMIC to --profile choices"
```

---

### Task 5: Unit tests for graph content (`tests/test_filters.py`)

**Files:**
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write the test file**

```python
from v7_pipeline.config import get_profile
from v7_pipeline.filters import build_filter_complex, sample_random_params


def test_aimimic_has_bloom_sat_lift_and_vae_chroma():
    prof = get_profile("AIMIMIC")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "add=" in fc, "bloom glow missing"
    assert f"saturation={rp.sat_lift}" in fc, "sat lift missing"
    assert f"cb='cb(X,Y)+{rp.vae_chroma}*sin" in fc, "vae chroma missing"


def test_safe_is_unchanged_no_bloom_default_sat():
    prof = get_profile("SAFE")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "add=" not in fc, "SAFE must not gain bloom"
    assert "saturation=0.97" in fc, "SAFE saturation must stay 0.97"
```

- [ ] **Step 2: Run the tests (expect PASS)**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -m pytest tests/test_filters.py -v
```
Expected: 2 passed.

- [ ] **Step 3: Commit**
```bash
git add tests/test_filters.py
git commit -m "test(filters): assert AIMIMIC graph content and SAFE regression"
```

---

### Task 6: End-to-end run on `input.mp4`

**Files:**
- None (verification only)

- [ ] **Step 1: Run the AIMIMIC profile on the user's video**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -m v7_pipeline --profile AIMIMIC --input "input/input.mp4"
```
Expected: completes; due to the source's corrupt (NaN) audio it will fall back to a **video-only** output in `output/` with `SHA-256: CHANGED` and `[OK] Validated: video-only (no audio)`. The video should look smoother/waxier with a faint block grid, soft glow, and slightly punchier color.

- [ ] **Step 2: Confirm SAFE still runs (regression smoke)**

Run:
```bash
cd "C:\Users\lenovo\OneDrive\Desktop\yt content hashing"
python -m v7_pipeline --profile SAFE --input "input/input.mp4"
```
Expected: completes as before; no bloom/glow applied (visually identical style to prior runs).

- [ ] **Step 3: Commit any final notes (optional)**

No code changes in this task; only verification. If you adjusted anything during debugging, commit it separately with a descriptive message.

---

## Self-Review Notes (done by planner)

- **Spec coverage:** AIMIMIC profile + new fields (Task 1) ✓; RandomParams population (Task 2) ✓; stronger hqdn3d, VAE chroma, sat_lift, bloom (Task 3) ✓; cli choice (Task 4) ✓; tests (Task 5) ✓; e2e (Task 6) ✓.
- **Placeholders:** none — every step has concrete code/commands.
- **Type consistency:** `rp.bloom`, `rp.sat_lift`, `rp.vae_chroma` declared in `RandomParams` (Task 2) and consumed in `build_filter_complex` (Task 3). `profile.bloom_enable`, `profile.bloom_strength`, `profile.sat_lift`, `profile.vae_chroma` declared in `Profile` (Task 1) and consumed in `filters.py`. Names match across tasks.
- **Regression safety:** SAFE/BALANCED/AGGRESSIVE keep `bloom_enable=False` (default) and `sat_lift=0.97` (default) and `vae_chroma=0.0` (default), so their graphs are byte-for-byte equivalent to before except for the stronger `hqdn3d` — but `hqdn3d` was already applied under `ai_plastic_smoothing`, which is `False` in SAFE and unchanged in BALANCED/AGGRESSIVE, so output is unchanged for them.
