# V7 Stage 1 Robust Pipeline — Design Spec

**Date:** 2026-07-10 (continued 2026-07-11)  
**Status:** Approved direction (Approach B, Stage 1 only)  
**Source of truth after implement:** `v7_pipeline/` package + thin `V7_Combined_local.py` CLI  

---

## 1. Problem & goals

### Problem

`V7_Combined_local.py` is a ~790-line monolith that works for single-file Stage 1 hashing (visual + audio re-encode) but is hard to harden:

- One giant `process_video` mixes filter math, encoder choice, progress, batch, and cleanup
- Failures (NVENC mid-run, unplayable output, temp leftover) are inconsistent
- No intensity profiles; every run uses the full heavy stack
- Stage 2 metadata lives only in `meta_data_hashing (1).ipynb` and must stay **out** of Stage 1

### Goals

1. **Reliability first** — playable outputs or explicit failure; no hangs; temp always cleaned
2. **Stage 1 only** — re-encode that changes structure/hash; **no** metadata inject, XMP, device spoof, Studio helpers
3. **Local Windows only** — `input/` → `output/`; `%TEMP%/hasher_v7` for work files
4. **Modular + profiles** — SAFE / BALANCED / AGGRESSIVE over the **existing** filter families
5. **Batch resume** — sequential multi-file; one fail does not kill the batch

### Explicit non-goals

| Out of scope | Why |
|--------------|-----|
| Stage 2 / metadata in this package | User requirement: separate tool only |
| Drive/Colab paths in local package | Windows-local focus |
| Web UI, multi-GPU queue, PyPI packaging | Overkill |
| New experimental filters in Phase 1 | Harden + reorganize existing stack first |
| Full notebook rewrite in Phase 1–2 | Local package is source of truth; notebook may lag |

`meta_data_hashing (1).ipynb` remains the separate Stage 2 path. Stage 1 may **print a reminder** that metadata is separate; it must **never** call Stage 2.

---

## 2. Architecture & file layout

```
yt content hashing/
├── V7_Combined_local.py          # thin CLI entry (compat wrapper)
├── v7_pipeline/                  # Stage 1 only
│   ├── __init__.py
│   ├── __main__.py               # python -m v7_pipeline
│   ├── config.py                 # constants + SAFE / BALANCED / AGGRESSIVE
│   ├── encoder.py                # NVENC / libx264, progress, fallback
│   ├── filters.py                # vf/af graph from profile + rng
│   ├── stage1.py                 # process_video: copy → encode → validate → out
│   ├── validate.py               # ffprobe: streams, duration, playable
│   ├── batch.py                  # sequential batch, skip/resume
│   └── paths.py                  # input/output/%TEMP%/hasher_v7
├── input/
├── output/
├── meta_data_hashing (1).ipynb   # SEPARATE — never imported by v7_pipeline
└── docs/superpowers/specs/
    └── 2026-07-10-v7-stage1-robust-design.md
```

**Not in this package:** `stage2.py`, metadata inject, XMP, container atom rewrites, upload helper generation.

### Module responsibilities

| Module | Owns | Does not own |
|--------|------|--------------|
| `config` | Toggles, intensity profiles, encoder defaults | FFmpeg execution |
| `filters` | `filter_complex` strings from profile + random seed | Encoder choice |
| `encoder` | NVENC/libx264 detect, cmd assembly, progress, fallback | Filter math |
| `stage1` | Temp copy, encode, optional EOF pad, cleanup | Metadata |
| `validate` | Post-encode ffprobe/size checks; fail closed | Processing |
| `batch` | Discover inputs, sequential loop, skip/resume, summary | Filter details |
| `paths` | `IN` / `OUT` / `TEMP` on Windows | Business logic |

### Data flow (single video)

```
1. resolve profile (default BALANCED) + paths
2. copy input → %TEMP%/hasher_v7/
3. build filter graph + encode (NVENC → fallback libx264 on hard fail)
4. validate (video + audio streams, duration within tolerance, size > 0)
5. copy to output/<stem>_v7_<ts>.mp4
6. optional light EOF pad (file hash only — not metadata atoms)
7. cleanup temp (success and failure); return path or None
8. print reminder: metadata is separate (Stage 2 notebook)
```

### Compatibility

