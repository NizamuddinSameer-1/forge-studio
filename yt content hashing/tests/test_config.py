from v7_pipeline.config import PROFILES, get_profile, ProfileName


def test_all_profiles_exist():
    # Superset check: adding profiles must not break this test, but removing
    # a shipped one must.
    assert {"SAFE", "BALANCED", "AGGRESSIVE", "AIMIMIC", "MAXIMUM", "TOON"} <= set(
        PROFILES.keys()
    )


def test_default_is_balanced():
    p = get_profile("BALANCED")
    assert p.name == "BALANCED"
    assert p.ai_optical_flow is True  # matches current V7 defaults


def test_safe_disables_expensive():
    p = get_profile("SAFE")
    assert p.ai_optical_flow is False
    assert p.ai_mimicry is False
    assert p.dct_geq is False


def test_invalid_profile_raises():
    try:
        get_profile("NOPE")
        assert False, "should raise"
    except ValueError:
        pass
