from __future__ import annotations

from src.domain.asset_models import Asset


_MATCH_ROLES = {"source_match_video", "extracted_match_clip"}
_MATCH_CATEGORIES = {"broadcast_footage", "match_footage"}


class MatchFootageClassifier:
    @staticmethod
    def is_match_footage(asset: Asset, ancestors: tuple[Asset, ...] = ()) -> bool:
        candidates = (asset, *ancestors)
        for candidate in candidates:
            role = str(candidate.metadata.get("pipeline_role", "")).strip().lower()
            category = str(candidate.metadata.get("source_category", "")).strip().lower()
            if role in _MATCH_ROLES or category in _MATCH_CATEGORIES:
                return True
        return False
