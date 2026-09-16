"""Stage 1 filter graph builders. Ported from V7_Combined_local.py (BALANCED defaults)."""
from __future__ import annotations

import random
from dataclasses import dataclass

from v7_pipeline.config import (
    GOP_INTERVAL,
    MV_X264_PARAMS_A,
    MV_X264_PARAMS_B,
    MV_X264_PARAMS_C,
    PERCEPTUAL_WARP_ENABLE,
    Profile,
    SAMPLE_RATE,
)


@dataclass
class RandomParams:
    seed: int
    chromatic: int
    warp: float
    rotation: float
    lumashadow: float
    lumahigh: float
    lutfreq: float
    grain: float
    dct_dc: float
    dct_ac: float
    dct_chroma: float
    desync: float
    crop: float
    pts_jitter: float
    bframes: int
    bstrat: int
    bpyramid: int
    ref: int
    mv_params: str
    crf: int
    gop: int
    vit_patch_amp: float
    vit_flicker: float
    vit_shift: int
    vit_blend: float
    pad_bytes: int
    ai_vae: float
    bloom: float
    sat_lift: float
    vae_chroma: float
    persp: float
    toon_levels: int
    cas_strength: float
    halftone_amp: float
    vibrance_intensity: float
    toon_pitch: float
    toon_presence: float
    toon_exciter: float
    toon_stereo: float
    # --- per-video structural randomization (anti-clustering) ---
    pan_freq: float
    hue_freq: float
    jnd_bright_freq: float
    jnd_contrast_freq: float
    jnd_gamma_freq: float
    vit_flicker_freq: float
    dct_t1: float
    dct_t2: float
    dct_t3: float
    pitch_shift: float
    eq_f1: int
    eq_f2: int
    echo_d1: int
    echo_d2: int
    ultra_lo: int
    ultra_hi: int
    invert_channel: int
    afft_coeff: float
    bitrate_mbps: float
    # feature dropout flags (False = skip technique on this video)
    use_pan: bool
    use_chromatic: bool
    use_grain: bool
    use_lut_freq: bool
    use_luma_crush: bool
    use_hue_drift: bool
    use_dct: bool
    use_vit_noise: bool
    use_vit_flicker: bool
    use_vit_shift: bool
    use_vit_blend: bool
    use_vignette: bool
    use_rotation: bool
    use_comb: bool
    use_phase_invert: bool
    use_ultrasonic: bool


