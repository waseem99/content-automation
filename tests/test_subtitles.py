"""Tests for subtitle helpers."""

from src.assembler.subtitles import format_srt_timestamp, wrap_caption_text, write_srt


def test_wrap_caption_text():
    text = "In 2014, the world held its breath as Neymar faced a devastating injury"
    wrapped = wrap_caption_text(text, width=20)
    assert "\n" in wrapped


def test_write_srt(tmp_path):
    srt_path = tmp_path / "test.srt"
    write_srt([(0.0, 5.5, "Hello world")], srt_path)
    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:05,500" in content
    assert "HELLO WORLD" in content


def test_format_srt_timestamp():
    assert format_srt_timestamp(65.5) == "00:01:05,500"
