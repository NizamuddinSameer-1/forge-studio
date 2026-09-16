# ⚡ FORGE STUDIO & V7 CONTENT HASHING ENGINE
## Comprehensive Project Context, Architecture, Technical Specifications & Systems Reference

> **Project Name:** Forge Studio (Custom Video Editing Micro-Studio & V7 Content Hashing Pipeline)  
> **Repository Root:** `Custom editing software/`  
> **Current Version:** 2.0.0  
> **Primary Interfaces:** Web Micro-Studio (`localhost:8000`), Automation CLI (`v7_pipeline`), Colab GPU Notebook (`ml_stage_colab.ipynb`)  
> **Target Platforms:** YouTube Shorts, Instagram Reels, TikTok  

---

## 1. Executive Summary & Core Mission

**Forge Studio** is a purpose-built, full-stack video editing micro-studio and algorithmic anti-detection platform. It is engineered specifically for digital creators, content curators, and media automation workflows who repurpose short-form video content (YouTube Shorts, Instagram Reels, TikTok) and need to **defeat automated content matching algorithms, Content ID fingerprinting, and duplicate clustering mechanisms** that cause algorithmic shadowbans.

The system combines:
1. A **high-speed browser-based editing suite** (instant URL downloads, visual canvas cropping, aspect ratio conversions, color grading, logo blur masking, custom text overlays, and precision timeline trimming).
2. A **two-stage algorithmic Content Hashing Engine (V7 Pipeline)** that modifies video and audio bitstreams on structural, mathematical, perceptual, and neural embedding levels so that the output **looks visually identical to humans** (SSIM ≥ 0.98) but appears **completely unique to automated platform detection systems**.

---

## 2. Why This Project Was Created (Origin & Problem Statement)

### The Creator's Problem: The "Shadowban Trap"
When short-form video creators repost or iterate on viral video clips across platforms like YouTube Shorts, social media platforms deploy automated duplicate detection algorithms. These systems do not merely compare simple file hashes (MD5 / SHA-256); they use:
- **Audio Fingerprinting** (Chromaprint / Acoustic ID)
- **Visual Frame Hashing & Spatio-Temporal Signatures** (DCT coefficients, perceptual hashing, motion vectors)
- **Deep AI Embeddings** (Vision Transformer / CLIP models clustering duplicate semantic concepts)

When an uploaded video matches an existing cluster, the platform flags it as duplicate or unoriginal content, resulting in **zero reach, algorithmic suppression, or outright account shadowbans**.

### The Previous Friction-Heavy Workflow (Before Forge Studio)
Before this project was built, the user had to jump between multiple applications and devices to prepare a single video:
```
[Social Media (Insta / YT)]
        │
        ▼ (Download clip via 3rd party tool)
[Mobile Phone / CapCut]
        │
        ▼ (Crop watermark, change to 9:16, trim black bars)
[Export to Phone Storage]
        │
        ▼ (Transfer file via AirDrop / Telegram / USB to PC)
[PC / Laptop]
        │
        ▼ (Upload video to Google Drive / Colab)
[Google Colab (Cloud GPU)]
        │
        ▼ (Run CLI content hashing script)
[Download Output to PC]
        │
        ▼ (Transfer back to phone for final captioning/editing)
[Upload to YouTube Shorts]
```
**Total Time:** 30 to 50 minutes per video.  
**Friction Points:** 5 device transfers, 4 distinct applications, battery drain, file fragmentation, and frequent encoding errors.

### The Solution: Forge Studio
Forge Studio collapses this entire pipeline into a single, cohesive local workstation:
1. Paste a video URL (YouTube, Instagram, TikTok) or drop a file.
2. Crop and frame the video directly on a live interactive canvas.
3. Apply color grading, blur out logos/watermarks, and add branded text.
4. Click **Run Content Hashing** with one click (profile selection + live progress).
5. Click **Export Video** for instant delivery ready for YouTube upload.

**Total Time:** Under 2 minutes per video with zero device switching.

---

## 3. High-Level System Architecture

