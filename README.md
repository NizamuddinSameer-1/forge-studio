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
- ✂️ **Visual Canvas Cropper**: Interactive aspect ratio transformation (`9:16` vertical, `1:1` square, `16:9` landscape) with drag & resize handles and coordinate tracking.
- 🎨 **Real-Time Color Grading**: Exposure, contrast, saturation, color temperature, and vignette adjustments.
- 🛡️ **Watermark & Logo Blur Mask**: Target and blur intrusive channel logos or platform watermarks with customizable coordinates.
- ✍️ **Custom Text Overlays**: Render stylized captions and hooks directly onto video frames with customizable font sizing and positioning.
- 🔬 **V7 Content Hashing Engine**: Multi-stage algorithmic stream modification designed to defeat automated Content ID and duplicate detection algorithms while preserving visual fidelity ($SSIM \ge 0.98$).
- 🤖 **Adversarial ML Stage (Stage 1.5)**: Deep embedding disruption using CLIP / Vision Transformer adversarial passes to break semantic clustering.
- 🧹 **Storage Management Hub**: Built-in disk usage monitoring, upload/render management, and one-click auto-cleanup.
- ⚡ **One-Click Startup**: Auto-detecting Windows batch launcher (`start_studio.bat`) that resolves Python environments and required packages automatically.

---

## 🏛️ System Architecture

```
Forge Studio Workstation
├── Web Micro-Studio UI (app/static/)
│   ├── Video Canvas & Visual Cropper (Aspect ratio transformations)
│   ├── Color Grading, Logo Blur, Text Overlays
│   └── Storage Management Dashboard
│
├── Studio Backend Engine (app/main.py, app/editor_engine.py)
│   ├── REST Endpoints (Upload, URL Download, Render, Storage)
│   ├── FFmpeg Filter Graph Builder
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

The hashing engine provides multiple pre-tuned profiles matching different platform risk tolerances:

| Profile | Target Platforms | Modifications Applied | Visual Quality |
|---|---|---|---|
| **SAFE** | Low-risk reposting / slight variants | Subtle micro-geometry adjustments, gentle audio EQ | SSIM > 0.99 (Virtually undetectable) |
| **BALANCED** | Standard YouTube Shorts / Reels | Geometric shifts, chromatic aberration, audio harmonic shifts | SSIM ~ 0.98 (Crisp & natural) |
| **AGGRESSIVE** | High-scrutiny viral clips | Advanced temporal cadence shifts, grain injection, frequency masking | SSIM ~ 0.96 (High protection) |
| **MAXIMUM** | Stringent duplicate detection environments | Full composite pipeline + TOON debanding + bilateral quantization | Strongest non-destructive protection |
| **TOON** | Anime, cartoons, stylized content | Frame rate cadence adaptation (12/24 fps), edge enhancement, halftone | Optimized for animated media |
| **AIMIMIC** | AI-generated content mimics | Synthetic artifact injection mimicking Gen-AI video models | Simulates fresh AI generation |

---

## 📁 Repository Structure

```
forge-studio/
├── app/
│   ├── main.py                 # FastAPI application routes & REST endpoints
│   ├── editor_engine.py        # FFmpeg video processing & export pipeline
│   ├── static/
│   │   ├── css/studio.css      # Dark-mode UI styling & responsive layout
│   │   └── js/                 # Modular frontend engines
│   │       ├── main.js         # Core application state & event routing
│   │       ├── cropper.js      # Interactive canvas aspect ratio cropper
│   │       ├── color_grading.js# Color adjustment controls
│   │       ├── text_overlay.js # Dynamic caption generator
│   │       └── storage.js      # Storage management modal
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

To run the full test suite for the V7 Content Hashing Engine:
```bash
cd "yt content hashing"
python -m pytest -v
```

---

## 📄 License

This project is licensed under the MIT License.
