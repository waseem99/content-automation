from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_generation_queue_assets_are_loaded_by_the_existing_api_client() -> None:
    client = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text(encoding="utf-8")
    queue = (ROOT / "web" / "static-creator-ui" / "assets" / "generation-queue.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "static-creator-ui" / "assets" / "generation-queue.css").read_text(encoding="utf-8")

    assert "generationJobs" in client
    assert "generationJob" in client
    assert '"generation-queue", "generation-queue.css", "generation-queue.js"' in client
    assert 'section.id = "generation-queue"' in queue
    assert "Generation and delivery queue" in queue
    assert "Attempt history" in queue
    assert "Lifecycle events" in queue
    assert "generation-queue-section" in styles


def test_generation_queue_remains_read_only_in_creator_studio() -> None:
    queue = (ROOT / "web" / "static-creator-ui" / "assets" / "generation-queue.js").read_text(encoding="utf-8")

    prohibited_calls = (
        "claimGenerationJob",
        "completeGenerationJob",
        "failGenerationJob",
        "cancelGenerationJob",
        "retryGenerationJob",
        "recoverGenerationJobs",
    )
    assert all(call not in queue for call in prohibited_calls)
