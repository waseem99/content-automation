from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    input_dir: Path = Field(default=Path("data/input"))
    output_dir: Path = Field(default=Path("data/output"))

    clip_count: int = Field(default=4, ge=1, le=20)
    clip_duration: float = Field(default=7.0, gt=0)
    clip_lead_in: float = Field(default=2.0, ge=0)
    min_gap: float = Field(default=15.0, ge=0)

    topic_weight: float = Field(default=0.5)
    energy_weight: float = Field(default=0.3)
    scene_weight: float = Field(default=0.2)

    scene_threshold: float = Field(default=27.0)
    energy_window_sec: float = Field(default=0.5)
    energy_top_percentile: float = Field(default=0.92)

    whisper_model: str = Field(default="small")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")

    max_duration: float | None = Field(default=None)

    # Production phase (OpenAI + ElevenLabs)
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    serpapi_api_key: str = Field(default="")
    serpapi_timeout_sec: float = Field(default=60.0, gt=0)
    serpapi_max_retries: int = Field(default=3, ge=1, le=10)
    image_download_timeout_sec: float = Field(default=90.0, gt=0)
    image_download_max_retries: int = Field(default=3, ge=1, le=10)
    web_image_fallback_to_ai: bool = Field(default=True)
    openai_image_edit_model: str = Field(default="gpt-image-1.5")
    cinematic_edit_prompt: str = Field(
        default=(
            "Apply cinematic documentary color grading, dramatic stadium lighting, "
            "rich contrast, subtle film grain, editorial sports magazine look. "
            "Keep the same composition; only enhance mood and polish."
        )
    )
    image_license_filter: str = Field(default="sur:cl")
    image_min_width: int = Field(default=600, ge=100)
    image_blocklist_domains: list[str] = Field(
        default_factory=lambda: [
            "gettyimages.com",
            "shutterstock.com",
            "alamy.com",
            "dreamstime.com",
            "reuters.com",
            "apimages.com",
            "imago-images.de",
            "icon-sport.com",
            "depositphotos.com",
            "istockphoto.com",
            "123rf.com",
            "stock.adobe.com",
        ]
    )
    image_prefer_domains: list[str] = Field(
        default_factory=lambda: [
            "commons.wikimedia.org",
            "upload.wikimedia.org",
            "wikimedia.org",
            "pexels.com",
            "pixabay.com",
        ]
    )
    image_blocklist_keywords: list[str] = Field(
        default_factory=lambda: [
            "getty",
            "shutterstock",
            "reuters",
            "afp",
            "ap photo",
            "press association",
            "watermark",
            "alamy",
            "istock",
        ]
    )

    intro_duration_sec: float = Field(default=4.0, gt=0)

    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")
    elevenlabs_model: str = Field(default="eleven_multilingual_v2")

    target_video_duration: float = Field(default=38.0)
    clip_segment_duration: float = Field(default=9.0)
    image_count: int = Field(default=3)
    video_width: int = Field(default=1080)
    video_height: int = Field(default=1920)
    video_fps: int = Field(default=30)

    enable_captions: bool = Field(default=True)
    caption_font_size: int = Field(default=58)
    caption_width: int = Field(default=900)
    caption_margin_bottom: int = Field(default=140)
    caption_words_per_group: int = Field(default=1, ge=1, le=5)
    caption_min_duration_sec: float = Field(default=0.45, gt=0)
    caption_font_path: Path | None = Field(default=None)

    crossfade_duration: float = Field(default=0.35, ge=0.0)
    ken_burns_zoom: float = Field(default=1.30, gt=1.0)
    ken_burns_pan: float = Field(default=0.35, ge=0.0, le=1.0)

    bg_music_path: Path | None = Field(default=None)
    bg_music_volume: float = Field(default=0.12, ge=0.0, le=1.0)
    bg_music_fade_in: float = Field(default=0.5, ge=0.0)
    bg_music_fade_out: float = Field(default=1.5, ge=0.0)

    # Explainer pipeline — GPT image: medium quality + vertical size (upscaled in assembly)
    openai_image_model: str = Field(default="gpt-image-1.5")
    openai_image_size: str = Field(default="1024x1536")
    openai_image_quality: str = Field(default="medium")
    max_still_beat_sec: float = Field(default=2.5, gt=0)
    max_ai_beat_sec: float = Field(default=1.0, gt=0)
    hook_beat_sec: float = Field(default=0.7, gt=0)
    explainer_crossfade_sec: float = Field(default=0.2, ge=0.0)
    hook_crossfade_sec: float = Field(default=0.15, ge=0.0)
    caption_mode: str = Field(default="keyword")
    explainer_ken_burns_zoom: float = Field(default=1.12, gt=1.0)


def get_settings() -> Settings:
    return Settings()
