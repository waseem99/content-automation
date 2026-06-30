"""Audio energy analysis for crowd-reaction spikes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np


@dataclass
class EnergySpike:
    time_sec: float
    energy: float
    score: float


def detect_energy_spikes(
    wav_path: Path,
    window_sec: float = 0.5,
    top_percentile: float = 0.92,
) -> list[EnergySpike]:
    audio, sample_rate = librosa.load(str(wav_path), sr=None, mono=True)
    if audio.size == 0:
        return []

    frame_length = max(1, int(sample_rate * window_sec))
    hop_length = max(1, frame_length // 2)
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    if rms.size == 0:
        return []

    times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=hop_length)
    threshold = float(np.quantile(rms, top_percentile))
    max_rms = float(np.max(rms)) or 1.0

    spikes: list[EnergySpike] = []
    for time_sec, energy in zip(times, rms):
        if energy < threshold:
            continue
        score = float(energy / max_rms)
        spikes.append(EnergySpike(time_sec=float(time_sec), energy=float(energy), score=score))

    return _dedupe_nearby(spikes, min_gap_sec=3.0)


def _dedupe_nearby(spikes: list[EnergySpike], min_gap_sec: float) -> list[EnergySpike]:
    if not spikes:
        return []

    sorted_spikes = sorted(spikes, key=lambda s: s.energy, reverse=True)
    kept: list[EnergySpike] = []
    for spike in sorted_spikes:
        if all(abs(spike.time_sec - k.time_sec) >= min_gap_sec for k in kept):
            kept.append(spike)
    return sorted(kept, key=lambda s: s.time_sec)
