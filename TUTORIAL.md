# How to Run This Project — Simple Tutorial

Bhai, this file explains **everything** in simple words: what the project does, the easy way to run it (Forge Studio), and the command-line / Colab ways if you need them. Follow step by step, no confusion.

---

## 1. What This Project Actually Does (30 seconds)

You give it a video → it re-encodes the video with tiny invisible changes → the output **looks the same to humans** but **looks different to YouTube's bots** (Content ID, duplicate detectors, AI embeddings).

This stops YouTube from thinking all your shorts are copies of each other (which caused your shadowban).

**Two stages:**
- **Stage 1** (works everywhere): ffmpeg tricks — noise, colour shifts, timing changes, audio tweaks. Runs on your normal PC.
- **Stage 1.5** (needs GPU): AI attack — uses a neural network (CLIP) to push your video's "AI fingerprint" away from the original. Runs on **Colab GPU** (free).

**The workflow problem this solves:** download from Insta/YT → CapCut to crop → export → laptop → Colab → hash → phone → re-edit. Forge Studio collapses all of that into one browser window.

---

## 2. Forge Studio — the easy way (start here)

This is the one-screen version: import, crop, colour, mask, text, hash, export. No Colab, no file shuffling.

### 2.1 Start it

Double-click **`start_studio.bat`**.

It finds a Python that has the right packages (it checks `py -3.13`, `3.12`, `3.11`, `3.10`, then `python`), installs `requirements.txt` automatically if nothing suitable is found, checks FFmpeg, then opens the studio in your browser.

You'll see the server logs in a window titled **"Forge Studio Server"**. Close that window to stop the studio.

> **Port already in use?** Another project on your machine may already own port 8000. Start the studio on a different port instead:
> ```powershell
> $env:FORGE_PORT=8010 ; python -m app.main
> ```
> Then open http://localhost:8010

### 2.2 The workflow

1. **Source tab** — drag in a video, browse for a file, or paste a YouTube/Insta/TikTok link (it downloads with `yt-dlp`).
2. **Crop & Ratio / Color / Mask Blur / Text Overlay** — make your edits. Everything previews live on the canvas.
3. **Anti-Detection tab** — check the green **"Hash engine ready"** line, pick a profile, then click **⚡ Run Content Hashing**.
4. A modal opens showing **real progress** (1% → 100%), the current stage, an elapsed timer, and the live engine log. You can hit *Continue in background* and keep editing — the job runs on the server.
5. When it finishes you get a **result card**: hash status, profile, resolution, duration, size, plus **Preview** and **Download**.
6. Click **Export Video** in the top bar. It's instant, because it hands back the file you already hashed.

### 2.3 Why hashing is a separate button

Hashing is the slow part (a full re-encode). Doing it as its own step means:
- You can see whether it actually worked before you upload.
- Export is instant instead of a long wait.
- If you change an edit afterwards, the card turns **amber** and says *"Your edits changed since this hash"* — Export will refuse and tell you to re-hash, instead of silently giving you a file that wasn't hashed with your current settings.

### 2.4 If something looks wrong

| What you see | What it means |
|---|---|
| Red **"Hash engine unavailable"** | The engine didn't load. Run `pip install -r requirements.txt` and restart. **Do not ignore this — hashing is not running.** |
| Amber **"Stage 1.5 (AI pass) — SKIPPED"** | Normal on your PC. See 2.5 below. |
| Hash button greyed out | No video loaded, or hashing is switched off, or the engine is unavailable. The hint text under the button says which. |
| Amber "edits changed" note | You edited something after hashing. Click **Re-run Content Hashing**. |
| `SHA-256: SAME` | The file didn't change — pick a stronger profile. |
| Export came out 9:16 but I picked Freeform | You moved the box without resizing it — Freeform doesn't reshape anything. See **2.6**. |
| Progress sits at 0% for a while | Normal at the start of a render. The stage line tells you which phase you're in. |
| `Audio encode failed — retrying...` | The encoder hit a bad audio stream and restarts from 0% with a simpler chain. Let it run. |

