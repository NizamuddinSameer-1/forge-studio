# ⚡ Forge Studio & V7 Content Hashing Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg?logo=ffmpeg)](https://ffmpeg.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Forge Studio** is a full-stack, local video editing micro-studio and algorithmic content hashing system. Engineered for creators, media curators, and automation workflows repurposing short-form video (YouTube Shorts, Instagram Reels, TikTok) while defeating duplicate clustering, perceptual fingerprinting, and automated algorithmic suppression.

---

## 🚀 Key Highlights

- 🎬 **Integrated Web Micro-Studio**: Clean, responsive browser-based editing suite running on FastAPI + Vanilla JS.
- 📥 **Instant URL Ingestion**: Download high-res clips directly from YouTube, Instagram, and TikTok via integrated `yt-dlp`.
- ✂️ **CapCut-Style Canvas Cropper**: Dimmed cut-away preview, center/edge snap guides, anchored 8-handle resize, aspect presets (`9:16`, `1:1`, `4:5`, `16:9`, `4:3`, freeform) with a live badge showing crop size → **exact export size**.
- 📐 **Exact Export Canvas**: Every export lands on an exact platform canvas — a `9:16` crop exports at exactly `1080×1920` (or `720×1280`, or the raw crop in `Source` mode). The hash engine keeps those dimensions instead of re-scaling them.
- 🎨 **Full Color Grading Suite**: Brightness, exposure, contrast, saturation, highlights, shadows, temperature, tint, sharpen, filmic fade, vignette, and film grain — live preview matched to the FFmpeg render.
- 🎭 **Multi-Mask Blur & Pixelate**: Unlimited blur or mosaic boxes with 8-handle resize and quick-position presets to hide watermarks, logos, and handles.
- ✍️ **Pro Text Overlays**: Multi-line captions, per-layer show-from/hide-after timing, fonts (Arial / Arial Bold / Arial Black / Impact), stroke, background box, and emoji fallback.
- 🔬 **V7 Content Hashing Engine**: Multi-stage algorithmic stream modification designed to defeat automated Content ID and duplicate detection algorithms while preserving visual fidelity ($SSIM \ge 0.98$).
- 🤖 **Adversarial ML Stage (Stage 1.5)**: Deep embedding disruption using CLIP / Vision Transformer adversarial passes to break semantic clustering.
- 📊 **Live Pipeline Stepper**: Watch exactly which stage your video is in — Render edits → V7 hash encode → Finalize — with real percentage progress, not a fake spinner.
- 🧹 **Storage Management Hub**: Built-in disk usage monitoring, upload/render management, and one-click auto-cleanup.
- ⚡ **One-Click Startup**: Auto-detecting Windows batch launcher (`start_studio.bat`) that resolves Python environments and required packages automatically.

---

## 🏛️ System Architecture

```
Forge Studio Workstation
├── Web Micro-Studio UI (app/static/)
│   ├── Video Canvas & CapCut-style Cropper (snap guides, exact export badge)
│   ├── 12-Control Color Suite, Multi-Mask Blur/Pixelate, Timed Text Layers
│   ├── Live Pipeline Stepper + Real Progress
│   └── Storage Management Dashboard
│
├── Studio Backend Engine (app/main.py, app/editor_engine.py)
│   ├── REST Endpoints (Upload, URL Download, Render, Storage)
│   ├── FFmpeg Filter Graph Builder (exact export canvas, cover-fit)
│   ├── Structured Stage/Progress Reporting ([STAGE k/N], RENDER_PROGRESS)
│   └── Hashing Pipeline Bridge
│
└── V7 Content Hashing Engine (yt content hashing/v7_pipeline/)
    ├── Stage 1: Classical Bitstream & Perceptual Hashing
    │   ├── Micro-geometry shifts (crop / scale / sub-pixel offset)
    │   ├── Frame cadence variations & temporal jitter
    │   ├── Dynamic audio EQ, harmonic injection & pitch micro-modulations
    │   └── Profiles: SAFE, BALANCED, AGGRESSIVE, MAXIMUM, TOON, AIMIMIC
    │
    └── Stage 1.5: Adversarial ML Engine (CLIP / ViT Perturbation)
        ├── Disruption of neural semantic clustering
        └── Graceful CPU/GPU fallback
```

---

## 🛠️ Installation & Setup