- Keep `V7_Combined_local.py` as a short wrapper so `python V7_Combined_local.py` still works
- Keep existing `input/` and `output/` folders
- Preserve known-good filter pad names (`bg_stream`, `fg_stream`, etc.) from current script

---

## 3. Profiles, CLI, reliability

### Profiles (filter intensity only — not metadata)

Same filter *families* as current `V7_Combined_local.py`. Profiles only enable/disable expensive steps and scale ranges.

| Profile | Intent | Notable knobs (illustrative) |
|---------|--------|------------------------------|
| **SAFE** | Faster, cleaner look | `minterpolate` off; heavy `geq` lighter/off; AI mimicry reduced; grain low |
| **BALANCED** | Current V7 default behavior | Match today’s flags and random ranges |
| **AGGRESSIVE** | Stronger transform, slower | Full stack; wider random ranges; full ViT/AI layers |

`PERCEPTUAL_WARP_ENABLE` stays **false** by default (perspective + expression support is unsafe / unproven). Document disabled flags in `config.py`.

### CLI examples

```text
python V7_Combined_local.py
python -m v7_pipeline
python -m v7_pipeline --profile SAFE
python -m v7_pipeline --input path\to\file.mp4 --profile BALANCED
python -m v7_pipeline --batch input\my_batch --skip-existing
python -m v7_pipeline --profile AGGRESSIVE --no-pad
```

**No `--stage2` flag** in this design.

Suggested flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `--profile` | `BALANCED` | SAFE / BALANCED / AGGRESSIVE |
| `--input` | latest in `input/` | Single file path |
| `--batch` | off | Process all videos in folder |
| `--skip-existing` | off | Skip if matching stem already has a `_v7_` output (batch) |
| `--out` | `./output` | Output directory |
| `--no-pad` | pad on | Disable EOF random pad |
| `--seed` | random | Reproducible RNG for filter params |

### Reliability rules (Phase 1 priority)

1. **Encoder:** live NVENC test once per process; on fail use libx264 without leaving half-written state
2. **Validate before “OK”:** ffprobe has video + audio; duration within tolerance of source (e.g. ±2% or ±0.5s, whichever larger); size > 0
3. **Cleanup always:** temp files removed on success *and* failure (`try` / `finally`)
4. **Batch:** one video at a time; one failure does not abort the batch; end summary (`OK` / `ERR` / `SKIP` counts)
5. **Logging:** clear `[OK]` / `[ERR]` / `[SKIP]` with encoder, profile, seconds, output path
6. **Filter safety:** keep known-good pad names; no perspective-with-`t` unless proven; document disabled flags

### Success criteria

- Batch of N files: playable outputs or explicit per-file fail; no hang
- Re-run same input → new timestamped name, different file hash
- SAFE clearly faster / cleaner than AGGRESSIVE on the same machine
- Zero intentional metadata writes in Stage 1 (aside from FFmpeg defaults on re-encode)
- Stage 1 never imports or shells into Stage 2 notebook

---

## 4. Filter & encoder behavior (port from current script)

Phase 1 **ports** existing behavior into modules; it does not invent a new transform stack.

### Video pipeline (families)

1. Scale / split → `bg_stream` / `fg_stream`
2. Background: downscale, optional `minterpolate` (AGGRESSIVE/BALANCED if AI optical-flow on), blur, upscale
3. Foreground: lens warp, colorchannelmixer, chromatic shift, smartblur, optional plastic smooth, grain, optional VAE geq, crop/pan, gblur/eq, hue drift, colorbalance, lutyuv, unsharp
4. Overlay + vignette + micro-rotate
5. JND eq + DCT-style `geq`
6. ViT stack: noise / flicker / crop-pad shift / tmix (profile-gated)
7. `setpts` desync / PTS jitter

### Audio pipeline (families)

1. Pitch shift via `asetrate` + `atempo`
2. EQ notches
3. Optional comb filter (`aecho`)
4. Optional phase scramble (`afftfilt`) + ultrasonic mix path as in current script

### Encoder

- Prefer `h264_nvenc` after live test encode; else `libx264`
- Preserve B-frame / ref / x264-params randomization for libx264 path
- Progress via `-progress pipe:1` + tqdm
- Hard NVENC failure mid-run: retry once with libx264 on same filter graph (current behavior), then fail closed

### Optional EOF pad

- Random 0..N bytes appended after successful encode **only if enabled**
- Purpose: change file hash only; **not** container metadata rewrite
- Off via `--no-pad` or profile config

