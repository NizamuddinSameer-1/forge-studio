from v7_pipeline.encoder import build_encode_cmd, EncodeParams


def test_build_cmd_libx264_has_maps():
    params = EncodeParams(
        encoder="libx264",
        crf=24,
        gop=30,
        b_frames=3,
        b_strategy=1,
        b_pyramid=1,
        ref_frames=4,
        mv_params="me=umh:subme=1",
        b_frame_inject=True,
        target_bitrate="5M",
        sample_rate=48000,
        frame_rate_mode="cfr",
        output_frame_rate=30,
        fps_flag="-fps_mode",
    )
    cmd = build_encode_cmd(
        local_in="in.mp4",
        local_out="out.mp4",
        filter_complex="[0:v]null[vout];[0:a]anull[aout]",
        extra_inputs=[],
        params=params,
    )
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    assert "[vout]" in cmd
    assert "[aout]" in cmd
    assert "libx264" in cmd
    assert str(params.crf) in cmd or "24" in cmd


def test_build_cmd_nvenc_uses_h264_nvenc():
    params = EncodeParams(
        encoder="nvenc",
        crf=24,
        gop=30,
        b_frames=2,
        b_strategy=1,
        b_pyramid=1,
        ref_frames=4,
        mv_params="",
        b_frame_inject=True,
        target_bitrate="5M",
        sample_rate=48000,
        frame_rate_mode="cfr",
        output_frame_rate=30,
        fps_flag="-fps_mode",
    )
    cmd = build_encode_cmd("in.mp4", "out.mp4", "fc", [], params)
    assert "h264_nvenc" in cmd
