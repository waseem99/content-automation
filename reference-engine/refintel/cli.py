from __future__ import annotations

import json
import shutil
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .acquisition import AcquisitionService, sanitize_diagnostic
from .adapters import capability_matrix, normalize_reference
from .facebook import (
    open_facebook_session,
    resolve_facebook_share_url,
    run_facebook_page_batch,
)
from .fingerprint import compare_fingerprints, load_fingerprint
from .ingest import validate_local_cookie_browser
from .models import RightsDeclaration
from .pipeline import ReferencePipeline, tool_versions
from .portfolio_sync import build_portfolio_sync_packet
from .settings import RefIntelSettings
from .temporal import build_temporal_report

app = typer.Typer(
    no_args_is_help=True,
    help="Local-first video reference ingestion, analysis, reporting, and brief export.",
)
console = Console()


def pipeline(workspace: Path) -> ReferencePipeline:
    return ReferencePipeline(workspace.expanduser().resolve())


@app.command("capabilities")
def capabilities(
    as_json: bool = typer.Option(False, "--json", help="Print the machine-readable matrix."),
) -> None:
    """Show honest acquisition support for every social platform adapter."""
    rows = capability_matrix()
    if as_json:
        console.print_json(json.dumps([row.model_dump(mode="json") for row in rows]))
        return
    table = Table(title="Social Reference Adapter Capabilities")
    for column in ("platform", "direct video", "image/carousel", "profile discovery"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row.platform.value,
            row.direct_video.value,
            row.image_or_carousel.value,
            row.profile_discovery.value,
        )
    console.print(table)


@app.command("plan-url")
def plan_url(urls: list[str] = typer.Argument(..., min=1)) -> None:
    """Normalize social URLs and plan acquisition without downloading anything."""
    plans = [normalize_reference(url).model_dump(mode="json") for url in urls]
    console.print_json(json.dumps({"plans": plans}))


