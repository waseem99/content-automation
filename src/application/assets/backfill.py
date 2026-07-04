from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from src.application.assets.classification import (
    AssetClassification,
    AssetClassificationPolicy,
    AssetContext,
)
from src.application.assets.hashing import inspect_file
from src.application.assets.models import RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


DEFAULT_EXCLUDES = (
    "asset_store/*",
    "*/asset_store/*",
    ".git/*",
    "*/.git/*",
    "__pycache__/*",
    "*/__pycache__/*",
    "asset-backfill-report.json",
    "*/asset-backfill-report.json",
    "asset-verification-report.json",
    "*/asset-verification-report.json",
    "asset_registry.json",
    "*/asset_registry.json",
)


@dataclass(frozen=True, slots=True)
class BackfillEntry:
    path: str
    sha256: str | None
    size_bytes: int | None
    asset_type: str | None
    source_type: str | None
    lifecycle_status: str | None
    parent_candidate: str | None
    parent_asset_id: str | None
    asset_id: str | None
    action: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BackfillReport:
    registry_version: int
    root: str
    committed: bool
    entries: list[BackfillEntry]

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "registry_version": self.registry_version,
                    "root": self.root,
                    "committed": self.committed,
                    "entries": [asdict(entry) for entry in self.entries],
                },
                indent=2,
            ),
            encoding="utf-8",
        )