### 2.5 The Stage 1.5 (AI pass) is off on your PC — and that's expected

Under the engine status you'll see a **Stage 1.5 (AI pass)** box. On your machine it says **SKIPPED**.

Four profiles — **BALANCED, AGGRESSIVE, AIMIMIC, MAXIMUM** — are built to include a CLIP-based AI attack on top of the normal ffmpeg work. That attack needs two Python packages:

| Package | Needed for |
|---|---|
| `torch` | the neural network runtime |
| `open_clip` | the CLIP model that the attack pushes against |

Neither is installed for the Python the studio uses, so **those four profiles still hash your video normally — they just skip the AI part.** They are marked with a small **AI** tag in the profile list, and the ones being skipped are highlighted amber so you can see at a glance.

**What to do about it:** nothing, if you're happy. The ffmpeg stage is what protects you day to day. When you want the AI pass on a video that really matters, run it on **Colab** (section 5) — that's what the GPU is for.

> If you want to try it locally anyway: `pip install open_clip_torch` would let it run, but on CPU it is extremely slow (the AI pass re-encodes the whole video). For anything longer than a few seconds, use Colab.

### 2.6 Cropping — how to know what you'll actually get

Two things about the crop box trip people up, so read this once:

**1. Everything outside the white box is blacked out — that's what gets cut.** The preview shows **only** the part you're keeping. The black area around it is thrown away on export, so what you see inside the box is exactly your video. Nothing outside it will survive.

**2. The badge shows the exact size you'll get.** Top-left of the box, e.g. `Custom · 204×580`. That's the real output resolution, in pixels. Check it before exporting — if it doesn't say what you expect, the crop isn't what you think it is.

> **Picking "Freeform" does not reshape the box.** It only unlocks the aspect ratio so you *can* reshape it. If you click Freeform and then just drag the box around, the **shape stays exactly as it was** — the badge will still read `Custom · 384×684`, which is 9:16.
>
> To actually change the shape, grab one of the **8 white handles** on the box edges/corners and drag. Or type exact numbers into Width / Height / Offset X / Offset Y on the left.

**New videos start uncropped.** The box covers the whole frame and the badge shows something like `Custom · 1280×720`. Nothing is thrown away until you ask for it. For a vertical short, click **9:16** and you get a tall centred slice in one click — the badge will show the new size immediately.

> If the badge still shows your source's full size after you pick a ratio or drag a handle, the crop didn't change. Trust the badge, not the shape of the box.

**3. The hash engine rescales your crop — same shape, different pixel count.** The v7 engine normalises every output to a standard delivery size: **1280 px wide** if your crop is portrait/square, or **720 px tall** if it's landscape. The *shape* is always preserved, but the numbers change:

| Your crop | Hashed output | Shape |
|---|---|---|
| 182×542 (portrait) | 1280×3810 | same ✓ |
| 300×600 (portrait) | 1280×2560 | same ✓ |
| 900×300 (landscape) | 2160×720 | same ✓ |
| 405×720 (9:16) | 1280×2276 | same ✓ |

So don't be alarmed if the hashed video isn't the same pixel size as your crop — check the **shape**, not the numbers. One caveat: a *small* crop gets upscaled a long way (182 px wide becomes 1280), which looks soft. Crop reasonably large regions and you'll be fine.

| You want | Do this |
|---|---|
| The whole frame, no crop | **Reset Crop** (this is also the default when a video loads) |
| A standard shape | Click **9:16**, **1:1**, **4:5**, **16:9** or **4:3** |
| A custom rectangle | Click **Freeform**, then drag the **white handles** to resize, then drag the box body to position it |
| An exact size | Click **Freeform**, then type Width/Height/Offset X/Offset Y |

### 2.7 Storage — keeping your disk under control

Every source you import and every video you hash stays on disk, in `app/uploads/` and `app/outputs/`. A 4K source is 30 MB+, so it adds up quickly.

The **Storage** panel at the bottom of the **Source** tab shows:

- Total size used by uploads and by outputs
- Every file with its size
- A **×** button to delete a single file
- **Clear all outputs** / **Clear all uploads** for a full clean-up

