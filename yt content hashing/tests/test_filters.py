from v7_pipeline.config import get_profile
from v7_pipeline.filters import build_filter_complex, sample_random_params


def test_aimimic_has_bloom_sat_lift_and_vae_chroma():
    prof = get_profile("AIMIMIC")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "blend=all_mode=screen" in fc, "bloom glow missing"
    assert f"saturation={rp.sat_lift}" in fc, "sat lift missing"
    assert f"cb='cb(X,Y)+{rp.vae_chroma}*sin" in fc, "vae chroma missing"


def test_maximum_enables_strong_techniques():
    # MAXIMUM is strong but practical: it intentionally disables the slow
    # per-pixel `geq` filters (dct_geq, ai_mimicry, toon_*) that made it take
    # 17min for an 11s video on Colab. It keeps the fast-but-strong tricks.
    prof = get_profile("MAXIMUM")
    assert prof.vit_patch_noise is True
    assert prof.vit_temporal_blend is True
    assert prof.vit_spatial_shift is True
    assert prof.bloom_enable is True
    assert prof.ai_plastic_smoothing is True
    assert prof.phase_invert is True
    assert prof.ultrasonic is True
    assert prof.grain_strength > 0
    # the slow geq-based ones must stay OFF (performance guard)
    assert prof.dct_geq is False
    assert prof.ai_mimicry is False
    assert prof.toon_quantization is False


def test_maximum_graph_builds_strong_features():
    prof = get_profile("MAXIMUM")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "blend=all_mode=screen" in fc, "bloom missing"
    assert "tmix=frames=2" in fc, "temporal blend missing"
    assert "hqdn3d=" in fc, "plastic smoothing missing"
    # slow geq filters must NOT be in MAXIMUM (performance guard)
    assert "geq=lum=" not in fc, "dct/vae geq should be off in MAXIMUM"


def test_toon_graph_has_all_toon_filters():
    prof = get_profile("TOON")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "lutrgb=" in fc, "quantization missing"
    assert "bilateral=" in fc, "bilateral missing"
    assert "deband=" in fc, "deband missing"
    assert "vibrance=" in fc, "vibrance missing"
    assert "cas=strength=" in fc, "cas missing"
    assert "sin(X*0.8+Y*0.8)" in fc, "halftone missing"
    assert "minterpolate=fps=30:mi_mode=dup" in fc, "cadence missing"


def test_toon_has_cartoon_audio_chain():
    prof = get_profile("TOON")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "rubberband=pitch=" in fc, "rubberband pitch missing"
    assert "deesser=" in fc, "deesser missing"
    assert "aexciter=" in fc, "aexciter missing"
    assert "extrastereo=" in fc, "stereo widen missing"
    assert "loudnorm=" in fc, "loudnorm missing"


def test_safe_uses_default_audio_not_toon():
    prof = get_profile("SAFE")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "rubberband=" not in fc, "SAFE must not use toon audio"


def test_safe_has_no_toon_filters():
    prof = get_profile("SAFE")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "lutrgb=" not in fc
    assert "cas=strength=" not in fc
    assert "minterpolate=fps=30:mi_mode=dup" not in fc


def test_safe_is_unchanged_no_bloom_default_sat():
    prof = get_profile("SAFE")
    rp = sample_random_params(prof, seed=1)
    fc, _ = build_filter_complex(prof, rp)
    assert "add=" not in fc, "SAFE must not gain bloom"
    assert "saturation=0.97" in fc, "SAFE saturation must stay 0.97"


def test_different_seeds_produce_different_structure():
    """Two runs of the same profile must differ in structural params
    (frequencies, audio chain) — not just magnitudes."""
    prof = get_profile("BALANCED")
    rp1 = sample_random_params(prof, seed=1)
    rp2 = sample_random_params(prof, seed=2)
    structural = (
        "pan_freq", "hue_freq", "jnd_bright_freq", "jnd_contrast_freq",
        "jnd_gamma_freq", "vit_flicker_freq", "dct_t1", "dct_t2", "dct_t3",
        "pitch_shift", "eq_f1", "eq_f2", "echo_d1", "echo_d2",
        "ultra_lo", "ultra_hi", "afft_coeff", "bitrate_mbps",
    )
    diffs = [k for k in structural if getattr(rp1, k) != getattr(rp2, k)]
    assert len(diffs) >= 10, f"too few structural diffs between seeds: {diffs}"


def test_feature_dropout_produces_varied_graphs():
    """Across many seeds, some techniques must appear and some must vanish."""
    prof = get_profile("BALANCED")
    built = [
        build_filter_complex(prof, sample_random_params(prof, seed=s))
        for s in range(20)
    ]
    graphs = [fc for fc, _ in built]
    # pan crop oscillation present in some, absent in others
    has_pan = sum("(iw-iw*" in g for g in graphs)
    assert 0 < has_pan < 20, f"pan never dropped or never kept: {has_pan}/20"
    # dct geq present in some, absent in others
    has_dct = sum("dct_shifted" in g for g in graphs)
    assert 0 < has_dct < 20, f"dct never dropped or never kept: {has_dct}/20"
    # ultrasonic second lavfi input present in some, absent in others
    has_ultra = sum(any("anoisesrc" in a for a in extra) for _, extra in built)
    assert 0 < has_ultra < 20, f"ultrasonic never dropped or never kept: {has_ultra}/20"


def test_dropout_zero_disables_dropout():
    """feature_dropout=0 must keep every profile-enabled technique."""
    import dataclasses
    prof = dataclasses.replace(get_profile("BALANCED"), feature_dropout=0.0)
    for seed in range(5):
        rp = sample_random_params(prof, seed=seed)
        assert rp.use_pan and rp.use_chromatic and rp.use_grain
        assert rp.use_dct and rp.use_vit_noise and rp.use_vit_blend
        assert rp.use_comb and rp.use_phase_invert and rp.use_ultrasonic


def test_dropout_one_disables_everything_optional():
    """feature_dropout=1 must drop every droppable technique."""
    import dataclasses
    prof = dataclasses.replace(get_profile("BALANCED"), feature_dropout=1.0)
    rp = sample_random_params(prof, seed=1)
    assert not rp.use_pan and not rp.use_chromatic and not rp.use_grain
    assert not rp.use_dct and not rp.use_vit_noise and not rp.use_vit_blend
    assert not rp.use_comb and not rp.use_phase_invert and not rp.use_ultrasonic
    fc, extra = build_filter_complex(prof, rp)
    assert "anoisesrc" not in fc and extra == []
    assert "dct_shifted" not in fc
    assert "aecho" not in fc