@app.command("discover-url")
def discover_url(
    url: str = typer.Argument(..., help="Public channel/profile/collection URL."),
    limit: int = typer.Option(20, min=1, max=100),
    cookies_from_browser: str | None = typer.Option(
        None,
        help="Optional operator-owned local browser; session data is never persisted.",
    ),
    cookie_file: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional local cookie jar; path and contents are never persisted.",
    ),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Discover direct candidates without downloading source media."""
    browser = validate_local_cookie_browser(cookies_from_browser)
    local_cookie_file = cookie_file.expanduser().resolve() if cookie_file else None
    manifest = AcquisitionService().discover(
        url,
        limit=limit,
        cookies_from_browser=browser,
        cookie_file=local_cookie_file,
    )
    run_dir = workspace.expanduser().resolve() / "discovery-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / (
        f"{manifest.platform.value}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    )
    target.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    console.print_json(manifest.model_dump_json())
    console.print(target)


@app.command("acquire-batch")
def acquire_batch(
    urls: list[str] = typer.Argument(..., min=1, help="Direct public media URLs."),
    rights: RightsDeclaration = typer.Option(..., help="Mandatory rights declaration."),
    cookies_from_browser: str | None = typer.Option(
        None,
        help="Optional operator-owned local browser; session data is never persisted.",
    ),
    cookie_file: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional local cookie jar; path and contents are never persisted.",
    ),
    force_new: bool = typer.Option(False),
    facebook_browser_profile: Path = typer.Option(
        Path.home() / ".local" / "share" / "refintel" / "facebook-browser",
        help="Dedicated local profile used only to resolve Facebook share links.",
    ),
    headed_facebook: bool = typer.Option(
        False,
        help="Show Chromium while resolving Facebook share links.",
    ),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Acquire direct references independently and preserve per-item failures."""
    browser = validate_local_cookie_browser(cookies_from_browser)
    local_cookie_file = cookie_file.expanduser().resolve() if cookie_file else None
    if browser and local_cookie_file:
        raise typer.BadParameter("Use either cookies-from-browser or cookie-file, not both")
    engine = pipeline(workspace)
    results: list[dict[str, object]] = []
    for index, url in enumerate(urls, start=1):
        try:
            planned = normalize_reference(url)
        except Exception as exc:  # noqa: BLE001 - isolate invalid item
            results.append(
                {
                    "index": index,
                    "url": "<invalid-or-unsupported>",
                    "platform": "unknown",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": sanitize_diagnostic(exc),
                    "fallback_action": (
                        "Provide an absolute supported public URL or use ingest-file."
                    ),
                }
            )
            continue
        resolution: dict[str, object] | None = None
        if planned.requires_resolution:
            try:
                resolution = resolve_facebook_share_url(
                    url,
                    profile_dir=facebook_browser_profile,
                    headless=not headed_facebook,
                )
                url = str(resolution["resolved_url"])
                planned = normalize_reference(url)
            except Exception as exc:  # noqa: BLE001 - isolate redirect failure
                results.append(
                    {
                        "index": index,
                        "url": planned.canonical_url,
                        "platform": planned.platform.value,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": sanitize_diagnostic(
                            exc,
                            private_paths=[facebook_browser_profile, local_cookie_file]
                            if local_cookie_file
                            else [facebook_browser_profile],
                        ),
                        "fallback_action": (
                            "Run facebook-login, retry, or provide the stable page/reel URL."
                        ),
                    }
                )
                continue
        result: dict[str, object] = {
            "index": index,
            "url": planned.canonical_url,
            "platform": planned.platform.value,
        }
        if resolution:
            result["share_resolution"] = {
                "share_url": resolution["share_url"],
                "resolved_url": resolution["resolved_url"],
                "input_type": resolution["input_type"],
            }
        try:
            project = engine.ingest_url(
                url,
                rights=rights,
                cookies_from_browser=browser,
                cookie_file=local_cookie_file,
                force_new=force_new,
            )
            result.update(
                {
                    "status": "acquired",
                    "reference_id": project.reference_id,
                    "workspace": project.workspace_path,
                }
            )
        except Exception as exc:  # noqa: BLE001 - preserve isolated item failure
            result.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": sanitize_diagnostic(
                        exc,
                        private_paths=[path for path in (local_cookie_file,) if path],
                    ),
                    "fallback_action": "Use ingest-file with an authorized local export.",
                }
            )
        results.append(result)
    run_id = f"batch-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    run_dir = workspace.expanduser().resolve() / "acquisition-runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "p75.acquisition_batch.v1",
        "run_id": run_id,
        "rights_declaration": rights.value,
        "summary": {
            "attempted": len(results),
            "acquired": sum(item["status"] == "acquired" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
        },
        "results": results,
        "security": {
            "credentials_persisted": False,
            "cookie_paths_persisted": False,
            "automatic_publication": False,
        },
    }
    target = run_dir / "batch-result.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print_json(json.dumps(payload))
    console.print(target)


@app.command("doctor")
def doctor(
    workspace: Path = typer.Option(Path("workspace"), help="Local workspace root."),
) -> None:
    """Check the local machine before processing media."""
    versions = tool_versions()
    table = Table(title="Reference Intelligence Environment")
    table.add_column("Capability")
    table.add_column("Status")
    table.add_column("Version / path")
    checks = {
        "Python": versions.get("python"),
        "FFmpeg": versions.get("ffmpeg"),
        "ffprobe": versions.get("ffprobe"),
        "yt-dlp": versions.get("yt-dlp"),
        "PySceneDetect": versions.get("pyscenedetect"),
        "faster-whisper": versions.get("faster-whisper"),
        "Playwright": versions.get("playwright"),
        "Ollama": shutil.which("ollama"),
    }
    for name, value in checks.items():
        table.add_row(name, "ready" if value else "optional/missing", str(value or "—"))
    store = pipeline(workspace).store
    table.add_row("Workspace", "ready", str(store.root))
    console.print(table)
    if not versions.get("ffmpeg") or not versions.get("ffprobe"):
        raise typer.Exit(code=2)


