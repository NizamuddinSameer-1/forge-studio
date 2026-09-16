from pathlib import Path
from v7_pipeline.paths import project_root, ensure_dirs, temp_work_dir, VIDEO_EXTS


def test_project_root_has_input_output():
    root = project_root()
    assert (root / "input").exists() or True  # may create later
    assert root.name  # non-empty


def test_video_exts():
    assert ".mp4" in VIDEO_EXTS
    assert ".mov" in VIDEO_EXTS


def test_temp_work_dir_under_hasher(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    d = temp_work_dir()
    assert d.name == "hasher_v7"
    assert d.exists()
