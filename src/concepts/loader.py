"""Load and validate explainer concept YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ExtractionConfig(BaseModel):
    clips_per_video: int = Field(default=4, ge=1, le=20)
    clip_duration: float = Field(default=7.0, gt=0)
    topics: list[str] = Field(default_factory=list)


class ConceptSection(BaseModel):
    id: str
    type: Literal["hook", "premise", "entity_block", "comparison", "cta"]
    duration_sec: float = Field(default=0.0, ge=0)
    beat_style: Literal["rapid", "normal"] = "normal"
    beat_count: int = Field(default=5, ge=1, le=20)
    entity_name: str = ""
    theme: str = ""
    keyword: str = ""
    min_clips: int = Field(default=0, ge=0)
    max_clips: int = Field(default=2, ge=0)

    @field_validator("max_clips")
    @classmethod
    def max_clips_gte_min(cls, value: int, info) -> int:
        min_clips = info.data.get("min_clips", 0)
        if value < min_clips:
            return min_clips
        return value


class ConceptDefinition(BaseModel):
    concept_id: str
    title: str
    target_duration_sec: float = Field(default=120.0, gt=0)
    context: str = ""
    stats: dict[str, str | int | float] = Field(default_factory=dict)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    sections: list[ConceptSection] = Field(default_factory=list)

    def entity_sections(self) -> list[ConceptSection]:
        return [s for s in self.sections if s.type == "entity_block"]

    def narrated_sections(self) -> list[ConceptSection]:
        return [s for s in self.sections if s.type != "premise" and s.duration_sec > 0]


def load_concept(path: Path) -> ConceptDefinition:
    if not path.exists():
        raise FileNotFoundError(f"Concept file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid concept YAML: {path}")
    return ConceptDefinition.model_validate(raw)