Forge Studio operates on a client-server decoupled architecture designed for low latency, zero UI stalls, and strict file isolation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             BROWSER CLIENT (UI)                             │
│       HTML5 Canvas 2D · Vanilla ES6 Modules · Glassmorphic Dark Theme        │
│                                                                             │
│  [Source Ingest]  [Canvas Cropper]  [Color/EQ]  [Mask Blur]  [Text Layers] │
│         │                 │              │           │             │        │
│         └─────────────────┴──────────────┴───────────┴─────────────┘        │
│                                    │                                        │
│                      JSON State + REST API (Fetch)                          │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI SERVER (app.main)                         │
│                    Uvicorn ASGI Engine · Port 8000 / Custom                 │
│                                                                             │
│  Endpoints: /api/upload, /api/fetch-url, /api/hash, /api/export, /api/storage│
│  State: Config Fingerprinting (SHA-256 Signature Registry)                 │
│  Workers: Background Thread Job Executor + TextIO Pipe Streamers            │
└───────────────────────┬─────────────────────────────┬───────────────────────┘
                        │                             │
                        ▼                             ▼
┌───────────────────────────────────────┐ ┌───────────────────────────────────┐
│     EDITOR ENGINE (app.editor_engine) │ │  V7 HASHING ENGINE (v7_pipeline)  │
│                                       │ │                                   │
│  • FFprobe JSON Metadata Inspector    │ │  • Stage 1: Mathematical/FFmpeg   │
│  • Dynamic FFmpeg Complex Filter Graph│ │    - JND Drift (Luma/Chroma/Hue)  │
│  • Precise In/Out Trim Handling       │ │    - ViT Patch Noise Injection    │
│  • Boxblur Sub-Region Masking         │ │    - DCT Coefficient Jitter       │
│  • Multi-Layer DrawText Formatting    │ │    - Audio Phase / Comb / Pitch   │
│  • Scratch Space Render Management    │ │    - Behavioral EOF Byte Padding  │
│                                       │ │  • Stage 1.5: Adversarial ML (GPU)│
│                                       │ │    - OpenCLIP ViT-B-32 Perturb    │
│                                       │ │    - Cosine Distance Optimization │
│                                       │ │    - SSIM Perceptual Budget Guard │
└───────────────────────────────────────┘ └───────────────────────────────────┘
```

---

## 4. Complete Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend Framework** | **FastAPI** (`>=0.110.0`) | High-performance asynchronous REST API handling endpoints, uploads, streaming, and background thread execution. |
| **Web Server** | **Uvicorn** (`uvicorn[standard]>=0.28.0`) | Lightning-fast ASGI server powering the local micro-studio. |
| **Data Validation** | **Pydantic v2** (`>=2.0.0`) | Strict request/response typing and schema validation for video edit parameters. |
| **Video Ingestion** | **yt-dlp** (`>=2026.0.0`) | Automated multi-platform video scraping and extraction (YouTube, Instagram, TikTok, Twitter/X). |
| **Media Engine** | **FFmpeg & FFprobe** | Hardware/software accelerated video transcoding, stream demuxing, complex filtering, drawtext, and metadata inspection. |
| **Progress Streaming**| **tqdm** (`>=4.60.0`) + Custom IO | Real-time CLI and UI progress parsing extracted from raw FFmpeg streams. |
| **ML Surrogate Attack**| **PyTorch & OpenCLIP** (`ViT-B-32`) | Neural adversarial attack pushing video embeddings outside automated platform duplicate clusters. |
| **Image & Math Tools** | **NumPy, Pillow (PIL), SciPy** | Frame buffer manipulations, SSIM calculations, and tensor operations. |
| **Frontend Core** | **Vanilla HTML5, CSS3, ES6 JavaScript** | Zero-framework footprint (no React, no Node.js build step), instantaneous page load, direct DOM/Canvas control. |
| **Typography** | **Google Fonts (Inter, Outfit, Space Grotesk)** | Modern, aesthetic typography curated for media production tools. |
| **Platform Automation**| **Windows Batch (`start_studio.bat`)** | Automated Python runtime selection, dependency auto-installation, FFmpeg verification, and browser orchestration. |

---

## 5. Comprehensive Directory & File Structure

```
Custom editing software/
│
├── start_studio.bat               # One-click launcher: finds Python 3.10-3.13, checks FFmpeg, runs server
├── requirements.txt               # Base studio dependencies (fastapi, uvicorn, yt-dlp, pydantic, tqdm)
├── TUTORIAL.md                    # Comprehensive end-user operations handbook and troubleshooting guide
├── PROJECT_CONTEXT.md             # Complete system architecture and engineering documentation (this file)
├── Gemini-Content Hashing...md    # Architectural origin log documenting the design requirements
│
├── app/                           # Forge Studio Web Application
│   ├── main.py                    # FastAPI server: route handlers, job queue, thread manager, storage API
│   ├── editor_engine.py           # FFmpeg filter-graph builder, metadata prober, full render pipeline
│   ├── uploads/                   # Local storage for imported source files and downloaded URLs
│   ├── outputs/                   # Final deliverables ready for preview, download, or platform upload
│   └── static/                    # Frontend static assets
│       ├── index.html             # Single-page studio interface (glassmorphic dark theme)
│       ├── css/
│       │   └── studio.css         # Custom stylesheet (custom tokens, responsive grid, animations)
│       ├── fonts/                 # Bundled TrueType fonts for FFmpeg drawtext (Arial, Arial Bold, Impact)
│       └── js/
│           ├── app.js             # Master frontend controller: state management, API polling, event binding
│           ├── canvas_cropper.js  # Interactive 8-handle video cropper with live aspect-ratio constraints
│           ├── color_grading.js   # Live preview and sliders for brightness, contrast, saturation, temperature
│           ├── mask_overlay.js    # Draggable, resizable blur region for watermarks and handles
│           ├── text_overlay.js    # Multi-layer typography engine with font selection, stroke, and background
│           └── timeline.js        # Video playback scrubber, duration formatter, and trim-range controller
│
├── yt content hashing/            # The V7 Anti-Detection Hashing Engine
│   ├── v7_pipeline/               # Modular Python package for Stage 1 and Stage 1.5
│   │   ├── config.py              # Profile definitions (SAFE, BALANCED, AGGRESSIVE, AIMIMIC, TOON, MAXIMUM)
│   │   ├── filters.py             # Stage 1 filter builder: JND drift, DCT, ViT noise, audio shifts
│   │   ├── encoder.py             # Hardware-accelerated (NVENC/QSV/AMF) & libx264 encoding orchestrator
│   │   ├── stage1.py              # Master Stage 1 executor: preflight checks, validation, byte padding
│   │   ├── validate.py            # Audio/video integrity checks, stream duration verification
│   │   ├── batch.py               # Folder batch processing engine
│   │   ├── cli.py                 # Terminal command-line interface (`python -m v7_pipeline`)
│   │   ├── paths.py               # Scratch space and temporary directory resolvers
│   │   └── ml/                    # Optional Stage 1.5 Adversarial Machine Learning Pipeline
│   │       ├── orchestrate.py     # Frame extraction, perturbation scheduler, and delta re-encoder
│   │       ├── video_adv.py       # OpenCLIP ViT-B-32 surrogate attack & gradient ascent implementation
│   │       └── budget.py          # SSIM floor (0.98) and L-inf epsilon bounding controllers
│   ├── notebooks/
│   │   ├── ml_stage_colab.ipynb   # Colab GPU notebook for executing Stage 1.5 with free T4 acceleration
│   │   └── meta_data_hashing...   # Supplementary notebook for deep EXIF/container metadata manipulation
│   ├── tests/                     # 43 automated pytest unit tests validating all hashing components
│   └── docs/                      # Technical references for content hashing logic
│
└── tools/                         # Maintenance, Diagnostics & Verification Utilities
    ├── smoke_test.py              # End-to-end integration test driving full studio flow via HTTP
    ├── storage_check.py           # Disk footprint validator for uploads/ and outputs/
    ├── scale_test_4k.py           # 4K / high-bitrate video render stress test
    ├── hash_crop_check.py         # Aspect ratio and resolution verification post-hashing
    ├── ui_check.js                # Headless browser verification script
    ├── crop_check.js              # Canvas cropping precision validator
    └── GIT-NOTES.md               # Diagnostic documentation on OneDrive sync locking & branch ref recovery
