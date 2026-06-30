"""Unit tests for moment ranking."""

from src.analyzer.audio_analyzer import EnergySpike
from src.config import Settings
from src.ranker.moment_ranker import rank_moments


def test_rank_moments_fills_requested_count_on_short_video():
    settings = Settings(clip_count=3, clip_duration=5, min_gap=15)
    spikes = [
        EnergySpike(time_sec=8.0, energy=0.9, score=0.9),
        EnergySpike(time_sec=16.0, energy=0.8, score=0.8),
        EnergySpike(time_sec=24.0, energy=0.7, score=0.7),
    ]
    windows = rank_moments(
        scenes=[],
        energy_spikes=spikes,
        transcript_hits=[],
        video_duration=30.0,
        settings=settings,
    )
    assert len(windows) == 3
    assert windows[0].start < windows[1].start < windows[2].start
