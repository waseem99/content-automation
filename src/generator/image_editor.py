"""Cinematic polish for web-sourced images via OpenAI image edit."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from openai import BadRequestError, OpenAI

from src.config import Settings
from src.generator.prompt_sanitizer import sanitize_ai_prompt
from src.generator.ai_image_generator import resolve_image_generation_params
from src.generator.prompt_sanitizer import DEFAULT_CINEMATIC_EDIT_PROMPT, sanitize_ai_prompt


def apply_cinematic_edit(
    source_path: Path,
    out_path: Path,
    settings: Settings,
    edit_prompt: str = "",
) -> Path:
    """
    Edit an existing image (from SerpAPI) for cinematic look.
    Editing real photos avoids public-figure generation blocks.
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    prompt = sanitize_ai_prompt(edit_prompt or settings.cinematic_edit_prompt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=settings.openai_api_key)
    params = resolve_image_generation_params(settings)
    model = settings.openai_image_edit_model or params.get("model", "gpt-image-1.5")
    size = params.get("size", "1024x1536")

    with source_path.open("rb") as image_file:
        try:
            response = client.images.edit(
                model=model,
                image=image_file,
                prompt=prompt,
                size=size,
                n=1,
            )
        except BadRequestError as exc:
            if "moderation" in str(exc).lower():
                # If edit blocked, keep the original web image
                print(f"  Cinematic edit skipped (moderation): using original web image", flush=True)
                if source_path != out_path:
                    out_path.write_bytes(source_path.read_bytes())
                return out_path
            raise

    image_data = response.data[0]
    if image_data.url:
        with httpx.Client(timeout=90.0) as http:
            content = http.get(image_data.url).content
        out_path.write_bytes(content)
    elif image_data.b64_json:
        out_path.write_bytes(base64.b64decode(image_data.b64_json))
    else:
        out_path.write_bytes(source_path.read_bytes())

    return out_path