@app.command("ingest-file")
def ingest_file(
    source: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    rights: RightsDeclaration = typer.Option(..., help="Mandatory rights declaration."),
    title: str | None = typer.Option(None),
    note: str | None = typer.Option(None, help="Internal rights/provenance note."),
    force_new: bool = typer.Option(False),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Copy a local authorized video into the reference library."""
    project = pipeline(workspace).ingest_file(
        source,
        rights=rights,
        title=title,
        operator_note=note,
        force_new=force_new,
    )
    console.print(f"[green]{project.reference_id}[/green] {project.workspace_path}")


@app.command("ingest-url")
def ingest_url(
    url: str = typer.Argument(...),
    rights: RightsDeclaration = typer.Option(..., help="Mandatory rights declaration."),
    title: str | None = typer.Option(None),
    note: str | None = typer.Option(None),
    cookies_from_browser: str | None = typer.Option(
        None,
        help="Optional operator-owned local browser profile; cookies are never logged or stored.",
    ),
    cookie_file: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional local Netscape cookie jar; its path and contents are never persisted.",
    ),
    force_new: bool = typer.Option(False),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Download an authorized publicly accessible reference with yt-dlp."""
    project = pipeline(workspace).ingest_url(
        url,
        rights=rights,
        title=title,
        operator_note=note,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
        force_new=force_new,
    )
    console.print(f"[green]{project.reference_id}[/green] {project.workspace_path}")


@app.command("process")
def process_reference(
    reference_id: str,
    interval: int | None = typer.Option(
        None,
        min=1,
        help="Fixed interval override. Omit for adaptive short-form sampling.",
    ),
    transcription_model: str = typer.Option("small"),
    transcription_device: str = typer.Option("auto"),
    local_vision: bool = typer.Option(False, help="Use configured local Ollama vision model."),
    every_frame: bool = typer.Option(
        False,
        help="Decode every frame for motion/change metrics without storing every image.",
    ),
    force: bool = typer.Option(False, help="Rebuild existing artifacts."),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Run media, frame, transcript, analysis, report, and fingerprint stages."""
    project = pipeline(workspace).process(
        reference_id,
        interval_seconds=interval,
        transcription_model=transcription_model,
        transcription_device=transcription_device,
        use_local_vision=local_vision,
        every_frame=every_frame,
        force=force,
    )
    console.print(f"[green]complete[/green] {project.reference_id}")
    console.print(Path(project.workspace_path) / "reports" / "index.html")


@app.command("facebook-login")
def facebook_login(
    browser_profile: Path = typer.Option(
        Path.home() / ".local" / "share" / "refintel" / "facebook-browser",
        help="Dedicated local Playwright profile; keep it outside the repository.",
    ),
) -> None:
    """Open a dedicated Chromium profile for one-time authorized Facebook login."""
    cookie_file = open_facebook_session(browser_profile)
    console.print(f"[green]session ready[/green] {browser_profile.expanduser().resolve()}")
    console.print(f"Local cookie jar: {cookie_file} (never commit or share this file)")


@app.command("facebook-page")
def facebook_page(
    page_url: str = typer.Argument(..., help="Stable Facebook page ID or handle URL."),
    brand: str = typer.Option(..., help="Portfolio brand slug."),
    rights: RightsDeclaration = typer.Option(..., help="Mandatory rights declaration."),
    limit: int = typer.Option(12, min=1, max=100),
    browser_profile: Path = typer.Option(
        Path.home() / ".local" / "share" / "refintel" / "facebook-browser"
    ),
    workspace: Path = typer.Option(Path("workspace")),
    headed: bool = typer.Option(False, help="Show Chromium while discovering page videos."),
    discover_only: bool = typer.Option(False, help="Save direct video URLs without downloading."),
    acquire_only: bool = typer.Option(
        False,
        help="Download references and manifests without running analysis.",
    ),
    local_vision: bool = typer.Option(
        True,
        help="Use local Ollama vision for frame and sequence storytelling analysis.",
    ),
    transcription_model: str = typer.Option("small"),
) -> None:
    """Discover and batch-analyze authorized videos from a Facebook brand page."""
    payload = run_facebook_page_batch(
        page_url,
        brand=brand,
        rights=rights,
        workspace_root=workspace,
        profile_dir=browser_profile,
        limit=limit,
        headless=not headed,
        discover_only=discover_only,
        acquire_only=acquire_only,
        use_local_vision=local_vision,
        transcription_model=transcription_model,
    )
    console.print_json(json.dumps(payload["summary"]))
    console.print(payload["run_dir"])


@app.command("report")
def open_report(
    reference_id: str,
    open_browser: bool = typer.Option(True),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Locate or open the generated offline report."""
    project = pipeline(workspace).store.load_project(reference_id)
    report_path = Path(project.workspace_path) / "reports" / "index.html"
    if not report_path.exists():
        raise typer.BadParameter("Process the reference before opening a report")
    console.print(report_path)
    if open_browser:
        webbrowser.open(report_path.as_uri())


@app.command("export-brief")
def export_brief(
    reference_id: str,
    brand: str = typer.Option(..., help="rawr_nation, animal_x, historiq, or ani_films"),
    topic: str | None = typer.Option(None),
    audience: str = typer.Option(
        "social video viewers interested in surprising, useful stories"
    ),
    duration: int = typer.Option(60, min=15, max=600),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Export an original, human-reviewable content brief."""
    target = pipeline(workspace).export_brief(
        reference_id,
        brand_id=brand,
        topic=topic,
        audience=audience,
        duration_seconds=duration,
    )
    console.print(f"[green]created[/green] {target}")


@app.command("library")
def list_library(
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """List locally stored references."""
    rows = pipeline(workspace).store.list_references()
    table = Table(title="Reference Library")
    for column in ("reference_id", "platform", "status", "duration_seconds", "title"):
        table.add_column(column)
    for row in rows:
        table.add_row(*(str(row.get(column) or "—") for column in (
            "reference_id", "platform", "status", "duration_seconds", "title"
        )))
    console.print(table)


@app.command("portfolio-sync-packet")
def portfolio_sync_packet(
    reference_id: str,
    workspace: Path = typer.Option(settings.workspace),
) -> None:
    """Create a sanitized metadata packet for the portfolio API handoff."""
    project = pipeline(workspace).store.load_project(reference_id)
    packet = build_portfolio_sync_packet(project, Path(project.workspace_path))
    console.print_json(
        json.dumps(
            {
                "reference_id": packet.local_reference_id,
                "status": packet.status,
                "progress_percent": packet.progress_percent,
                "artifact_count": len(packet.artifacts),
                "source_media_included": packet.source_media_included,
                "human_review_required": packet.human_review_required,
            }
        )
    )
    console.print(Path(project.workspace_path) / "exports" / "portfolio_sync_packet.json")


@app.command("compare")
def compare(
    fingerprint_paths: list[Path] = typer.Argument(..., min=2),
    output: Path | None = typer.Option(None),
) -> None:
    """Compare two or more local reference fingerprints."""
    result = compare_fingerprints(load_fingerprint(path) for path in fingerprint_paths)
    rendered = json.dumps(result, indent=2)
    if output:
        output.write_text(rendered, encoding="utf-8")
        console.print(output)
    else:
        console.print_json(rendered)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765, min=1, max=65535),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Run the local browser interface."""
    import os

    os.environ["REFINTEL_WORKSPACE"] = str(workspace.expanduser().resolve())
    try:
        import uvicorn
    except ImportError as exc:
        console.print("Install the base package dependencies first.")
        raise typer.Exit(code=2) from exc
    uvicorn.run("refintel.api:app", host=host, port=port, reload=False)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
