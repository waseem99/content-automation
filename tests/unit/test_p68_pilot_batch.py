from __future__ import annotations

import json
from pathlib import Path

from src.p68_pilot_batch import evaluate_batch, evaluate_pilot, load_benchmark


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "docs" / "operations" / "p68-quality-benchmark.json"


def record(tmp_path: Path, index: int, brand: str) -> dict[str, object]:
    output = tmp_path / f"pilot-{index}.mp4"
    output.write_bytes(f"fixture-{index}".encode())
    benchmark = load_benchmark(BENCHMARK)
    dimensions = [item["id"] for item in benchmark["dimensions"]]
    return {
        "pilot_id": f"pilot-{index}",
        "brand_profile": brand,
        "output_path": str(output),
        "probe": {
            "duration_seconds": 30,
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "video_codec": "h264",
            "audio_codec": "aac",
        },
        "shot_count": 6,
        "human_review": {
            "reviewer_role": "creative director fixture",
            "decision": "production_candidate",
            "scores": {name: 8.5 for name in dimensions},
            "evidence_notes": {name: f"Fixture evidence for {name}." for name in dimensions},
        },
        "factual_sources": [{"url": "https://example.org/source"}],
        "rights_evidence": [{"status": "fixture"}],
        "originality_evidence": [{"status": "fixture"}],
        "advertiser_suitability_evidence": [{"status": "fixture"}],
        "revision_history": [{"revision": 1, "status": "fixture"}],
    }


def test_missing_real_video_and_human_evidence_cannot_close_p68(tmp_path: Path) -> None:
    benchmark = load_benchmark(BENCHMARK)
    result = evaluate_pilot(
        {
            "pilot_id": "missing",
            "brand_profile": "rawr_nation",
            "output_path": str(tmp_path / "missing.mp4"),
        },
        benchmark,
    )
    assert result["production_candidate"] is False
    assert "real_video_file_required" in result["errors"]
    assert "human_decision_required" in result["errors"]
    assert result["publish_allowed"] is False


def test_exactly_three_per_brand_with_complete_reviews_can_reach_closeout(tmp_path: Path) -> None:
    benchmark = load_benchmark(BENCHMARK)
    records = [record(tmp_path, index, "rawr_nation" if index <= 3 else "animal_x") for index in range(1, 7)]
    result = evaluate_batch(records, benchmark)
    assert result["brand_counts"] == {"rawr_nation": 3, "animal_x": 3}
    assert result["production_candidate_count"] == 6
    assert result["p68_closeout_ready"] is True
    assert result["historiq_and_ani_films_adaptation_allowed"] is True
    assert result["publish_allowed"] is False
