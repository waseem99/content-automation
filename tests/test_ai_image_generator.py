"""Tests for OpenAI image generation params."""

from src.config import Settings, get_settings
from src.generator.ai_image_generator import resolve_image_generation_params


def test_config_defaults_use_gpt_image_medium():
    settings = get_settings()
    params = resolve_image_generation_params(settings)
    assert params["model"] == "gpt-image-1.5"
    assert params["size"] == "1024x1536"
    assert params["quality"] == "medium"


def test_gpt_image_maps_legacy_vertical_size():
    settings = Settings(openai_image_model="gpt-image-1.5", openai_image_size="1024x1792")
    params = resolve_image_generation_params(settings)
    assert params["model"] == "gpt-image-1.5"
    assert params["size"] == "1024x1536"
    assert params["quality"] == "medium"


def test_gpt_image_low_cost_preset():
    settings = Settings(
        openai_image_model="gpt-image-1.5",
        openai_image_size="1024x1024",
        openai_image_quality="low",
    )
    params = resolve_image_generation_params(settings)
    assert params["size"] == "1024x1024"
    assert params["quality"] == "low"


def test_dalle2_still_supported():
    settings = Settings(openai_image_model="dall-e-2", openai_image_size="512x512")
    params = resolve_image_generation_params(settings)
    assert params["model"] == "dall-e-2"
    assert params["size"] == "512x512"