Files tagged **IN USE** back your current hashed result — deleting one means you'll need to re-hash before you can export again (the studio will tell you).

**Nothing is ever deleted automatically.** Every delete asks you to confirm first, and the panel only ever touches those two folders.

> Tip: once you've exported a video, you can safely clear the uploads. The files in `outputs/` are what you actually upload to YouTube.

### 2.8 Check it still works

With the studio running:
```powershell
python tools\smoke_test.py 8000
```
It drives the whole flow (upload → refuse-export-before-hash → hash → poll → reuse → staleness → download) and prints PASS/FAIL for each step.

---

## 3. The 6 Profiles (which one to pick?)

A "profile" is just a preset — how strong the changes are.

| Profile | Strength | ML Stage? | Use when |
|---------|----------|-----------|----------|
| **SAFE** | Lowest | ❌ Off | You're scared of quality loss. Barely changes anything. |
| **BALANCED** | Medium | ✅ On | **Default. Start here.** Good mix of safety + strength. |
| **AGGRESSIVE** | High | ✅ On | BALANCED wasn't enough, videos still getting flagged. |
| **AIMIMIC** | High | ✅ On | Makes video look "AI-generated style" (bloom, saturation lift). |
| **TOON** | Medium | ❌ Off | For cartoon/anime content specifically. |
| **MAXIMUM** | Maximum | ✅ On | Nuclear option. Everything turned on. Try last. |

**Rule:** Start with **BALANCED**. If YouTube still clusters your videos, move up to AGGRESSIVE, then MAXIMUM.

---

## 4. Command line (batch / automation)

The pipeline still works on its own, without the studio. Open PowerShell in the project folder:

```powershell
# Simplest - uses the newest video in input/
python -m v7_pipeline

# Pick a specific video
python -m v7_pipeline --input "input\myvideo.mp4"

# Pick a profile + specific video
python -m v7_pipeline --input "input\myvideo.mp4" --profile AGGRESSIVE

# Process a whole folder (batch)
python -m v7_pipeline --batch "input" --profile BALANCED
```

| Option | What it does |
|--------|--------------|
| `--profile SAFE` | Use a different profile |
| `--seed 42` | Same seed = same output (for testing). No seed = random every time |
| `--no-pad` | Skip the random-bytes padding step |
| `--skip-existing` | In batch mode, skip videos already processed |
| `--out "myfolder"` | Save outputs somewhere else |

Output goes to the `output/` folder, named like `myvideo_v7_20260809_143022.mp4`.

**Important:** Locally, the ML stage (Stage 1.5) will **silently skip** because you don't have torch/GPU. That's normal — Stage 1 alone still works. The line `[OK] ML adversarial pass applied` will NOT appear locally. It only appears on Colab.

---

## 5. Running on COLAB (free GPU — for the AI stage)

This is where the **full power** is. Colab gives you a free GPU so the ML stage actually runs.

### 5.1 Steps

1. Go to https://colab.research.google.com
2. **File → Upload notebook** → select `yt content hashing/notebooks/ml_stage_colab.ipynb`
3. **Runtime → Change runtime type → GPU (T4)** → Save
4. Run the cells **one by one, top to bottom**:

| Cell | What it does | What you do |
|------|--------------|-------------|
| **Cell 2** (GPU check) | Checks you got a GPU | Just run it. Should print `cuda available: True` |
| **Cell 3** (install) | Installs torch, open_clip, ffmpeg | Just run it. Wait ~2 min |
| **Cell 4** (load project) | Gets your code onto Colab | It asks you to **upload a zip** of the project folder. Zip it on your PC first, then upload |
| **Cell 5** (upload video) | Gets your video onto Colab | Run it, then upload your video file |
| **Cell 6** (run pipeline) | **Actually processes your video** with BALANCED + ML stage | Just run it. Wait a few minutes |
| **Cell 7** (metrics) | Shows you the proof it worked | Read the numbers (below) |
| **Cell 8** (download) | Downloads the result to your PC | Run it, browser downloads the file |

### 5.2 How to read the metrics (Cell 7)

