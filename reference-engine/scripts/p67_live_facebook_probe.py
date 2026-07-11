from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yt_dlp

from refintel.models import RightsDeclaration
from refintel.pipeline import ReferencePipeline


def sanitize_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:1200]


def discover_page(url: str, limit: int) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": limit,
        "noplaylist": False,
        "retries": 2,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
        clean = downloader.sanitize_info(info)
    entries = []
    for entry in clean.get("entries") or []:
        if not entry:
            continue
        entries.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "url": entry.get("webpage_url") or entry.get("url"),
                "duration": entry.get("duration"),
            }
        )
    return {
        "extractor": clean.get("extractor_key") or clean.get("extractor"),
        "title": clean.get("title"),
        "entry_count": len(entries),
        "entries": entries,
    }


def copy_analysis_artifacts(workspace: Path, output_dir: Path, source_id: str) -> list[str]:
    target_root = output_dir / "analysis" / source_id
    target_root.mkdir(parents=True, exist_ok=True)
    candidates = [
        workspace / "analysis" / "reference_analysis.json",
        workspace / "exports" / "reference_fingerprint.json",
        workspace / "frames" / "contact_sheet.jpg",
        workspace / "frames" / "frame_manifest.json",
        workspace / "transcript" / "transcript.txt",
        workspace / "transcript" / "transcript.json",
    ]
    copied: list[str] = []
    for source in candidates:
        if not source.exists():
            continue
        target = target_root / source.name
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(output_dir)))
    return copied


def process_reel(source: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="p67-facebook-") as temporary:
        workspace_root = Path(temporary) / "workspace"
        pipeline = ReferencePipeline(workspace_root)
        project = pipeline.ingest_url(
            source["url"],
            rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
            title=source["id"],
            operator_note="P67 temporary internal reference analysis; source media is not retained.",
        )
        processed = pipeline.process(
            project.reference_id,
            interval_seconds=10,
            transcription_model="tiny",
            transcription_device="cpu",
            use_local_vision=False,
        )
        workspace = Path(processed.workspace_path)
        artifacts = copy_analysis_artifacts(workspace, output_dir, source["id"])
        return {
            "status": "downloaded_and_analyzed",
            "reference_id": processed.reference_id,
            "title": processed.source.title,
            "platform": processed.source.platform.value,
            "duration_seconds": processed.media.duration_seconds if processed.media else None,
            "frame_count": len(processed.frames),
            "scene_count": len(processed.scenes),
            "transcript_segment_count": len(processed.transcript),
            "analysis_artifacts": artifacts,
            "source_media_retained": False,
        }


def run(manifest_path: Path, output_dir: Path, page_limit: int) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for source in sorted(manifest["sources"], key=lambda item: item.get("priority", 99)):
        result: dict[str, Any] = {
            "id": source["id"],
            "kind": source["kind"],
            "url": source["url"],
            "attempted_at": datetime.now(UTC).isoformat(),
        }
        try:
            if source["kind"] == "reel":
                result.update(process_reel(source, output_dir))
            else:
                discovery = discover_page(source["url"], page_limit)
                result.update(
                    {
                        "status": (
                            "page_entries_discovered"
                            if discovery["entry_count"]
                            else "page_accessible_no_entries"
                        ),
                        "discovery": discovery,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - preserve extractor diagnostics
            result.update(
                {
                    "status": "blocked_or_unavailable",
                    "error_type": type(exc).__name__,
                    "error": sanitize_error(exc),
                }
            )
        results.append(result)

    payload = {
        "schema_version": "p67.facebook_probe_result.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "rights_declaration": manifest["rights_declaration"],
        "source_media_policy": manifest["source_media_policy"],
        "summary": {
            "attempted": len(results),
            "downloaded_and_analyzed": sum(
                item["status"] == "downloaded_and_analyzed" for item in results
            ),
            "pages_with_entries": sum(
                item["status"] == "page_entries_discovered" for item in results
            ),
            "blocked_or_unavailable": sum(
                item["status"] == "blocked_or_unavailable" for item in results
            ),
        },
        "results": results,
    }
    target = output_dir / "p67-live-results.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-limit", type=int, default=5)
    args = parser.parse_args()
    payload = run(args.manifest, args.output, args.page_limit)
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
