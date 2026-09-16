# Design: TOON Profile (Stage 1 v7 pipeline)

**Date:** 2026-07-14
**Status:** Approved (design)
**Goal:** Add a `TOON` profile specialized for 2D/anime/rigged cartoon content:
flat color quantization, edge-preserving smoothing, line-art sharpening,
anime frame cadence, manga halftone, and vibrance — without organic grain or
plastic smoothing that degrade flat animation.

> NOTE (honest scope): As with other profiles, this restructures pixels/timing
> for a stylized "clean anime" look. It is not a guaranteed content-matching
> evader; the re-encode remains the real transform.

## Key technical decision
FFmpeg has **no `posterize` filter**. Cel-shading quantization is implemented
with `lutrgb` rounding: for L levels per channel,
`val = round(val*(L-1)/255)*255/(L-1)`. Fast, deterministic, no extra pass.

## Techniques (order matters)
Injected into `fg_chain` in this order:
1. **bilateral** (edge-preserving flat smoothing) — `bilateral=sigmaS=8:sigmaR=0.1`
   (flattens color regions, keeps line art). Gated by `toon_bilateral`.
2. **Cel-shading quantization** — `lutrgb` rounding with `toon_levels`
   (default 48). Gated by `toon_quantization`.
3. **deband** — `deband=1thr=0.02:2thr=0.02:3thr=0.02:4thr=0.02` cleans
   quantization banding. Gated by `toon_deband`.
4. **vibrance** — `vibrance=intensity=0.15` punchy anime color. Gated by
   `toon_vibrance`.
5. **Line-art sharpening (CAS)** — `cas=strength=<cas_strength>` (default 0.7).
   Gated by `toon_line_art`.
6. **Manga halftone** — `geq=lum='lum(X,Y)+<halftone_amp>*sin(X*0.8+Y*0.8)'`
   (default amp 1.5). Gated by `toon_halftone`.

**Anime cadence** applied in the video tail (after the merged/vignette/rotate
stages, on the final video chain before `[vout]` setpts):
`fps=15,minterpolate=fps=30:mi_mode=dup`. Gated by `toon_cadence`.

## Components

### config.py — new Profile fields (defaults keep other profiles unchanged)
```
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
```
TOON profile: all `toon_*` True; `grain_strength=0.0`;
`ai_plastic_smoothing=False`; `ai_mimicry=False`; `dct_geq=False`;
`bloom_enable=False`; `chromatic_shift=1`; `behavioral_pad=True`;
`range_scale=1.1`. Audio (phase/ultrasonic/echo/pitch) left on.

### filters.py
- Add to `RandomParams`: `toon_levels: int`, `cas_strength: float`,
  `halftone_amp: float`, `vibrance_intensity: float`.
- Populate both branches of `sample_random_params` from profile fields.
  `cas_strength`, `halftone_amp`, `vibrance_intensity` scale gently with
  `range_scale`; `toon_levels` stays an int (no scaling).
- Inject filters 1-6 into `fg_chain` (before `format=yuv420p[sharp_foreground_fg]`).
- Inject cadence into the final video chain, gated by `profile.toon_cadence`.

### cli.py
Add `"TOON"` to `--profile` choices.

### tests/test_filters.py
- Assert TOON graph contains `lutrgb`, `cas=strength=`, `bilateral`,
  `vibrance`, `geq=lum='lum(X,Y)+` halftone, and cadence
  `minterpolate=fps=30:mi_mode=dup`.
- Regression: SAFE/BALANCED graphs gain none of the toon filters.

## Data flow
`cli.main` -> `get_profile("TOON")` -> `sample_random_params` ->
`build_filter_complex` (emits toon filters + cadence) -> encode/validate/pad.
No orchestration change. Video-only NaN-audio fallback still applies.

## Testing
1. `python -m v7_pipeline --profile TOON --input <clip>` completes, output in
   `output/`, SHA-256 CHANGED.
2. Visual: flat colors preserved, lines crisp, subtle halftone, anime cadence.
3. Regression: `--profile SAFE` unchanged.

## Out of scope
- Two-pass palette re-indexing (palettegen/paletteuse).
- xBR/hqx upscaling.
- Vertical/Shorts aspect handling.
