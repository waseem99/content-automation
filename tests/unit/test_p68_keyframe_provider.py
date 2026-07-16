from __future__ import annotations

import json
from pathlib import Path

import httpx

from src.p68_keyframe_provider import ComfyUIKeyframeProvider, ImageJobStatus, KeyframeGenerationRequest


def request() -> KeyframeGenerationRequest:
    return KeyframeGenerationRequest("pilot", "S01", "original portrait", "text, logo", 42)


def test_request_identity_is_deterministic_and_portrait() -> None:
    first, second = request(), request()
    assert first.idempotency_key == second.idempotency_key
    assert (first.width, first.height) == (1024, 1824)


def test_comfyui_workflow_submit_poll_and_download(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({"1": {"inputs": {"text": "{{POSITIVE_PROMPT}}", "seed": "{{SEED}}", "ckpt": "{{CHECKPOINT}}"}}}))

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/prompt":
            body = json.loads(req.content)
            assert body["prompt"]["1"]["inputs"] == {"text": "original portrait", "seed": 42, "ckpt": "model.safetensors"}
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if req.url.path == "/history/job-1":
            return httpx.Response(200, json={"job-1": {"status": {"completed": True}, "outputs": {"7": {"images": [{"filename": "out.png", "type": "output"}]}}}})
        if req.url.path == "/view":
            return httpx.Response(200, content=b"image-bytes")
        raise AssertionError(req.url)

    provider = ComfyUIKeyframeProvider(
        base_url="https://worker.test", workflow_path=workflow, checkpoint="model.safetensors",
        client=httpx.Client(base_url="https://worker.test", transport=httpx.MockTransport(handler)),
    )
    job = provider.submit(request())
    assert job.status == ImageJobStatus.QUEUED
    job = provider.poll(job)
    assert job.status == ImageJobStatus.SUCCEEDED
    output = provider.download(job, tmp_path / "out.png")
    assert output.read_bytes() == b"image-bytes"