### Prerequisites
1. **Python 3.10+** (Python 3.11 or 3.12 recommended)
2. **FFmpeg**: Must be installed and accessible on your system `PATH`.
   - Windows (winget): `winget install Gyan.FFmpeg`
   - Linux (apt): `sudo apt-get install ffmpeg`
   - macOS (brew): `brew install ffmpeg`

### Quick Start (Windows)
Double-click `start_studio.bat` or run:
```bat
start_studio.bat
```
The launcher will:
1. Probe for an active Python interpreter with required dependencies.
2. Install any missing packages automatically.
3. Check for FFmpeg availability.
4. Launch the local web server at `http://localhost:8000`.

### Manual Installation
```bash
# Clone the repository
git clone https://github.com/NizamuddinSameer-1/forge-studio.git
cd forge-studio

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start the studio web application
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at `http://127.0.0.1:8000` to access Forge Studio.

---

## 🎛️ V7 Content Hashing Profiles

| Profile | Target Platforms | Modifications Applied | Visual Quality |
|---|---|---|---|
| **SAFE** | Low-risk reposting / slight variants | Subtle micro-geometry adjustments, gentle audio EQ | SSIM > 0.99 (Virtually undetectable) |
| **BALANCED** | Standard YouTube Shorts / Reels | Geometric shifts, chromatic aberration, audio harmonic shifts | SSIM ~ 0.98 (Crisp & natural) |
| **AGGRESSIVE** | High-scrutiny viral clips | Advanced temporal cadence shifts, grain injection, frequency masking | SSIM ~ 0.96 (High protection) |
| **MAXIMUM** | Stringent duplicate detection environments | Full composite pipeline + heavy grain/chroma/timing | Strongest non-destructive protection |
| **TOON** | Anime, cartoons, stylized content | Frame rate cadence adaptation (12/24 fps), edge enhancement, halftone | Optimized for animated media |
| **AIMIMIC** | AI-generated content mimics | Synthetic artifact injection mimicking Gen-AI video models | Simulates fresh AI generation |

---

## 📁 Repository Structure

```
forge-studio/
├── app/
│   ├── main.py                 # FastAPI application routes & REST endpoints
│   ├── editor_engine.py        # FFmpeg video processing & exact-canvas export pipeline
│   ├── static/
│   │   ├── index.html          # Single-page studio interface
│   │   ├── css/
│   │   │   ├── studio.css      # Base dark-mode UI styling
│   │   │   └── studio_v21.css  # v2.1 additions (crop guides, masks, stepper)
│   │   ├── fonts/              # Bundled TrueType fonts for FFmpeg drawtext
│   │   └── js/
│   │       ├── app.js          # Master controller: state, API polling, stepper
│   │       ├── canvas_cropper.js # Snap guides, dimmed cut-away, export badge
│   │       ├── color_grading.js  # 12-control color suite + live preview
│   │       ├── mask_overlay.js   # Multi-mask blur/pixelate manager
│   │       ├── text_overlay.js   # Multi-line, timed text layers
│   │       └── timeline.js       # Scrubber & trim-range controller
│   ├── uploads/                # Incoming media staging (gitignored)
│   └── outputs/                # Rendered exports (gitignored)
│
├── yt content hashing/
│   ├── v7_pipeline/            # V7 Algorithmic Content Hashing Engine
│   │   ├── cli.py              # CLI entry point
│   │   ├── config.py           # Engine configuration & profiles
│   │   ├── filters.py          # FFmpeg complex filter graphs
│   │   ├── encoder.py          # Multi-pass encoding routines
│   │   ├── stage1.py           # Primary hashing orchestrator
│   │   └── ml/                 # Stage 1.5 Adversarial CLIP model
│   ├── notebooks/              # Google Colab GPU notebooks
│   └── tests/                  # Unit and integration test suite
│
├── tools/                      # Automated smoke tests & validation scripts
├── requirements.txt            # Python dependencies
├── start_studio.bat            # Windows auto-launch script
├── PROJECT_CONTEXT.md          # Comprehensive technical specification
└── TUTORIAL.md                 # Complete user tutorial & workflow guide
```

---

## 🧪 Running Tests

Full end-to-end smoke test (drives upload → hash → exact-canvas export → download):
```bash
python tools/smoke_test.py
```
And the hashing engine unit tests:
```bash
cd "yt content hashing"
python -m pytest -v
```

---

## 📄 License

This project is licensed under the MIT License.
