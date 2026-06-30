"""Pydantic models for the production pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScriptSegment(BaseModel):
    order: int
    type: Literal["intro", "image", "clip"]
    narration: str = ""
    image_index: int | None = None
    image_prompt: str = ""
    image_search_query: str = ""
    clip_file: str = ""
    target_duration_sec: float = 0.0


class ProductionPlan(BaseModel):
    title: str
    topic: str
    target_duration_sec: float = 38.0
    clip_duration_sec: float = 9.0
    segments: list[ScriptSegment] = Field(default_factory=list)

    def intro_segment(self) -> ScriptSegment | None:
        for segment in self.segments:
            if segment.type == "intro":
                return segment
        return None

    def image_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type == "image"]

    def clip_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type == "clip"]

    def narrated_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type in ("intro", "image") and s.narration.strip()]

    def visual_segments(self) -> list[ScriptSegment]:
        return [s for s in self.segments if s.type in ("intro", "image")]


class VisualBeat(BaseModel):
    duration_sec: float = Field(gt=0)
    visual_type: Literal["web_image", "ai_image", "clip"]
    image_search_query: str = ""
    ai_image_prompt: str = ""
    clip_file: str = ""
    caption_highlight: str = ""
    cinematic_edit: bool = False
    cinematic_edit_prompt: str = ""


class ExplainerSection(BaseModel):
    id: str
    section_type: str
    entity_name: str = ""
    theme: str = ""
    keyword: str = ""
    narration: str = ""
    target_duration_sec: float = Field(default=0.0, ge=0)
    beats: list[VisualBeat] = Field(default_factory=list)

    def beat_duration_sum(self) -> float:
        return sum(beat.duration_sec for beat in self.beats)


class ExplainerPlan(BaseModel):
    concept_id: str
    title: str
    target_duration_sec: float = Field(default=120.0, gt=0)
    sections: list[ExplainerSection] = Field(default_factory=list)

    def narrated_sections(self) -> list[ExplainerSection]:
        return [s for s in self.sections if s.narration.strip()]

    def entity_sections(self) -> list[ExplainerSection]:
        return [s for s in self.sections if s.section_type == "entity_block"]