---

## 5. Phased implementation plan

| Phase | Deliverable | Exit criteria |
|-------|-------------|----------------|
| **P0 — Scaffold** | Create `v7_pipeline/` package skeleton; thin CLI wrapper that still calls old logic or stubs | `python -m v7_pipeline --help` works |
| **P1 — Port + reliability** | Move detect_encoder, progress, process_video, paths into modules; add `validate.py`; try/finally cleanup; structured logs | Single file: playable out or clear ERR; temp empty after run |
| **P2 — Profiles** | SAFE / BALANCED / AGGRESSIVE in `config.py` + `filters.py` gating | Same input, three profiles, different speed/look; BALANCED ≈ today’s output character |
| **P3 — Batch polish** | `batch.py` skip-existing, continue-on-error, end summary; CLI flags | Batch of 3+ files with mixed success reported correctly |
| **P4 — Hardening** | Document disabled flags; smoke-test script; optional seed; fail messages list encoder + last FFmpeg stderr tail | Smoke tests pass on sample in `input/` |

Order of implementation for agents: **P0 → P1 → P2 → P3 → P4**. Do not add Stage 2 in any phase of this design.

### Migration strategy

1. Extract pure functions first (`detect_encoder`, `get_duration`, filter builders) without changing defaults
2. Point `V7_Combined_local.py` at package entry so daily use does not change
3. Delete or shrink in-place monolith only after P1 smoke pass
4. Keep notebook files on disk; no requirement to sync them in this design

---

## 6. Testing strategy

### Smoke (manual / scripted)

| Test | Expect |
|------|--------|
| Latest video in `input/`, default profile | Output under `output/`, playable, duration ~ source |
| `--profile SAFE` | Completes faster than BALANCED; playable |
| `--profile AGGRESSIVE` | Completes; playable |
| Re-run same file | New timestamp; SHA-256 ≠ input and ≠ previous out |
| NVENC unavailable (or forced x264) | Falls back; still succeeds |
| Corrupt / missing input | `[ERR]`, no crash, temp cleaned |
| Batch 2+ files, one forced fail | Other files still processed; summary counts correct |

### Validation rules (automated in `validate.py`)

- At least one video stream and one audio stream
- `format.duration` within tolerance of source
- Output file size > 0 and preferably > small threshold (e.g. 10 KB)
- Optional: ffprobe exit 0 on output path

### Non-tests (out of scope)

- YouTube upload / Content ID outcome
- Metadata atom contents (Stage 2)
- Visual quality MOS scores (human judgment only)

---

## 7. Logging & UX conventions

```
[ ] Checking FFmpeg...
[OK] Encoder: nvenc (...)
[ ] Profile: BALANCED
[ ] Processing: example.mp4 (12.3s, 45.1 MB)
[OK] Encode 18.2s → output\example_v7_20260711_....mp4
[!] Metadata is separate — use meta_data_hashing notebook if needed.
```

Batch end:

```
[SUMMARY] OK=2 ERR=1 SKIP=0  total=3
```

Never print secrets. Never claim “undetectable” or guarantee platform outcomes.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Filter graph regression on split | Port graph string-for-string first; profiles only gate known flags |
| `minterpolate` / heavy `geq` slow or OOM | SAFE disables; document cost |
| Perspective filter expressions | Keep off (`PERCEPTUAL_WARP_ENABLE = False`) |
| OneDrive path / lock issues | Prefer `%TEMP%` work dir; copy then process |
| Silent unplayable “success” | `validate` fail-closed before final move |

---

## 9. Locked decisions (session history)

| Decision | Choice |
|----------|--------|
| Overall approach | **B** — modular local pipeline |
| Stage 2 in Stage 1 | **No** — metadata stays separate |
| Runtime | Local Windows only |
| Profiles | SAFE / BALANCED / AGGRESSIVE |
| Default profile | BALANCED (current V7 character) |
| Phase priority | Reliability → modular port → profiles → batch polish |
| Notebook | Secondary; do not block on Colab parity |

---

## 10. Next step after this spec

1. User reviews this file and requests tweaks if any  
2. Implementation plan: `docs/superpowers/plans/2026-07-11-v7-stage1-robust.md` (task checkboxes)  
3. Implement P0–P4 against the plan; no Stage 2 code  