```

---

## 6. Deep Dive: The V7 Anti-Detection Content Hashing Pipeline

The V7 Engine is not a simple random noise generator. It is an adversarial signal processing pipeline specifically targeted at the feature-extraction techniques used by social media platforms.

### 6.1 Stage 1: Mathematical, Perceptual & Bitstream Perturbations (Runs Everywhere)
Stage 1 executes on standard CPUs via FFmpeg filtergraphs and customized x264 parameters. It applies subtle, pseudo-randomized mathematical operations:

1. **JND (Just Noticeable Difference) Drift:**
   - Dynamic non-linear fluctuations in luminance, gamma, and contrast (`eq` filter) modulated by micro-frequency sine waves.
   - Subtle dynamic hue shifts (`hue` filter) shifting the global color balance imperceptibly across time.

2. **Vision Transformer (ViT) Patch Perturbation:**
   - Video matching neural networks (like VideoCLIP or ViT) divide video frames into discrete $16\times16$ or $32\times32$ pixel patches.
   - Stage 1 introduces micro-luminance flicker and high-frequency noise tailored to alter patch attention maps without human visual degradation.

3. **Discrete Cosine Transform (DCT) Manipulation:**
   - Standard Content ID and perceptual hashing algorithms (pHash, aHash, dHash) compute DCT frequencies on 8x8 pixel blocks.
   - Stage 1 slightly perturbs low-frequency (DC) and medium-frequency (AC) coefficients to break perceptual hash signatures.

4. **Micro-Transformations & Perspective Warping:**
   - Dynamic subtle pan-and-scan micro-zooming (`0.1%` to `0.3%`).
   - Perceptual perspective skew and sub-degree micro-rotation (`rotate`).
   - Slight chromatic aberration (channel splitting of Red and Blue channels via `rgbashift`).

5. **Acoustic / Audio Pipeline Obfuscation:**
   - Sub-semitone pitch shifting (`asetrate` / `atempo` combo preserving pitch contour).
   - Dynamic parametric equalization notch filters (`equalizer`).
   - Comb filtering and slight stereo phase inversion (`aeval` / `chorus`).
   - High-frequency ultrasonic watermark injection (inaudible carrier tones above 18.5 kHz).

6. **H.264 Bitstream & Container Perturbations:**
   - **GOP (Group of Pictures) Jitter:** Randomizing I-frame intervals between 12 and 48 frames.
   - **B-Frame Pyramid & Motion Vector Variance:** Randomized sub-pixel motion estimation flags (`subme`, `me_range`, `trellis`).
   - **PTS (Presentation Time Stamp) Jitter:** Micro-adjusting presentation timestamps by microseconds to desynchronize automated frame matchers.
   - **Behavioral EOF Byte Padding:** Injecting randomized cryptographic entropy (`os.urandom(N)`) into the MP4 container structure outside atom boundaries.

---

### 6.2 Stage 1.5: Adversarial Machine Learning Attack (Colab / GPU)
Modern platforms (such as Meta and Google/YouTube) use multimodal deep learning models (like CLIP and ViT) to map video frames into a 512-dimensional vector embedding space. If two videos have a cosine similarity above ~0.85, they are categorized as identical content.

Stage 1.5 directly attacks this vector space:
- **Surrogate Model:** Uses `OpenCLIP` with a `ViT-B-32` backbone pretrained on `laion2b_s34b_b79k`.
- **Target Loss Function:** Maximizes cosine distance between original frame embeddings $E_{orig}$ and perturbed frame embeddings $E_{adv}$:
  $$\mathcal{L} = 1 - \cos(E_{orig}, E_{adv})$$
- **Optimization Strategy:** Iterative Projected Gradient Ascent / Fast Gradient Sign Method (FGSM) with an $L_\infty$ perturbation budget ($\epsilon = 6.0$).
- **Perceptual Floor (SSIM Guard):** Samples frames and calculates Structural Similarity (SSIM). If SSIM drops below `0.98`, the attack strength automatically dampens to preserve pristine visual fidelity.
- **Result:** Pushes the AI embedding away from the duplicate cluster (cosine similarity drops from `1.0` to `<0.75`), rendering the clip "novel" to neural content scanners.

---

### 6.3 The 6 Hashing Profiles

| Profile Name | Intensity | ML Stage? | Optimal Use Case | Key Characteristics |
|---|---|---|---|---|
| **`SAFE`** | Lowest | ❌ Off | High-value, delicate 4K footage | Minimum perturbation; undetectable to human eye; safeguards against quality degradation. |
| **`BALANCED`** | Medium | ✅ On (GPU) | **Default choice for 90% of videos** | Excellent protection/fidelity tradeoff; moderate JND drift and audio shifts. |
| **`AGGRESSIVE`**| High | ✅ On (GPU) | Stubborn clips repeatedly flagged | Increased chromatic shift, stronger ViT noise, aggressive GOP and audio jitter. |
| **`AIMIMIC`** | High | ✅ On (GPU) | Modern Gen-Z/Shorts styling | Injects a subtle "AI-generated" visual aesthetic (bloom, saturation lift, diffusion softness). |
| **`TOON`** | Medium | ❌ Off | Anime, cartoons, 2D vector art | Customized edge detection, contrast-adaptive sharpening, and flat-color preserving filters. |
| **`MAXIMUM`** | Maximum | ✅ On (GPU) | Nuclear option | All perturbations set to maximum allowable thresholds; used when everything else fails. |

---

## 7. Forge Studio: Interactive Editing Features & Functions

Forge Studio's user interface is structured around a real-time reactive editing paradigm:

### 7.1 Source Ingestion Tab
- **Local File Upload:** Supports drag-and-drop or file picker for `.mp4`, `.mov`, `.webm`, `.mkv`. Immediate server-side `ffprobe` extracts dimensions, frame rate, duration, and file size.
- **Social Media Link Downloader:** Built-in integration with `yt-dlp`. Paste any public URL from YouTube (Shorts or long-form), Instagram Reels, TikTok, or Twitter/X. The server fetches the optimal video/audio streams, remuxes to MP4, and mounts it directly on the canvas.
- **Storage Management Panel:** Real-time visibility into `uploads/` and `outputs/` folder size. Displays individual file sizes, timestamps, "IN USE" protection tags, single-file delete buttons, and age-filtered bulk purge options.

### 7.2 Crop & Aspect Ratio Tab
- **Interactive Canvas Cropper:** 8-point white resize handles allowing freeform box scaling, corner dragging, and repositioning over an HTML5 canvas.
- **Aspect Ratio Presets:**
  - `9:16` (Vertical Short / Reel / TikTok - standard `1080×1920` slice)
  - `1:1` (Square Instagram / Feed)
  - `4:5` (Vertical Feed)
  - `16:9` (Widescreen Landscape)
  - `4:3` (Classic Format)
  - `Freeform` (Unlocks aspect ratio lock for arbitrary custom rectangles)
- **Live Dimension Badge:** Displays real-time output pixel dimensions (e.g., `Custom · 1080×1920`).
- **Even-Pixel Enforcement:** Automatically forces crop dimensions to even numbers ($cw = cw - (cw \pmod 2)$) to ensure compliance with YUV420p H.264 macroblock constraints.
- **Standardized Hash Rescaling:** The engine normalizes vertical crops to `1280px` width and horizontal crops to `720px` height while strictly preserving the cropped aspect ratio.

### 7.3 Color & Sharpening Tab
- **Sharpen:** Unsharp mask filter (`unsharp=lx=5:ly=5:la=X:cx=5:cy=5:ca=Y`) enhancing high-frequency edge clarity (0.0 to 2.5).
- **Brightness:** Linear luminance adjustment (-1.0 to 1.0).
- **Contrast:** Dynamic range expansion (0.1 to 2.5).
- **Saturation:** Color vibrance multiplier (0.0 to 3.0).
- **Temperature (Warmth/Cool):** RGB color balance filter (`colorbalance=rs=X:bs=-X`) shifting the mood between warm sunlight and cool cyan tones.

### 7.4 Mask Blur Tab
- **Logo & Watermark Obliteration:** A draggable, resizable overlay box designed to blur out TikTok watermarks, Instagram account handles, or channel logos.
- **Sub-Region Extraction Filter Graph:** Splits the video stream into two branches, crops the exact masked rectangle, passes it through an intensive `boxblur` filter (`boxblur=luma_radius=X:luma_power=2`), and overlays it back onto the base video at exact pixel coordinates.

### 7.5 Text Overlay Tab
- **Multi-Layer Typography:** Add and configure multiple independent text layers on screen.
- **Font Selection:** Direct mapping to local system TrueType fonts:
  - `Arial`
  - `Arial Bold`
  - `Arial Black`
  - `Impact` (the classic meme / punchline typography)
- **Styling Controls:** Text string, font size (px), text color (hex color picker), outline/stroke color and stroke width, background box badge with customizable opacity.
- **DrawText Escaping:** Robust sanitization of quotes, colons, brackets, and percentage symbols to prevent FFmpeg filter syntax breakage.

### 7.6 Timeline & Precision Trimming
- **Interactive Scrubber:** Scrub through video frames with real-time video sync.
- **Trim Start & Trim End:** Set precise in/out points down to millisecond accuracy.
- **Precision Seek Transcoding:** Employs FFmpeg input seeking (`-ss`) before the input flag for rapid parsing combined with duration slicing (`-t`).

---

## 8. State Architecture, Job Infrastructure & Export Safety

To prevent server locks and guarantee that exported files are genuine, Forge Studio incorporates enterprise-grade execution patterns:

### 8.1 Configuration Signature Fingerprinting
Whenever a user modifies a crop handle, color slider, text layer, or hashing setting, the system calculates a deterministic SHA-256 state fingerprint:
```python
signature = hashlib.sha256(json.dumps({
    "filename": req.filename,
    "edits": {trim, crop, color_grade, mask, text_layers},
    "hashing": req.hashing,
    "apply_hashing": True
}, sort_keys=True).encode()).hexdigest()
```

### 8.2 Two-Stage Export Protection
- Hashing is computationally intensive (a full re-encode). Therefore, **Content Hashing is executed as an explicit step via the Anti-Detection tab**.
- When hashing finishes, the result is cached in `HASH_REGISTRY` indexed by its state signature.
- If the user subsequently alters an edit (e.g. adjusts text or crop), the UI immediately detects that the current state differs from the cached hash, turning the status badge **Amber** (*"Your edits changed since this hash"*).
- The **Export Video** button **refuses** to export stale renders, forcing the creator to re-run hashing. This completely eliminates the catastrophic mistake of accidentally uploading unhashed content.

### 8.3 Live Job Queue & Stream Interceptors
- Hashing jobs run in a dedicated background worker thread (`threading.Thread`).
- The server captures standard output and standard error using a custom stream interceptor (`_JobLogStream`).
- **Real Progress Extraction:** Regular expressions parse `tqdm` output lines (e.g. `Encoding: 47%|████...`) into exact integer percentages ($1\% \to 100\%$) sent to the frontend.
- **Non-blocking Editing:** Creators can click *"Continue in background"* to dismiss the modal and continue working while the server encodes.
- **Janitor Thread:** A background watchdog periodically sweeps `JOBS`, terminating and reporting any task that exceeds the execution timeout (default: 2 hours).

---

## 9. Complete REST API Reference

The backend exposes a clean REST API documented below:

| Method | Endpoint | Description | Payload / Query | Response |
|---|---|---|---|---|
| `GET` | `/` | Serves the single-page application | None | HTML content with `no-store` cache headers. |
| `GET` | `/api/profiles` | Returns available hashing profiles, fonts, engine status, and ML availability | None | `{ profiles: [...], fonts: [...], engine: { available: bool }, ml_stage: {...} }` |
| `POST` | `/api/upload` | Multipart video file upload | `file: UploadFile` | `{ success: true, filename: str, url: str, width, height, duration, fps, size_mb }` |
| `POST` | `/api/fetch-url` | Scrapes and downloads video from public URL via yt-dlp | `{ "url": "https://..." }` | `{ success: true, filename: str, url: str, width, height, duration, fps, size_mb }` |
| `POST` | `/api/hash` | Initiates asynchronous content hashing worker thread | Full `ProcessVideoRequest` JSON | `{ success: true, job_id: str, signature: str, engine_available: bool }` |
| `GET` | `/api/hash/{job_id}` | Polls progress, status, stage, and incremental server logs | `since: int` (log offset) | `{ status: "running"|"done"|"error", progress: int, stage: str, logs: [...], elapsed: float, result: {...} }` |
| `POST` | `/api/export` | Validates hash signature and returns hashed deliverable | Full `ProcessVideoRequest` JSON | `{ success: true, file_name: str, download_url: str, reused: bool, ... }` |
| `POST` | `/api/process` | Synchronous one-shot render (ideal for scripts / batch) | Full `ProcessVideoRequest` JSON | Full rendered pipeline result dictionary. |
| `GET` | `/api/storage` | Returns disk usage metrics for uploads and outputs | None | `{ uploads: [...], outputs: [...], uploads_total_mb: float, outputs_total_mb: float, in_use: [...] }` |
| `DELETE`| `/api/storage/{kind}/{filename}` | Deletes a single uploaded or rendered file safely | Path parameters: `kind` (`uploads`\|`outputs`), `filename` | `{ success: true, deleted: str, freed_mb: float }` |
| `POST` | `/api/storage/clear` | Bulk clears uploaded or rendered files (with age filter) | `{ "kind": "uploads"|"outputs"|"all", "older_than_hours": float }` | `{ success: true, deleted_count: int, freed_mb: float }` |
| `GET` | `/api/download/{filename}`| Direct attachment download of rendered video | Path parameter: `filename` | Binary MP4 file response (`Content-Disposition: attachment`). |
| `GET` | `/api/debug/threads` | Developer diagnostic: dumps thread stacks and job ages | None | Thread stack traces and active job statuses. |

---

## 10. Operational Workflows: How to Run the System

### Workflow 1: The Local Studio (Day-to-Day Editing)
1. **Start the Studio:** Double-click `start_studio.bat` in the project root.
   - The script identifies a suitable Python interpreter (`3.13` down to `3.10`).
   - Automatically installs any missing packages from `requirements.txt`.
   - Confirms FFmpeg is present on system PATH.
   - Launches `app.main` on `http://localhost:8000` and automatically opens your default browser.
