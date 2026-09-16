# Design: AIMIMIC Profile (Stage 1 v7 pipeline)

**Date:** 2026-07-13
**Status:** Approved (design)
**Goal:** Add a dedicated `AIMIMIC` profile that stylizes output to look
"AI-generated" (stronger-but-subtle): waxy/plastic texture, faint 8x8 VAE
block grid, soft bloom/glow, slight saturation lift, synthetic background flow.
This is a *cosmetic / creative* effect, not a content-matching evader.

> NOTE (honest scope): Making a video "look AI" does not make fingerprinting
> (Content ID / pHash) treat it as AI or spare it. Perceptual fingerprinting
> matches pixels/audio regardless of style. The re-encode remains the real
> evasion mechanism. AIMIMIC is for visual stylization only.

## Approach
Approach A (chosen): enable all existing `ai_*` / `vit_*` / `dct_geq` flags,
tune them stronger-but-subtle, and add 2-3 new cosmetic "sheen" filters, reusing
the existing `filters.build_filter_complex` graph. Low risk, stays in-pattern.

## Components

### 1. `config.py` — new Profile
Add `AIMIMIC` to `PROFILES` dict (consumed by existing `get_profile`).

New `Profile` fields (frozen dataclass, safe defaults):
- `bloom_strength: float = 0.15`  # screen-blend glow amount
- `sat_lift: float = 1.06`        # eq saturation multiplier (AI "punchy" grade)
- `vae_chroma: float = 0.01`      # per-block chroma offset for blocky tell

AIMIMIC settings:
- `ai_mimicry=True`, `ai_vae_grid_strength=0.08` (was 0.03)
- `ai_plastic_smoothing=True`, `ai_optical_flow=True`, `ai_bg_morph=True`
- `dct_geq=True`, all `vit_*` = True
- `chromatic_enable=True`, `hue_spatial_drift=True`, `grain_strength=3.0`
- `range_scale=1.1`, `behavioral_pad=True`, `behavioral_pad_max_bytes=4096`
- `pan_enable`, `warp_strength`, `micro_rotation_deg` left at base values

### 2. `filters.py` — graph enhancements
Prerequisite: add `bloom`, `sat_lift`, `vae_chroma` fields to the
`RandomParams` dataclass and populate them in `sample_random_params` from the
profile fields (`bloom_strength`, `sat_lift`, `vae_chroma`), honoring
`profile.randomize` scaling. These feed the filters below.

In `build_filter_complex` (keep `include_audio` param and video-only path):

- **VAE grid** (`ai_mimicry` branch): use `rp.ai_vae` for 8x8 `geq` block
  luminance; add faint per-block chroma offset scaled by `rp.vae_chroma`.
- **Plastic smoothing**: when `ai_plastic_smoothing`, use stronger
  `hqdn3d=luma_spatial=8:chroma_spatial=6:luma_tmp=10:chroma_tmp=8`.
- **Bloom/glow** (new): after foreground chain, build
  `split=2`, blur one copy, `gblur`, `threshold`, then `add` (screen-ish)
  blended by `rp.bloom`, producing soft synthetic halo. Append to `vf_parts`.
- **Saturation lift** (new): replace hardcoded `eq=...saturation=0.97...`
  with `saturation=rp.sat_lift`.
- All changes gated by the relevant profile flags; non-AIMIMIC profiles
  (SAFE/BALANCED/AGGRESSIVE) must produce identical output to before
  (regression-safe: bloom/sat_lift only apply when enabled by profile).

### 3. `cli.py`
Add `"AIMIMIC"` to `--profile` `choices` list.

### 4. Validation / error handling
Unchanged. `validate_output(require_audio=False)` and the no-audio NaN
fallback in `stage1.process_video` remain in force (matters for corrupt
`input.mp4` audio).

## Data flow
`cli.main` -> `get_profile("AIMIMIC")` -> `sample_random_params` ->
`build_filter_complex(profile, rp)` (now emits bloom + sat-lift + stronger
VAE/grid) -> `encode_with_fallback` -> validate + pad. No change to
orchestration.

## Testing
1. `python -m v7_pipeline --profile AIMIMIC --input input/input.mp4`
   - Expect completion, video-only output (corrupt source audio), file in
     `output/`, SHA-256 CHANGED.
2. Visual check: output should look smoother/waxier with faint block grid +
   soft glow, still watchable (stronger-but-subtle).
3. Regression: `--profile SAFE` and `--profile BALANCED` outputs must be
   unchanged vs. prior runs (no bloom/sat applied).

## Out of scope
- No new encoder/audio changes.
- No Content-ID evasion guarantees.
- Shorts/vertical (9:16) handling not added here.
