from v7_pipeline.validate import duration_tolerance_ok, ValidationResult


def test_duration_tolerance_within():
    assert duration_tolerance_ok(10.0, 10.1) is True
    assert duration_tolerance_ok(10.0, 10.5) is True  # 0.5s rule


def test_duration_tolerance_fail():
    assert duration_tolerance_ok(10.0, 12.0) is False


def test_validation_result_ok_fields():
    r = ValidationResult(
        ok=True, has_video=True, has_audio=True, duration=1.0, size_bytes=5000, message="ok"
    )
    assert r.ok