```
mean SSIM over 24 sampled frames: 0.9856  (floor 0.98)
CLIP cosine similarity original vs output: 0.7231
cosine distance: 0.2769  (higher = further from source embedding)
```

- **SSIM ≥ 0.98** → ✅ Good. Means humans can't see the difference. If it drops below 0.98, the system auto-reduces the attack strength.
- **Cosine distance** → higher = better. This is how far the AI fingerprint moved. `0.0` = identical, `1.0` = completely different. Anything above ~0.15 is meaningful movement.

---

## 6. Which Should I Use?

| | Forge Studio | Command line | Colab (GPU) |
|---|---|---|---|
| Cropping / text / mask / colour | ✅ Built in | ❌ | ❌ |
| Stage 1 (ffmpeg tricks) | ✅ | ✅ | ✅ |
| Stage 1.5 (AI attack) | ❌ (no GPU) | ❌ (no GPU) | ✅ |
| Speed | Fast | Fast | Medium |
| Batch a folder | ❌ | ✅ | ❌ |

**Recommendation:** Use **Forge Studio** for everyday work — it does everything except the GPU stage. Use **Colab** when you want the extra ML protection on a video that matters.

---

## 7. Common Problems

| Problem | Fix |
|---------|-----|
| `FFmpeg not found` | `winget install Gyan.FFmpeg`, then reopen your terminal |
| `Address already in use` on port 8000 | Use `$env:FORGE_PORT=8010 ; python -m app.main` |
| Red "Hash engine unavailable" | `pip install -r requirements.txt`, then restart |
| `No videos in input` | Put a video file in the `input/` folder |
| `[ERR] Validate: ...` | Source video might be corrupt — try a different file |
| Colab says `cuda available: False` | Runtime → Change runtime type → GPU |
| `ml stage skipped: torch/device unavailable` | Normal on local PC. Only works on Colab GPU |
| Output looks glitchy | You used too strong a profile — drop down (MAXIMUM → BALANCED) |
| Hashing takes a long time | Normal — it's a full re-encode. Watch the progress bar; a 3s clip takes ~60-80s |

---

## 8. Quick Cheat Sheet

```powershell
# THE EASY WAY
#   double-click start_studio.bat  ->  http://localhost:8000

# Studio on a different port
$env:FORGE_PORT=8010 ; python -m app.main

# Verify the studio end to end (studio must be running)
python tools\smoke_test.py 8000

# COMMAND LINE
python -m v7_pipeline                                          # newest video, BALANCED
python -m v7_pipeline --input "input\video.mp4" --profile AGGRESSIVE
python -m v7_pipeline --batch "input" --profile BALANCED
python -m v7_pipeline --input "input\video.mp4" --seed 42       # reproducible

# TESTS
cd "yt content hashing" ; python -m pytest -q                   # 43 tests

# COLAB
#   upload yt content hashing/notebooks/ml_stage_colab.ipynb, set GPU runtime, run cells
```

---

## 9. The Full Flow (diagram)

```
Your video (file or URL)
    │
    ▼
┌──────────────────────────────────────────┐
│  FORGE STUDIO (browser, localhost)       │
│  crop · trim · colour · mask · text      │
└──────────────────────────────────────────┘
    │  click "Run Content Hashing"
    ▼
┌──────────────────────────────────────────┐
│  STAGE 1 (ffmpeg) — runs everywhere      │
│  noise, colour shift, timing, audio      │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│  STAGE 1.5 (AI) — Colab GPU only         │
│  CLIP adversarial attack                 │
│  (auto-skipped locally)                  │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│  Validate + random padding               │
│  SHA-256 check: CHANGED ✅               │
└──────────────────────────────────────────┘
    │  click "Export Video"
    ▼
app/outputs/  →  upload to YouTube
```

---

Bas itna hi hai. Start with **BALANCED** in Forge Studio, check the progress bar finishes and the result card says **CHANGED**, then export. If YouTube still gives trouble, move up to AGGRESSIVE or MAXIMUM. Koi problem aaye toh the "Common Problems" table dekh lo.
