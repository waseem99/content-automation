from __future__ import annotations

import json
import shutil
import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .fingerprint import compare_fingerprints, load_fingerprint
from .models import RightsDeclaration
from .pipeline import ReferencePipeline, tool_versions


app = typer.Typer(
    no_args_is_help=True,
    help="Local-first video reference ingestion, analysis, reporting, and brief export.",
)
console = Console()


def pipeline(workspace: Path) -> ReferencePipeline:
    return ReferencePipeline(workspace.expanduser().resolve())


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
    force_new: bool = typer.Option(False),
    workspace: Path = typer.Option(Path("workspace")),
) -> None:
    """Download an authorized publicly accessible reference with yt-dlp."""
    project = pipeline(workspace).ingest_url(
        url,
        rights=rights,
        title=title,
        operator_note=note,
        force_new=force_new,
    )
    console.print(f"[green]{project.reference_id}[/green] {project.workspace_path}")


@app.command("process")
def process_reference(
    reference_id: str,
    interval: int = typer.Option(60, min=1, help="Fixed frame interval in seconds."),
    transcription_model: str = typer.Option("small"),
    transcription_device: str = typer.Option("auto"),
    local_vision: bool = typer.Option(False, help="Use configured local Ollama vision model."),
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
        force=force,
    )
    console.print(f"[green]complete[/green] {project.reference_id}")
    console.print(Path(project.workspace_path) / "reports" / "index.html")


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