2. **Ingest Media:** Drag an MP4 file into the dropzone or paste an Instagram Reel / YouTube Shorts URL.
3. **Edit:**
   - Select **Crop & Ratio** $\to$ choose `9:16` for vertical Shorts.
   - Select **Color & Sharpen** $\to$ increase sharpen (+0.5) and adjust saturation.
   - Select **Mask Blur** $\to$ place blur box over watermarks/usernames.
   - Select **Text Overlay** $\to$ add custom headline with outline or background box.
4. **Hash:**
   - Go to **Anti-Detection** tab.
   - Select `BALANCED` (recommended default).
   - Click **⚡ Run Content Hashing**.
   - Monitor the real-time progress bar ($1\% \to 100\%$) and stage indicator.
5. **Export:**
   - Click **Export Video** in the top navigation header.
   - Download the file directly or preview it in the player. The file is ready for YouTube upload.

---

### Workflow 2: Command-Line Automation (Batch Processing)
To process video batches without launching the web browser:
```powershell
# Open terminal in project root
cd "Custom editing software"

# Process the newest video in yt content hashing/input using BALANCED profile
python -m v7_pipeline

# Process a specific video with AGGRESSIVE profile
python -m v7_pipeline --input "path\to\video.mp4" --profile AGGRESSIVE

# Reproducible run using an exact integer seed
python -m v7_pipeline --input "path\to\video.mp4" --profile BALANCED --seed 42

# Batch process an entire directory of downloaded videos
python -m v7_pipeline --batch "input_folder" --profile BALANCED --skip-existing
```