def sample_random_params(profile: Profile, seed: int | None = None) -> RandomParams:
    if seed is None:
        seed = random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    s = profile.range_scale

    if not profile.randomize:
        return RandomParams(
            seed=seed,
            chromatic=profile.chromatic_shift,
            warp=profile.warp_strength,
            rotation=profile.micro_rotation_deg,
            lumashadow=profile.luma_shadows,
            lumahigh=profile.luma_highlights,
            lutfreq=profile.lut_freq_strength,
            grain=profile.grain_strength,
            dct_dc=profile.dct_dc_strength,
            dct_ac=profile.dct_ac_strength,
            dct_chroma=profile.dct_chroma_strength,
            desync=profile.timeline_desync_delta,
            crop=profile.crop_size,
            pts_jitter=(profile.pts_jitter_min + profile.pts_jitter_max) / 2,
            bframes=profile.b_frames,
            bstrat=profile.b_strategy,
            bpyramid=profile.b_pyramid,
            ref=profile.ref_frames,
            mv_params=MV_X264_PARAMS_A,
            crf=24,
            gop=GOP_INTERVAL,
            vit_patch_amp=profile.vit_patch_noise_amplitude,
            vit_flicker=profile.vit_luminance_flicker_max,
            vit_shift=1,
            vit_blend=profile.vit_temporal_blend_ratio,
            pad_bytes=(
                profile.behavioral_pad_max_bytes // 2 if profile.behavioral_pad else 0
            ),
            ai_vae=profile.ai_vae_grid_strength,
            bloom=profile.bloom_strength,
            sat_lift=profile.sat_lift,
            vae_chroma=profile.vae_chroma,
            persp=3.0 if PERCEPTUAL_WARP_ENABLE else 0.0,
            toon_levels=profile.toon_levels,
            cas_strength=profile.cas_strength,
            halftone_amp=profile.halftone_amp,
            vibrance_intensity=profile.vibrance_intensity,
            toon_pitch=profile.toon_pitch,
            toon_presence=profile.toon_presence,
            toon_exciter=profile.toon_exciter,
            toon_stereo=profile.toon_stereo,
            pan_freq=profile.pan_frequency,
            hue_freq=0.5,
            jnd_bright_freq=1.0,
            jnd_contrast_freq=1.5,
            jnd_gamma_freq=2.0,
            vit_flicker_freq=3.0,
            dct_t1=0.5,
            dct_t2=0.3,
            dct_t3=0.4,
            pitch_shift=profile.pitch_shift_factor,
            eq_f1=1000,
            eq_f2=4000,
            echo_d1=10,
            echo_d2=14,
            ultra_lo=18000,
            ultra_hi=20000,
            invert_channel=1,
            afft_coeff=0.002,
            bitrate_mbps=5.0,
            use_pan=profile.pan_enable,
            use_chromatic=profile.chromatic_enable,
            use_grain=True,
            use_lut_freq=profile.lut_freq_tweak,
            use_luma_crush=profile.luma_crush,
            use_hue_drift=profile.hue_spatial_drift,
            use_dct=profile.dct_geq,
            use_vit_noise=profile.vit_patch_noise,
            use_vit_flicker=profile.vit_luminance_flicker,
            use_vit_shift=profile.vit_spatial_shift,
            use_vit_blend=profile.vit_temporal_blend,
            use_vignette=True,
            use_rotation=True,
            use_comb=profile.aeco_comb_filter,
            use_phase_invert=profile.phase_invert,
            use_ultrasonic=profile.ultrasonic,
        )

    return RandomParams(
        seed=seed,
        chromatic=max(1, int(profile.chromatic_shift * s * rng.uniform(0.7, 1.3))),
        warp=profile.warp_strength * s * rng.uniform(0.8, 1.2),
        rotation=profile.micro_rotation_deg * s * rng.uniform(0.85, 1.15),
        lumashadow=profile.luma_shadows * s * rng.uniform(0.7, 1.3),
        lumahigh=profile.luma_highlights * s * rng.uniform(0.7, 1.3),
        lutfreq=profile.lut_freq_strength * s * rng.uniform(0.8, 1.2),
        grain=profile.grain_strength * s * rng.uniform(0.8, 1.2),
        dct_dc=profile.dct_dc_strength * s * rng.uniform(0.9, 1.1),
        dct_ac=profile.dct_ac_strength * s * rng.uniform(0.9, 1.1),
        dct_chroma=profile.dct_chroma_strength * s * rng.uniform(0.9, 1.1),
        desync=profile.timeline_desync_delta * s * rng.uniform(0.9, 1.1),
        crop=profile.crop_size * rng.uniform(0.98, 1.0),
        pts_jitter=rng.uniform(profile.pts_jitter_min, profile.pts_jitter_max) * s,
        bframes=(
            rng.randint(profile.b_frames, profile.b_frames + 2)
            if profile.b_frame_inject
            else 0
        ),
        bstrat=rng.choice([1, 2]) if profile.b_frame_inject else 0,
        bpyramid=rng.choice([0, 1, 2]) if profile.b_frame_inject else profile.b_pyramid,
        ref=(
            rng.randint(profile.ref_frames, profile.ref_frames + 2)
            if profile.b_frame_inject
            else 3
        ),
        mv_params=rng.choice([MV_X264_PARAMS_A, MV_X264_PARAMS_B, MV_X264_PARAMS_C]),
        crf=rng.randint(23, 26),
        gop=rng.randint(15, 45),
        vit_patch_amp=profile.vit_patch_noise_amplitude * s * rng.uniform(0.7, 1.3),
        vit_flicker=profile.vit_luminance_flicker_max * s * rng.uniform(0.7, 1.3),
        vit_shift=rng.randint(1, max(1, profile.vit_spatial_shift_max_px)),
        vit_blend=profile.vit_temporal_blend_ratio * s * rng.uniform(0.7, 1.3),
        pad_bytes=(
            rng.randint(0, profile.behavioral_pad_max_bytes)
            if profile.behavioral_pad
            else 0
        ),
        ai_vae=profile.ai_vae_grid_strength * s * rng.uniform(0.8, 1.2),
        bloom=profile.bloom_strength * s * rng.uniform(0.8, 1.2),
        sat_lift=profile.sat_lift,
        vae_chroma=profile.vae_chroma * s,
        persp=rng.uniform(2.0, 4.0) if PERCEPTUAL_WARP_ENABLE else 0.0,
        toon_levels=profile.toon_levels,
        cas_strength=profile.cas_strength * s,
        halftone_amp=profile.halftone_amp * s * rng.uniform(0.8, 1.2),
        vibrance_intensity=profile.vibrance_intensity * s,
        toon_pitch=1.0 + (profile.toon_pitch - 1.0) * s * rng.uniform(0.8, 1.2),
        toon_presence=profile.toon_presence * s,
        toon_exciter=profile.toon_exciter * s,
        toon_stereo=profile.toon_stereo,
        # --- per-video structural randomization (anti-clustering) ---
        pan_freq=profile.pan_frequency * rng.uniform(0.5, 2.0),
        hue_freq=rng.uniform(0.2, 1.2),
        jnd_bright_freq=rng.uniform(0.5, 2.0),
        jnd_contrast_freq=rng.uniform(0.8, 2.5),
        jnd_gamma_freq=rng.uniform(1.0, 3.0),
        vit_flicker_freq=rng.uniform(1.5, 5.0),
        dct_t1=rng.uniform(0.2, 0.9),
        dct_t2=rng.uniform(0.15, 0.6),
        dct_t3=rng.uniform(0.2, 0.8),
        pitch_shift=1.0 + (profile.pitch_shift_factor - 1.0) * rng.uniform(0.5, 1.8),
        eq_f1=rng.choice([800, 1000, 1250, 1600]),
        eq_f2=rng.choice([3200, 4000, 5000, 6300]),
        echo_d1=rng.randint(7, 16),
        echo_d2=rng.randint(17, 27),
        ultra_lo=rng.choice([16000, 17000, 18000]),
        ultra_hi=rng.choice([20000, 21000, 22000]),
        invert_channel=rng.randint(0, 1),
        afft_coeff=rng.uniform(0.001, 0.004),
        bitrate_mbps=rng.uniform(4.0, 6.0),
        # feature dropout: each video randomly skips a subset of techniques
        use_pan=profile.pan_enable and rng.random() >= profile.feature_dropout,
        use_chromatic=profile.chromatic_enable and rng.random() >= profile.feature_dropout,
        use_grain=rng.random() >= profile.feature_dropout,
        use_lut_freq=profile.lut_freq_tweak and rng.random() >= profile.feature_dropout,
        use_luma_crush=profile.luma_crush and rng.random() >= profile.feature_dropout,
        use_hue_drift=profile.hue_spatial_drift and rng.random() >= profile.feature_dropout,
        use_dct=profile.dct_geq and rng.random() >= profile.feature_dropout,
        use_vit_noise=profile.vit_patch_noise and rng.random() >= profile.feature_dropout,
        use_vit_flicker=profile.vit_luminance_flicker and rng.random() >= profile.feature_dropout,
        use_vit_shift=profile.vit_spatial_shift and rng.random() >= profile.feature_dropout,
        use_vit_blend=profile.vit_temporal_blend and rng.random() >= profile.feature_dropout,
        use_vignette=rng.random() >= profile.feature_dropout,
        use_rotation=rng.random() >= profile.feature_dropout,
        use_comb=profile.aeco_comb_filter and rng.random() >= profile.feature_dropout,
        use_phase_invert=profile.phase_invert and rng.random() >= profile.feature_dropout,
        use_ultrasonic=profile.ultrasonic and rng.random() >= profile.feature_dropout,
    )


