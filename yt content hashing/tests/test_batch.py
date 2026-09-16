from pathlib import Path

from v7_pipeline.batch import list_videos, should_skip_existing, summarize


def test_list_videos(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"x")
    (tmp_path / "c.MOV").write_bytes(b"x")
    vids = list_videos(tmp_path)
    names = {v.name for v in vids}
    assert "a.mp4" in names
    assert "c.MOV" in names
    assert "b.txt" not in names


def test_skip_existing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "clip_v7_20260101_000000_0.mp4").write_bytes(b"x")
    assert should_skip_existing(Path("clip.mp4"), out) is True
    assert should_skip_existing(Path("other.mp4"), out) is False


def test_summarize():
    s = summarize([("a", "ok"), ("b", None), ("c", "SKIP")])
    assert s["ok"] == 1 and s["err"] == 1 and s["skip"] == 1
