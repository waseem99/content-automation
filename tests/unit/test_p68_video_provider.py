from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.p68_video_provider import ComfyUIVideoProvider, VideoGenerationRequest, VideoJob, VideoJobStatus


def request(tmp_path: Path) -> VideoGenerationRequest:
    image = tmp_path / "master.png"
    image.write_bytes(b"image")
    return VideoGenerationRequest(
        pilot_id="pilot-one",
        shot_id="S01",
        input_image=image,
        prompt="The elephant shifts its weight naturally.",
        negative_prompt="static, distorted anatomy",
        duration_seconds=5.5,
        seed=7,
    )


def workflow(tmp_path: Path) -> Path:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "{{INPUT_IMAGE}}"}},
                "2": {"class_type": "Prompt", "inputs": {"text": "{{POSITIVE_PROMPT}}", "seed": "{{SEED}}"}},
                "3": {"class_type": "Video", "inputs": {"width": "{{WIDTH}}", "height": "{{HEIGHT}}", "length": "{{FRAME_COUNT}}"}},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_wan_frame_count_rounds_up_to_four_n_plus_one(tmp_path: Path) -> None:
    item = request(tmp_path)
    assert (item.frame_count - 1) % 4 == 0
    assert item.frame_count >= item.duration_seconds * item.fps


def test_comfyui_submit_poll_download_and_template_replacement(tmp_path: Path) -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        if incoming.url.path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"name": "mock-gpu"}]})
        if incoming.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "uploaded.png"})
        if incoming.url.path == "/prompt":
            payload = json.loads(incoming.content)
            assert payload["prompt"]["1"]["inputs"]["image"] == "uploaded.png"
            assert payload["prompt"]["2"]["inputs"]["seed"] == 7
            assert payload["prompt"]["3"]["inputs"]["height"] == 1280
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if incoming.url.path == "/history/job-1":
            return httpx.Response(
                200,
                json={
                    "job-1": {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {"9": {"videos": [{"filename": "clip.webm", "subfolder": "p68", "type": "output"}]}},
                    }
                },
            )
        if incoming.url.path == "/view":
            return httpx.Response(200, content=b"video")
        raise AssertionError(incoming.url)

    client = httpx.Client(base_url="http://rn.test", transport=httpx.MockTransport(handler))
    provider = ComfyUIVideoProvider(base_url="http://rn.test", workflow_path=workflow(tmp_path), client=client)
    assert provider.health()["healthy"] is True
    job = provider.submit(request(tmp_path))
    assert job.status == VideoJobStatus.QUEUED
    complete = provider.poll(job)
    assert complete.status == VideoJobStatus.SUCCEEDED
    output = provider.download(complete, tmp_path / "clip")
    assert output.name == "clip.webm"
    assert output.read_bytes() == b"video"


def test_poll_keeps_incomplete_history_running_and_rejects_non_video_completion(tmp_path: Path) -> None:
    states = iter(
        [
            {"job-1": {"status": {"status_str": "running", "completed": False}, "outputs": {}}},
            {
                "job-1": {
                    "status": {"status_str": "success", "completed": True},
                    "outputs": {"9": {"images": [{"filename": "preview.png", "type": "output"}]}},
                }
            },
        ]
    )

    def handler(incoming: httpx.Request) -> httpx.Response:
        if incoming.url.path == "/history/job-1":
            return httpx.Response(200, json=next(states))
        raise AssertionError(incoming.url)

    client = httpx.Client(base_url="http://rn.test", transport=httpx.MockTransport(handler))
    provider = ComfyUIVideoProvider(base_url="http://rn.test", workflow_path=workflow(tmp_path), client=client)
    item = request(tmp_path)
    queued = VideoJob("rn-comfyui-wan", "job-1", item.idempotency_key, VideoJobStatus.QUEUED, "now", item.model_id)
    assert provider.poll(queued).status == VideoJobStatus.RUNNING
    failed = provider.poll(queued)
    assert failed.status == VideoJobStatus.FAILED
    assert "video output" in str(failed.error)


def test_download_refuses_empty_response_without_leaving_partial_file(tmp_path: Path) -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        if incoming.url.path == "/view":
            return httpx.Response(200, content=b"")
        raise AssertionError(incoming.url)

    client = httpx.Client(base_url="http://rn.test", transport=httpx.MockTransport(handler))
    provider = ComfyUIVideoProvider(base_url="http://rn.test", workflow_path=workflow(tmp_path), client=client)
    job = VideoJob(
        "rn-comfyui-wan",
        "job-1",
        "key",
        VideoJobStatus.SUCCEEDED,
        "now",
        "wan2.2-ti2v-5b",
        {"filename": "clip.mp4", "type": "output"},
    )
    with pytest.raises(RuntimeError, match="empty"):
        provider.download(job, tmp_path / "clip")
    assert not (tmp_path / "clip.partial.mp4").exists()