def build_filter_complex(
    profile: Profile,
    rp: RandomParams,
    *,
    scale_to: tuple[int, int] | None = None,
    include_audio: bool = True,
    simple_audio: bool = False,
) -> tuple[str, list[str]]:
    """Build video+audio filter_complex and optional extra lavfi inputs.

    scale_to=(w, h) forces an exact output canvas (CLI auto mode, computed in
    stage1 with even rounding). scale_to=None keeps the input dimensions
    untouched (studio mode — the editor already rendered the exact export
    canvas; the old forced rescale upscaled user crops and its /10*10 blur
    border chain truncated 1080x1920 to 1280x2270, drifting off 9:16).
    Pass include_audio=False to drop the audio branch (e.g. corrupt source).
    Pass simple_audio=True to use only the base pitch/EQ/comb chain (drops
    afftfilt/ultrasonic/phase-invert — the NaN-prone filters) as a safe retry.
    """
    rr = rp.rotation * 3.14159 / 180
    bilinear_str = f"bilinear={profile.rotation_bilinear}"
    pan_off = profile.pan_offset_px
    pan_freq = rp.pan_freq

    vf_parts: list[str] = []

    if scale_to is not None:
        out_w, out_h = scale_to
        vf_parts.append(
            f"scale={out_w}:{out_h}:flags=bicubic,split=2[bg_stream][fg_stream]"
        )
        bg_down_w = max(2, out_w // 10)
        bg_down_h = max(2, out_h // 10)
        bg_chain = f"[bg_stream]scale={bg_down_w}:{bg_down_h}"
        bg_up = f"scale={out_w}:{out_h}:flags=bicubic"
    else:
        # No rescale: blur border derives from the untouched frame. Dimensions
        # stay exact because the studio always emits even-sized canvases.
        vf_parts.append("split=2[bg_stream][fg_stream]")
        bg_chain = "[bg_stream]scale=iw/10:ih/10"
        bg_up = "scale=iw*10:ih*10:flags=bicubic"

    # GUARD: two minterpolates in one filter_complex deadlock ffmpeg's frame
    # buffer (bg optical-flow + toon_cadence). Never stack them.
    if profile.ai_optical_flow and not profile.toon_cadence:
        # minterpolate on 1/10-scale stream simulates Sora's perfect optical flow (cheap)
        bg_chain += (
            ",minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )
    bg_chain += f",boxblur=luma_radius=4:luma_power=1,{bg_up}[blurred_border_bg]"
    vf_parts.append(bg_chain)

    fg_chain = f"[fg_stream]lenscorrection=k1={rp.warp}:k2=0.001"
    if rp.use_lut_freq:
        lf = rp.lutfreq
        fg_chain += (
            f",colorchannelmixer=rr={1 - lf}:rg={lf * 0.5}:rb={lf * 0.5}"
            f":gr={lf * 0.5}:gg={1 - lf}:gb={lf * 0.5}"
            f":br={lf * 0.5}:bg={lf * 0.5}:bb={1 - lf}"
        )
    else:
        fg_chain += (
            ",colorchannelmixer=rr=0.97:rg=0.01:rb=0.02:gr=0.01:gg=0.97:gb=0.02"
            ":br=0.02:bg=0.01:bb=0.97"
        )
    if rp.use_chromatic:
        # Static RGB channel shift (rgbashift has no time support)
        fg_chain += f",rgbashift=rh={rp.chromatic}:bh=-{rp.chromatic}"
    fg_chain += ",smartblur=lr=1:ls=0.8:lt=2:cr=1:cs=0.8:ct=2"

    if profile.ai_plastic_smoothing:
        # Aggressively smooth temporal noise -> "AI plastic" texture
        fg_chain += ",hqdn3d=luma_spatial=8:chroma_spatial=6:luma_tmp=10:chroma_tmp=8"

    # Organic grain now acts as AI "latent noise"
    # Skip when grain rounds to 0 (e.g. TOON grain_strength=0.0) — avoids a
    # no-op `noise=alls=0` filter that wastes a pass.
    if rp.use_grain and int(rp.grain) > 0:
        t_str = "t+u" if profile.grain_temporal else "u"
        fg_chain += f",noise=alls={int(rp.grain)}:allf={t_str}"

    if profile.ai_mimicry:
        # Inject 8x8 VAE decoder grid (block luminance + chroma shift = AI fingerprint)
        fg_chain += (
            f",geq=lum='lum(X,Y)+{rp.ai_vae}"
            f"*sin(2*PI*floor(X/8)/8)*sin(2*PI*floor(Y/8)/8)':"
            f"cb='cb(X,Y)+{rp.vae_chroma}*sin(2*PI*floor(X/8)/8)':"
            f"cr='cr(X,Y)+{rp.vae_chroma}*sin(2*PI*floor(Y/8)/8)'"
        )
    if rp.use_pan:
        pan_w = rp.crop
        pan_h = rp.crop
        # trunc-to-even keeps the pan-cropped foreground yuv420p-legal even
        # when the incoming frame has odd dimensions (e.g. an 855x665 crop),
        # which used to hard-fail the format conversion downstream.
        fg_chain += (
            f",crop='trunc(iw*{pan_w}/2)*2':'trunc(ih*{pan_h}/2)*2':"
            f"'(iw-ow)/2+{pan_off}*sin(t*{pan_freq})':"
            f"'(ih-oh)/2+{pan_off}*sin(t*{pan_freq})'"
        )
    else:
        fg_chain += (
            f",crop='trunc(iw*{rp.crop}/2)*2':'trunc(ih*{rp.crop}/2)*2':"
            "'(iw-ow)/2':'(ih-oh)/2'"
        )

    fg_chain += (
        ",gblur=sigma=0.5"
        f",eq=saturation={rp.sat_lift}:brightness=0.003:gamma=0.997"
    )

    # Dynamic hue drift (color pHash breaker) — hue filter has no X support, so temporal-only
    if rp.use_hue_drift:
        fg_chain += f",hue=h='5*sin(t*{rp.hue_freq:.4f})'"
    else:
        fg_chain += ",hue=h=3"

    unsharp = (
        ",unsharp=lx=5:ly=5:la=0.8:cx=5:cy=5:ca=0.4"
        if profile.ai_mimicry
        else ",unsharp=lx=3:ly=3:la=0.05"
    )
    fg_chain += (
        ",colorbalance=bs=0.02:bm=-0.02:bh=0.01"
        ",lutyuv=y='val*0.99+3'"
        + unsharp
    )

    # Dynamic perspective warp — only if proven/enabled globally
    if PERCEPTUAL_WARP_ENABLE and rp.persp > 0:
        p = rp.persp
        fg_chain += (
            f",perspective=x0='{p}*sin(t)':y0='{p}*cos(t)':"
            f"x1='W-{p}*sin(t)':y1='{p}*cos(t)':"
            f"x2='{p}*cos(t)':y2='H-{p}*sin(t)':"
            f"x3='W-{p}*cos(t)':y3='H-{p}*sin(t)':sense=forward"
        )

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

    fg_chain += ",format=yuv420p[sharp_foreground_fg]"

    vf_parts.append(fg_chain)

    vf_parts.append(
        f"[blurred_border_bg][sharp_foreground_fg]overlay="
        f"x='(W-w)/2+{pan_off}*sin(t*{pan_freq})':"
        f"y='(H-h)/2+{pan_off}*sin(t*{pan_freq})'[merged]"
    )

    if profile.bloom_enable:
        b = rp.bloom
        vf_parts.append(
            f"[merged]format=gbrp,split=2[bloom_base][bloom_pre];"
            f"[bloom_pre]gblur=sigma=10[bloomg];"
            f"[bloom_base][bloomg]blend=all_mode=screen:all_opacity={b:.3f},"
            f"format=yuv420p[bloomed]"
        )
        bloom_src = "[bloomed]"
    else:
        bloom_src = "[merged]"

    if rp.use_vignette:
        vf_parts.append(
            f"{bloom_src}vignette=angle='PI/12+0.02*sin(t*{pan_freq})'[vignetted]"
        )
        rot_src = "[vignetted]"
    else:
        rot_src = bloom_src

    if rp.use_rotation:
        vf_parts.append(
            f"{rot_src}rotate=angle='{rr}*sin(t*{pan_freq})':ow=iw:oh=ih:c=black:"
            f"{bilinear_str}[rotated]"
        )
        jnd_src = "[rotated]"
    else:
        jnd_src = rot_src

    jnd_brightness = 0.003
    jnd_contrast = 1.004
    jnd_gamma = 1.003
    if rp.use_luma_crush:
        jnd_brightness += rp.lumashadow
        jnd_contrast += rp.lumahigh
        jnd_gamma += rp.lumahigh * 0.5
    vf_parts.append(
        f"{jnd_src}eq="
        f"brightness='{jnd_brightness}*sin(t*{rp.jnd_bright_freq:.4f})':"
        f"contrast='{jnd_contrast}+{abs(rp.lumashadow) * 0.3}*cos(t*{rp.jnd_contrast_freq:.4f})':"
        f"gamma='{jnd_gamma}+0.002*sin(t*{rp.jnd_gamma_freq:.4f})'[jnd_shifted]"
    )

    if rp.use_dct:
        vf_parts.append(
            f"[jnd_shifted]geq="
            f"lum='lum(X,Y)+{rp.dct_dc}*"
            f"sin(2*PI*floor(X/8)/32+2*PI*floor(Y/8)/24+T*{rp.dct_t1:.4f})+"
            f"{rp.dct_ac}*(cos(PI*mod(X,8)/4)+sin(PI*mod(Y,8)/4))*sin(T*{rp.dct_t2:.4f})':"
            f"cb='cb(X,Y)+{rp.dct_chroma}*sin(2*PI*floor(X/16)/16+T*{rp.dct_t3:.4f})':"
            f"cr='cr(X,Y)+{rp.dct_chroma}*cos(2*PI*floor(Y/16)/16+T*{rp.dct_t3:.4f})'[dct_shifted]"
        )
        vit_chain = "dct_shifted"
    else:
        vit_chain = "jnd_shifted"

    if rp.use_vit_noise:
        # Native C-level noise (replaces per-pixel geq) -> much faster
        vf_parts.append(
            f"[{vit_chain}]noise=alls={int(rp.vit_patch_amp * 2)}:allf=t+u[vit_noisy]"
        )
        vit_chain = "vit_noisy"

    if rp.use_vit_flicker:
        vf_parts.append(
            f"[{vit_chain}]eq=brightness='{rp.vit_flicker}*sin(t*{rp.vit_flicker_freq:.4f})'[vit_flickered]"
        )
        vit_chain = "vit_flickered"

    if rp.use_vit_shift:
        mc = rp.vit_shift
        # Patch-boundary grid shift: crop+pad oscillates frame by mc px
        vf_parts.append(
            f"[{vit_chain}]crop=iw-{mc * 2}:ih-{mc * 2}:"
            f"'{mc}+{mc}*sin(n/5)':'{mc}+{mc}*cos(n/7)',"
            f"pad=iw+{mc * 2}:ih+{mc * 2}:{mc}:{mc}:color=black[vit_shifted]"
        )
        vit_chain = "vit_shifted"

    if rp.use_vit_blend:
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
        vf_parts.append(
            f"[{vit_chain}]setpts="
            f"'PTS+{rp.desync}*sin(T)/TB+{rp.pts_jitter:.6f}*sin(T)/TB'[vout]"
        )
    else:
        vf_parts.append(
            f"[{vit_chain}]setpts='PTS+{rp.desync}*sin(T)/TB'[vout]"
        )

    vf = ";".join(vf_parts)

    ns = int(SAMPLE_RATE * rp.pitch_shift)
    tf = 1.0 / rp.pitch_shift

    # Base audio chain: pitch-shift + EQ cuts + comb-filter (shared by all branches)
    audio_core = (
        f"asetrate={ns},atempo={tf:.6f},"
        f"equalizer=f={rp.eq_f1}:t=q:w=1:g=-10,equalizer=f={rp.eq_f2}:t=q:w=1:g=-10"
    )

    # Acoustic comb-filtering (Content ID destroyer)
    if rp.use_comb:
        audio_core += f",aecho=0.8:0.9:{rp.echo_d1}|{rp.echo_d2}:0.2|0.1"

    if simple_audio:
        # Safe retry chain: pitch + EQ + comb only (no afftfilt/ultrasonic/pan).
        af_base = f"[0:a]{audio_core}[aout_pre]"
        extra = []
    elif profile.toon_audio:
        # Cartoon/anime-optimized chain: formant-preserving pitch shift + clarity
        tp = rp.toon_pitch
        af_base = (
            f"[0:a]rubberband=pitch={tp:.4f}:transients=crisp,"
            "highpass=f=60,"
            "deesser=i=0.4,"
            f"highshelf=f=6000:g={rp.toon_presence:.2f},"
            f"aexciter=amount={rp.toon_exciter:.2f}:freq=7500,"
            "acompressor=threshold=-18dB:ratio=3:attack=20:release=250,"
            f"extrastereo=m={rp.toon_stereo:.3f},"
            "speechnorm=e=6.25:r=0.0005,"
            "loudnorm=I=-14:TP=-1.5:LRA=11"
            "[aout_pre]"
        )
        extra = []
    elif rp.use_phase_invert and rp.use_ultrasonic:
        # afftfilt: non-linear per-bin phase scramble
        c = rp.invert_channel
        af_base = (
            f"[0:a]{audio_core},afftfilt=real='re*cos(b*b*{rp.afft_coeff:.6f})-im*sin(b*b*{rp.afft_coeff:.6f})':"
            f"imag='re*sin(b*b*{rp.afft_coeff:.6f})+im*cos(b*b*{rp.afft_coeff:.6f})':win_size=512:overlap=0.5,"
            f"pan=stereo|c{c}=c{c}|c{1 - c}=-1*c{1 - c},volume=0.95[i];"
            f"[1:a]highpass=f={rp.ultra_lo},lowpass=f={rp.ultra_hi},volume={profile.ultrasonic_amp}[u];"
            "[i][u]amix=inputs=2:duration=first:normalize=0[aout_pre]"
        )
        extra = [
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=white:amplitude={profile.ultrasonic_amp}"
            f":sample_rate={SAMPLE_RATE}",
        ]
    elif rp.use_phase_invert:
        c = rp.invert_channel
        af_base = (
            f"[0:a]{audio_core},"
            f"afftfilt=real='re*cos(b*b*{rp.afft_coeff:.6f})-im*sin(b*b*{rp.afft_coeff:.6f})':"
            f"imag='re*sin(b*b*{rp.afft_coeff:.6f})+im*cos(b*b*{rp.afft_coeff:.6f})':win_size=512:overlap=0.5,"
            f"pan=stereo|c{c}=c{c}|c{1 - c}=-1*c{1 - c}[aout_pre]"
        )
        extra = []
    elif rp.use_ultrasonic:
        af_base = (
            f"[0:a]{audio_core}[i];"
            f"[1:a]highpass=f={rp.ultra_lo},lowpass=f={rp.ultra_hi},volume={profile.ultrasonic_amp}[u];"
            "[i][u]amix=inputs=2:duration=first:normalize=0[aout_pre]"
        )
        extra = [
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=white:amplitude={profile.ultrasonic_amp}"
            f":sample_rate={SAMPLE_RATE}",
        ]
    else:
        af_base = f"[0:a]{audio_core}[aout_pre]"
        extra = []

    if profile.pts_jitter:
        af = (
            af_base
            + f";[aout_pre]asetpts="
            f"'PTS+{rp.desync}*sin(T)/TB+{rp.pts_jitter:.6f}*sin(T)/TB'[aout]"
        )
    else:
        af = af_base.replace("[aout_pre]", "[aout]")

    if not include_audio:
        return vf, []

    return f"{vf};{af}", extra
