from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Protocol

from .models import ReferenceFingerprint


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Deterministic offline fallback for tests and CPU-only installations."""

    name = "hash-token-fallback"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def fingerprint_text(fingerprint: ReferenceFingerprint) -> str:
    return "\n".join(
        [
            fingerprint.title,
            str(fingerprint.hook),
            str(fingerprint.story_arc),
            str(fingerprint.pacing),
            str(fingerprint.visual_language),
            *fingerprint.reusable_mechanics,
        ]
    )


class ReferenceIndex:
    def __init__(
        self,
        index_root: Path,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self.root = index_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.provider = provider or HashEmbeddingProvider()
        self.records_path = self.root / "records.json"
        self.vectors_path = self.root / "vectors.json"

    def rebuild(self, fingerprint_paths: list[Path]) -> None:
        records: list[dict[str, object]] = []
        vectors: list[list[float]] = []
        for path in fingerprint_paths:
            fingerprint = ReferenceFingerprint.model_validate_json(path.read_text(encoding="utf-8"))
            records.append(
                {
                    "reference_id": fingerprint.reference_id,
                    "title": fingerprint.title,
                    "platform": fingerprint.platform.value,
                    "duration_seconds": fingerprint.duration_seconds,
                    "path": str(path.resolve()),
                }
            )
            vectors.append(self.provider.embed(fingerprint_text(fingerprint)))
        self.records_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        self.vectors_path.write_text(json.dumps(vectors), encoding="utf-8")
        (self.root / "index_meta.json").write_text(
            json.dumps(
                {
                    "schema_version": "p66.reference_index.v1",
                    "provider": self.provider.name,
                    "dimensions": self.provider.dimensions,
                    "count": len(records),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def search(self, query: str, limit: int = 10) -> list[dict[str, object]]:
        if not self.records_path.exists() or not self.vectors_path.exists():
            return []
        records = json.loads(self.records_path.read_text(encoding="utf-8"))
        vectors = json.loads(self.vectors_path.read_text(encoding="utf-8"))
        query_vector = self.provider.embed(query)
        results: list[dict[str, object]] = []
        for record, vector in zip(records, vectors, strict=True):
            score = sum(float(left) * float(right) for left, right in zip(query_vector, vector, strict=True))
            results.append({**record, "similarity": round(score, 4)})
        return sorted(results, key=lambda item: float(item["similarity"]), reverse=True)[:limit]

    def export_faiss(self) -> Path | None:
        """Optionally produce a FAISS index when numpy/faiss are installed."""
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            return None
        vectors = json.loads(self.vectors_path.read_text(encoding="utf-8"))
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.size == 0:
            return None
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        target = self.root / "references.faiss"
        faiss.write_index(index, str(target))
        return target
