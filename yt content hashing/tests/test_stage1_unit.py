from pathlib import Path

from v7_pipeline.stage1 import make_output_name, safe_unlink


def test_make_output_name_pattern():
    name = make_output_name("clip.mp4")
    assert name.startswith("clip_v7_")
    assert name.endswith(".mp4")


def test_safe_unlink(tmp_path):
    f = tmp_path / "t.bin"
    f.write_bytes(b"x")
    safe_unlink(f)
    assert not f.exists()
    safe_unlink(f)  # no throw