class BackfillService:
    def __init__(
        self,
        database: Database,
        registry: AssetRegistryService,
        policy: AssetClassificationPolicy | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.policy = policy or AssetClassificationPolicy()

    def run(
        self,
        *,
        root: Path,
        commit: bool,
        include: tuple[str, ...] = (),
        exclude: tuple[str, ...] = DEFAULT_EXCLUDES,
        max_files: int | None = None,
        created_by: str | None = None,
        continue_on_error: bool = False,
        report_path: Path | None = None,
    ) -> BackfillReport:
        resolved_root = root.expanduser().resolve(strict=True)
        parent_candidates = self._parent_candidates(resolved_root)
        files = list(self._iter_files(resolved_root, include, exclude))
        if max_files is not None:
            files = files[:max_files]

        source_paths = set(parent_candidates.values())
        files.sort(key=lambda path: (path not in source_paths, str(path)))
        entries: list[BackfillEntry] = []
        registered: dict[Path, UUID] = {}

        for path in files:
            relative = path.relative_to(resolved_root).as_posix()
            parent_path = parent_candidates.get(path)
            parent_asset_id: UUID | None = None
            try:
                inspection = inspect_file(path)
                classification = self._classify(path, parent_path)
                with unit_of_work(self.database) as uow:
                    existing = uow.assets.get_by_sha256(inspection.sha256)

                if parent_path:
                    parent_asset_id = registered.get(parent_path)
                    if parent_asset_id is None and parent_path.is_file():
                        parent_inspection = inspect_file(parent_path)
                        with unit_of_work(self.database) as uow:
                            parent_asset = uow.assets.get_by_sha256(parent_inspection.sha256)
                        parent_asset_id = parent_asset.id if parent_asset else None
                        if commit and parent_asset_id is None:
                            parent_classification = self._classify(parent_path, None)
                            parent_result = self.registry.register_file(
                                RegisterFileRequest(
                                    path=parent_path,
                                    asset_type=parent_classification.asset_type,
                                    source_type=parent_classification.source_type,
                                    lifecycle_status=parent_classification.lifecycle_status,
                                    storage_mode=StorageMode.REFERENCE_IN_PLACE,
                                    created_by=created_by,
                                    metadata={"auto_registered_as_parent": True},
                                )
                            )
                            parent_asset_id = parent_result.asset.id
                            registered[parent_path] = parent_asset_id

                if not commit:
                    entries.append(
                        BackfillEntry(
                            path=relative,
                            sha256=inspection.sha256,
                            size_bytes=inspection.size_bytes,
                            asset_type=classification.asset_type.value,
                            source_type=classification.source_type.value,
                            lifecycle_status=classification.lifecycle_status.value,
                            parent_candidate=self._display_parent(parent_path, resolved_root),
                            parent_asset_id=str(parent_asset_id) if parent_asset_id else None,
                            asset_id=str(existing.id) if existing else None,
                            action="deduplicate" if existing else "create",
                        )
                    )
                    continue

                result = self.registry.register_file(
                    RegisterFileRequest(
                        path=path,
                        asset_type=classification.asset_type,
                        source_type=classification.source_type,
                        lifecycle_status=classification.lifecycle_status,
                        storage_mode=StorageMode.REFERENCE_IN_PLACE,
                        parent_asset_id=parent_asset_id,
                        created_by=created_by,
                        metadata={
                            "backfill_root": str(resolved_root),
                            "relative_path": relative,
                        },
                    )
                )
                registered[path] = result.asset.id
                entries.append(
                    BackfillEntry(
                        path=relative,
                        sha256=result.asset.sha256,
                        size_bytes=result.asset.size_bytes,
                        asset_type=result.asset.asset_type.value,
                        source_type=result.asset.source_type.value,
                        lifecycle_status=result.asset.lifecycle_status.value,
                        parent_candidate=self._display_parent(parent_path, resolved_root),
                        parent_asset_id=(
                            str(result.asset.parent_asset_id)
                            if result.asset.parent_asset_id
                            else None
                        ),
                        asset_id=str(result.asset.id),
                        action="create" if result.created else "deduplicate",
                    )
                )
            except Exception as exc:
                entries.append(
                    BackfillEntry(
                        path=relative,
                        sha256=None,
                        size_bytes=None,
                        asset_type=None,
                        source_type=None,
                        lifecycle_status=None,
                        parent_candidate=self._display_parent(parent_path, resolved_root),
                        parent_asset_id=str(parent_asset_id) if parent_asset_id else None,
                        asset_id=None,
                        action="conflict",
                        reason=str(exc),
                    )
                )
                if not continue_on_error:
                    raise

        report = BackfillReport(
            registry_version=1,
            root=str(resolved_root),
            committed=commit,
            entries=entries,
        )
        if report_path:
            report.write(report_path)
        if commit:
            self._write_sidecars(resolved_root, entries)
        return report

    def _classify(
        self,
        path: Path,
        parent_path: Path | None,
    ) -> AssetClassification:
        name = path.name.lower()
        parts = {part.lower() for part in path.parts}
        if parent_path is not None and "_source." in parent_path.name.lower():
            context = AssetContext.WEB_IMAGE_DERIVATIVE
        elif parent_path is not None:
            context = AssetContext.EXTRACTED_MATCH_CLIP
        elif "_source." in name:
            context = AssetContext.WEB_IMAGE_SOURCE
        elif name.startswith("narration_"):
            context = AssetContext.GENERATED_VOICEOVER
        elif name in {"final_video.mp4", "preview.mp4"}:
            context = AssetContext.PREVIEW_RENDER
        elif name.startswith("image_") or name == "image_intro.png":
            context = AssetContext.WEB_IMAGE_DERIVATIVE
        elif "input" in parts and path.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"}:
            context = AssetContext.SOURCE_MATCH_VIDEO
        elif path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2"}:
            context = AssetContext.FONT
        elif "music" in name or "audio" in parts:
            context = AssetContext.BACKGROUND_MUSIC
        else:
            context = AssetContext.UNKNOWN
        return self.policy.classify(context, path)

    def _parent_candidates(self, root: Path) -> dict[Path, Path]:
        candidates: dict[Path, Path] = {}
        for manifest_path in root.rglob("manifest.json"):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                source_value = payload.get("source_video")
                if not source_value:
                    continue
                source_path = Path(source_value).expanduser()
                if not source_path.is_absolute():
                    source_path = (manifest_path.parent / source_path).resolve()
                else:
                    source_path = source_path.resolve()
                for clip in payload.get("clips", []):
                    clip_name = clip.get("file")
                    if clip_name:
                        candidates[(manifest_path.parent / clip_name).resolve()] = source_path
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue

        for source_path in root.rglob("*_source.*"):
            normalized_stem = source_path.name.split("_source.", 1)[0]
            for extension in (".png", ".jpg", ".jpeg", ".webp"):
                normalized = source_path.with_name(f"{normalized_stem}{extension}")
                if normalized.is_file():
                    candidates[normalized.resolve()] = source_path.resolve()
                    break
        return candidates

    @staticmethod
    def _iter_files(
        root: Path,
        include: tuple[str, ...],
        exclude: tuple[str, ...],
    ) -> Iterable[Path]:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if include and not any(fnmatch.fnmatch(relative, pattern) for pattern in include):
                continue
            if any(fnmatch.fnmatch(relative, pattern) for pattern in exclude):
                continue
            yield path

    @staticmethod
    def _write_sidecars(root: Path, entries: list[BackfillEntry]) -> None:
        by_folder: dict[Path, dict[str, dict[str, str | None]]] = {}
        for entry in entries:
            if not entry.asset_id or entry.action == "conflict":
                continue
            relative = Path(entry.path)
            folder = relative.parent
            by_folder.setdefault(folder, {})[relative.name] = {
                "asset_id": entry.asset_id,
                "parent_asset_id": entry.parent_asset_id,
            }
        for folder, assets in by_folder.items():
            sidecar = root / folder / "asset_registry.json"
            sidecar.write_text(
                json.dumps({"registry_version": 1, "assets": assets}, indent=2),
                encoding="utf-8",
            )

    @staticmethod
    def _display_parent(path: Path | None, root: Path) -> str | None:
        if path is None:
            return None
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return str(path)