---

### Workflow 3: Google Colab (Free GPU for Stage 1.5 AI Pass)
When processing high-stakes videos where you want the full neural network CLIP adversarial attack:
1. Open [Google Colab](https://colab.research.google.com).
2. Upload notebook: `yt content hashing/notebooks/ml_stage_colab.ipynb`.
3. Set runtime to **GPU (T4)**: `Runtime` $\to$ `Change runtime type` $\to$ `T4 GPU`.
4. Run cells sequentially:
   - Installs PyTorch, OpenCLIP, and FFmpeg.
   - Uploads project code zip and source video.
   - Executes `v7_pipeline` with the Stage 1.5 ML pass enabled.
   - Calculates and displays validation metrics:
     ```
     mean SSIM over 24 sampled frames: 0.9856  (safe floor: 0.98)
     CLIP cosine similarity: 0.7231  (original was 1.0)
     cosine distance: 0.2769  (successful embedding shift)
     ```
   - Downloads the final AI-protected video.

---

## 11. Engineering Gotchas, Edge Cases & Diagnostics

### 11.1 OneDrive Sync & Git Ref Disappearance
- **The Issue:** Because this workspace resides inside a Microsoft OneDrive synchronized folder (`OneDrive\Desktop\...`), OneDrive's background file locking can interfere with atomic file renames performed by Git.
- **Symptom:** Committing in `yt content hashing/` succeeds, but running `git log` immediately returns `fatal: your current branch does not have any commits yet`.
- **The Reality:** No data or commit objects are lost; only the pointer file in `.git/refs/heads/` was locked during rename.
- **The Recovery Command:**
  ```bash
  cd "yt content hashing"
  git reflog
  git branch -f feature/v7-stage1-robust <COMMIT_SHA>
  ```
- **Architectural Safeguard:** `app/editor_engine.py` deliberately places intermediate render files in the operating system's temporary directory (`os.environ["TEMP"] / forge_studio_work`), completely outside OneDrive, preventing sync locks during intensive video encoding.

### 11.2 Audio Encoder NaN/Inf Recovery
- When applying randomized notch filtering, comb filtering, and pitch shifting, certain rare source audio streams can produce arithmetic infinities ($NaN$ or $Inf$) in FFmpeg's `aac` encoder, causing FFmpeg to fail with code 1.
- **The Engine's Automated Fallback:** `v7_pipeline.stage1.process_video` continuously inspects stderr tails. If it identifies `NaN in audio`, it logs `[!] Audio encode failed; retrying with simpler audio chain...` and automatically re-encodes using an ultra-stable pitch+EQ chain. If that also encounters issues, it cleanly re-encodes without audio rather than crashing the studio.

### 11.3 Port Collisions
- If port `8000` is already in use by another local development server, start Forge Studio on a custom port using an environment variable:
  ```powershell
  $env:FORGE_PORT=8010 ; python -m app.main
  ```

### 11.4 End-to-End Automated Testing
Verify the complete stack (API, rendering, hashing, signature verification, staleness detection, and download) at any time by running the automated smoke test against a running studio instance:
```powershell
python tools\smoke_test.py 8000
```
Or run the 43 unit tests in the hashing test suite:
```powershell
cd "yt content hashing"
python -m pytest -q
```

---

## 12. Summary Checklist: What Makes This System Unique

1. **All-in-One Convergence:** Replaces a 4-software, 2-device friction loop with a single zero-dependency web micro-studio.
2. **True Anti-Detection:** Goes far beyond cosmetic filters; attacks DCT frequencies, JND thresholds, audio acoustic signatures, H.264 bitstream metadata, and neural CLIP embeddings.
3. **Human-Indistinguishable Quality:** Guaranteed SSIM $\ge 0.98$ ensures that viewers experience 100% crisp visual and acoustic fidelity.
4. **Resilient Architecture:** Incorporates scratch space isolation, automatic audio fallback recovery, state signature caching, and live progress streaming.
5. **Zero Vendor Lock-In:** 100% local, private, and open-source running completely on your own machine.
