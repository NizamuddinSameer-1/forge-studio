"""Stage 1 constants and intensity profiles. No metadata / Stage 2."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["SAFE", "BALANCED", "AGGRESSIVE", "AIMIMIC", "MAXIMUM", "TOON"]

# ----- global encode defaults (shared) -----
PROCESS_TIMEOUT = 28800
TARGET_BITRATE = "5M"
GOP_INTERVAL = 30
DOWNSCALE_W = 1280
DOWNSCALE_H = 720
FRAME_RATE_MODE = "cfr"
OUTPUT_FRAME_RATE = 30
SAMPLE_RATE = 48000
MIN_OUTPUT_BYTES = 1024

# Disabled / unsafe (document; do not enable without proof)
# PERCEPTUAL_WARP: perspective filter lacks reliable t/n expression support
PERCEPTUAL_WARP_ENABLE = False

MV_X264_PARAMS_A = "me=umh:subme=1:merange=48:mbtree=0:direct=spatial:no-dct-decimate=1:trellis=0:weightp=0"
MV_X264_PARAMS_B = "me=esa:subme=2:merange=32:mbtree=1:direct=temporal:no-dct-decimate=0:trellis=1:weightp=2"
MV_X264_PARAMS_C = "me=tesa:subme=3:merange=64:mbtree=0:direct=auto:no-dct-decimate=1:trellis=2:weightp=1"

@dataclass(frozen=True)
class Profile:
    name: ProfileName
    # geometry / motion
    pan_enable: bool = True
    pan_offset_px: int = 6
    pan_frequency: float = 0.5
    crop_size: float = 0.95
    micro_rotation_deg: float = 0.3
    rotation_bilinear: int = 0
    warp_strength: float = 0.015
    # color / grain
    chromatic_enable: bool = True
    chromatic_shift: int = 2
    grain_strength: float = 3.0
    grain_temporal: bool = True
    lut_freq_tweak: bool = True
    lut_freq_strength: float = 0.005
    luma_crush: bool = True
    luma_shadows: float = 0.01
    luma_highlights: float = 0.0
    hue_spatial_drift: bool = True
    # timing
    pts_jitter: bool = True
    pts_jitter_min: float = 0.0005
    pts_jitter_max: float = 0.002
    timeline_desync_delta: float = 0.003
    # encode structure
    b_frame_inject: bool = True
    b_frames: int = 3
    b_strategy: int = 1
    b_pyramid: int = 1
    ref_frames: int = 4
    # DCT / ViT
    dct_geq: bool = True
    dct_dc_strength: float = 0.3
    dct_ac_strength: float = 0.15
    dct_chroma_strength: float = 0.15
    vit_patch_noise: bool = True
    vit_patch_noise_amplitude: float = 1.5
    vit_luminance_flicker: bool = True
    vit_luminance_flicker_max: float = 0.002
    vit_spatial_shift: bool = True
    vit_spatial_shift_max_px: int = 2
    vit_temporal_blend: bool = True
    vit_temporal_blend_ratio: float = 0.03
    # AI mimicry (expensive)
    ai_mimicry: bool = True
    ai_vae_grid_strength: float = 0.03
    ai_plastic_smoothing: bool = True
    ai_optical_flow: bool = True  # minterpolate on bg
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
    # toon audio (cartoon/anime-optimized chain)
    toon_audio: bool = False
    toon_pitch: float = 1.03
    toon_presence: float = 3.0
    toon_exciter: float = 2.0
    toon_stereo: float = 1.3
    # ML stage (Stage 1.5) — optional, cloud-first (Colab GPU)
    ml_stage: bool = False
    ml_video_adv: bool = True
    ml_video_adv_eps: float = 6.0      # L-inf bound, /255
    ml_video_adv_steps: int = 10       # PGD iterations
    ml_ssim_floor: float = 0.98        # perceptual budget guard
    # audio
    phase_invert: bool = True
    ultrasonic: bool = True
    ultrasonic_amp: float = 0.03
    pitch_shift_factor: float = 1.015
    aeco_comb_filter: bool = True
    # behavioral pad
    behavioral_pad: bool = True
    behavioral_pad_max_bytes: int = 4096
    # randomize ranges multiplier: 1.0 = current V7
    randomize: bool = True
    range_scale: float = 1.0  # AGGRESSIVE > 1, SAFE can keep 1 with flags off
    # per-video feature dropout: probability each non-critical technique is
    # skipped on a given run (breaks the fixed "processing fingerprint"
    # that lets platforms cluster all uploads from the same pipeline)
    feature_dropout: float = 0.2

PROFILES: dict[str, Profile] = {
    "BALANCED": Profile(name="BALANCED", ml_stage=True),
    "SAFE": Profile(
        name="SAFE",
        ai_optical_flow=False,
        ai_mimicry=False,
        ai_plastic_smoothing=False,
        dct_geq=False,
        vit_patch_noise=False,
        vit_temporal_blend=False,
        grain_strength=1.5,
        chromatic_shift=1,
        aeco_comb_filter=True,
        ultrasonic=True,
        phase_invert=True,
        range_scale=0.85,
    ),
    "AGGRESSIVE": Profile(
        name="AGGRESSIVE",
        grain_strength=4.0,
        chromatic_shift=3,
        vit_spatial_shift_max_px=3,
        vit_patch_noise_amplitude=2.0,
        ai_vae_grid_strength=0.04,
        range_scale=1.2,
        behavioral_pad_max_bytes=8192,
        ml_stage=True,
    ),
    "AIMIMIC": Profile(
        name="AIMIMIC",
        ai_mimicry=True,
        ai_vae_grid_strength=0.08,
        ai_plastic_smoothing=True,
        ai_optical_flow=True,
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
        ml_stage=True,
    ),
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
        toon_audio=True,
        toon_pitch=1.03,
        toon_presence=3.0,
        toon_exciter=2.0,
        toon_stereo=1.3,
        chromatic_enable=True,
        chromatic_shift=1,
        grain_strength=0.0,
        ai_plastic_smoothing=False,
        ai_mimicry=False,
        ai_optical_flow=False,  # minterpolate bg + toon_cadence minterpolate = deadlock
        dct_geq=False,
        bloom_enable=False,
        hue_spatial_drift=True,
        behavioral_pad=True,
        range_scale=1.1,
    ),
    "MAXIMUM": Profile(
        name="MAXIMUM",
        # geometry / motion
        pan_enable=True,
        chromatic_enable=True,
        # color / grain
        grain_temporal=True,
        lut_freq_tweak=True,
        luma_crush=True,
        hue_spatial_drift=True,
        grain_strength=4.0,
        chromatic_shift=3,
        # timing
        pts_jitter=True,
        # encode structure
        b_frame_inject=True,
        # DCT / ViT
        # NOTE: dct_geq + ai_mimicry + toon_* all use per-pixel `geq` filters
        # which are extremely slow (Python-speed per-pixel eval). Stacking all
        # of them made MAXIMUM take 17min for an 11s video on Colab's 2-core
        # CPU. Keep MAXIMUM strong but practical: use the fast ViT tricks +
        # heavy grain/chroma/timing, drop the slow geq-based ones.
        dct_geq=False,          # was True — geq per-pixel, ~13s/1s-video alone
        vit_patch_noise=True,
        vit_patch_noise_amplitude=2.0,
        vit_luminance_flicker=True,
        vit_spatial_shift=True,
        vit_spatial_shift_max_px=3,
        vit_temporal_blend=True,
        # AI mimicry
        ai_mimicry=False,       # was True — geq VAE grid, ~12s/1s-video alone
        ai_vae_grid_strength=0.08,
        ai_plastic_smoothing=True,
        ai_optical_flow=True,
        # ai-look stylization
        bloom_enable=True,
        bloom_strength=0.15,
        sat_lift=1.06,
        vae_chroma=0.01,
        # toon — all OFF in MAXIMUM (they're for the TOON profile; the geq
        # halftone + bilateral stack added ~12s/1s-video and fights the AI-look)
        toon_quantization=False,
        toon_line_art=False,
        toon_cadence=False,
        toon_halftone=False,
        toon_bilateral=False,
        toon_vibrance=False,
        toon_deband=False,
        toon_audio=False,
        # audio
        phase_invert=True,
        ultrasonic=True,
        aeco_comb_filter=True,
        # behavioral pad
        behavioral_pad=True,
        behavioral_pad_max_bytes=8192,
        # randomize
        randomize=True,
        ml_stage=True,
        range_scale=1.2,
    ),
}

def get_profile(name: str) -> Profile:
    key = (name or "BALANCED").strip().upper()
    if key not in PROFILES:
        valid = "|".join(PROFILES)
        raise ValueError(f"Unknown profile {name!r}; choose {valid}")
    return PROFILES[key]
