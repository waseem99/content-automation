"""Incremental production checkpoint — resume without redoing completed steps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class ProductionCheckpoint(BaseModel):
    concept_id: str = ""
    voice_id: str = ""
    voice_name: str = ""
    script: str = "pending"  # pending | completed
    assembly: str = "pending"  # pending | completed
    images: dict[str, str] = Field(default_factory=dict)  # beat_key -> completed
    voice: dict[str, str] = Field(default_factory=dict)  # section_id -> completed
    updated_at: str = ""

    @classmethod
    def load(cls, path: Path) -> ProductionCheckpoint:
        if not path.exists():
            return cls()
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def mark_script_completed(self, concept_id: str) -> None:
        self.concept_id = concept_id
        self.script = "completed"

    def mark_image_completed(self, beat_key: str) -> None:
        self.images[beat_key] = "completed"

    def mark_voice_completed(self, section_id: str) -> None:
        self.voice[section_id] = "completed"

    def mark_assembly_completed(self) -> None:
        self.assembly = "completed"

    def summary(self) -> str:
        img_done = sum(1 for v in self.images.values() if v == "completed")
        voice_done = sum(1 for v in self.voice.values() if v == "completed")
        return (
            f"checkpoint: script={self.script}, images={img_done}, "
            f"voice={voice_done}, assembly={self.assembly}"
        )
