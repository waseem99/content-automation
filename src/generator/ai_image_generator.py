"""Generate stylized editorial images via OpenAI Images API."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from openai import OpenAI

from src.config import Settings
from src.generator.prompt_sanitizer import sanitize_ai_prompt

DALLE2_SIZES = ("256x256", "512x512", "1024x1024")
GPT_IMAGE_SIZES = ("1024x1024", "1024x1536", "1536x1024", "auto")
SIZE_ALIASES = {
    "1024x1792": "1024x1536",
    "1792x1024": "1536x1024",
}


def _is_gpt_image_model(model: str) -> bool:
    return model.startswith("gpt-image")


def resolve_image_generation_params(settings: Settings) -> dict:
    """Pick valid API params — GPT image models default to medium quality, vertical size."""
    model = settings.openai_image_model.lower()
    requested = SIZE_ALIASES.get(settings.openai_image_size, settings.openai_image_size)

    if model == "dall-e-2":
        size = requested if requested in DALLE2_SIZES else settings.openai_image_size
        if size not in DALLE2_SIZES:
            size = "512x512"
        return {"model": "dall-e-2", "size": size}

    if model == "dall-e-3":
        size = requested if requested in GPT_IMAGE_SIZES else "1024x1024"
        quality = settings.openai_image_quality
        if quality not in ("standard", "hd"):
            quality = "standard"
        return {"model": "dall-e-3", "size": size, "quality": quality}

    if _is_gpt_image_model(model):
        size = requested if requested in GPT_IMAGE_SIZES else "1024x1536"
        if size == "auto":
            size = "1024x1536"
        quality = settings.openai_image_quality
        if quality not in ("low", "medium", "high", "auto"):
            quality = "medium"
        return {"model": settings.openai_image_model, "size": size, "quality": quality}

    # Unknown model — pass through with safe GPT-image-style defaults
    size = requested if requested in GPT_IMAGE_SIZES else "1024x1536"
    return {"model": settings.openai_image_model, "size": size, "quality": "medium"}


def generate_ai_image(prompt: str, out_path: Path, settings: Settings) -> Path:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
    if not prompt.strip():
        raise ValueError("AI image prompt is empty.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=settings.openai_api_key)
    params = resolve_image_generation_params(settings)
    prompt = sanitize_ai_prompt(prompt)

    response = client.images.generate(
        prompt=prompt,
        n=1,
        **params,
    )

    image_data = response.data[0]
    if image_data.url:
        with httpx.Client(timeout=60.0) as http:
            content = http.get(image_data.url).content
        out_path.write_bytes(content)
    elif image_data.b64_json:
        out_path.write_bytes(base64.b64decode(image_data.b64_json))
    else:
        raise RuntimeError("OpenAI image response had no url or b64_json")

    return out_path
