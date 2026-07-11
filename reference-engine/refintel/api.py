from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from .models import RightsDeclaration
from .pipeline import ReferencePipeline, tool_versions


WORKSPACE = Path(os.getenv("REFINTEL_WORKSPACE", "workspace")).expanduser().resolve()
PIPELINE = ReferencePipeline(WORKSPACE)
app = FastAPI(title="Local Reference Intelligence Engine", version="0.1.0")


HOME_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Reference Intelligence</title><style>body{font-family:system-ui;background:#0b0d12;color:#f5f6f8;margin:0}.shell{max-width:1100px;margin:auto;padding:28px}.card{background:#171a22;border:1px solid #2a2f3a;border-radius:14px;padding:18px;margin:14px 0}input,select,button{width:100%;padding:10px;margin:6px 0;border-radius:8px;border:1px solid #3a4050;background:#0e1117;color:#fff}button{background:#ffcf33;color:#111;font-weight:700;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #2a2f3a;text-align:left}a{color:#ffcf33}.muted{color:#a8adba}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style></head><body><main class='shell'><h1>Local Reference Intelligence</h1><p class='muted'>Authorized internal research only. Source footage is not reused automatically.</p><div class='grid'><section class='card'><h2>Upload local video</h2><form action='/ingest/file' method='post' enctype='multipart/form-data'><input type='file' name='file' accept='video/*' required><input name='title' placeholder='Title'><select name='rights' required><option value='owned'>Owned</option><option value='permitted'>Permitted</option><option value='public-internal-research'>Public internal research</option><option value='rights-holder-upload'>Rights-holder upload</option></select><button>Ingest file</button></form></section><section class='card'><h2>Ingest public URL</h2><form action='/ingest/url' method='post'><input name='url' placeholder='Facebook, Instagram, YouTube, TikTok, X, or Drive URL' required><input name='title' placeholder='Title'><select name='rights' required><option value='owned'>Owned</option><option value='permitted'>Permitted</option><option value='public-internal-research'>Public internal research</option><option value='rights-holder-upload'>Rights-holder upload</option></select><button>Ingest URL</button></form></section></div><section class='card'><h2>Reference library</h2><table><thead><tr><th>ID</th><th>Platform</th><th>Status</th><th>Title</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></section></main></body></html>"""


def _rows() -> str:
    rows: list[str] = []
    for item in PIPELINE.store.list_references():
        reference_id = html.escape(str(item["reference_id"]), quote=True)
        platform = html.escape(str(item.get("platform") or ""), quote=True)
        status = html.escape(str(item.get("status") or ""), quote=True)
        title = html.escape(str(item.get("title") or ""), quote=True)
        actions = [
            f"<form style='display:inline' action='/process/{reference_id}' method='post'>"
            "<button style='width:auto;padding:6px 9px'>Process</button></form>"
        ]
        report = WORKSPACE / "references" / reference_id / "reports" / "index.html"
        if report.exists():
            actions.append(f"<a href='/report/{reference_id}/index.html'>Report</a>")
        rows.append(
            "<tr>"
            f"<td>{reference_id}</td><td>{platform}</td><td>{status}</td>"
            f"<td>{title}</td><td>{' · '.join(actions)}</td></tr>"
        )
    return "".join(rows) or "<tr><td colspan='5' class='muted'>No references yet.</td></tr>"


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HOME_TEMPLATE.format(rows=_rows())


@app.get("/health")
def health() -> dict[str, object]:
    versions = tool_versions()
    return {
        "status": "ok" if versions.get("ffmpeg") and versions.get("ffprobe") else "degraded",
        "workspace": str(WORKSPACE),
        "tools": versions,
        "reference_count": len(PIPELINE.store.list_references()),
    }


@app.get("/api/references")
def references() -> list[dict[str, object]]:
    return PIPELINE.store.list_references()


@app.post("/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    rights: RightsDeclaration = Form(...),
    title: str | None = Form(None),
) -> RedirectResponse:
    suffix = Path(file.filename or "reference.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
        while chunk := await file.read(1024 * 1024):
            temporary.write(chunk)
        temporary_path = Path(temporary.name)
    try:
        project = PIPELINE.ingest_file(temporary_path, rights=rights, title=title)
    finally:
        temporary_path.unlink(missing_ok=True)
    return RedirectResponse(f"/?created={project.reference_id}", status_code=303)


@app.post("/ingest/url")
def ingest_url(
    url: str = Form(...),
    rights: RightsDeclaration = Form(...),
    title: str | None = Form(None),
) -> RedirectResponse:
    try:
        project = PIPELINE.ingest_url(url, rights=rights, title=title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/?created={project.reference_id}", status_code=303)


@app.post("/process/{reference_id}")
def process_reference(reference_id: str, background_tasks: BackgroundTasks) -> RedirectResponse:
    try:
        PIPELINE.store.load_project(reference_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(PIPELINE.process, reference_id)
    return RedirectResponse(f"/?processing={reference_id}", status_code=303)


@app.get("/report/{reference_id}")
def report_redirect(reference_id: str) -> RedirectResponse:
    return RedirectResponse(f"/report/{reference_id}/index.html", status_code=307)


@app.get("/report/{reference_id}/index.html")
def report(reference_id: str) -> FileResponse:
    try:
        project = PIPELINE.store.load_project(reference_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    target = Path(project.workspace_path) / "reports" / "index.html"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Process the reference first")
    return FileResponse(target)


@app.get("/report/{reference_id}/assets/{filename}")
def report_asset(reference_id: str, filename: str) -> FileResponse:
    project = PIPELINE.store.load_project(reference_id)
    assets = (Path(project.workspace_path) / "reports" / "assets").resolve()
    target = (assets / Path(filename).name).resolve()
    if assets not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(target)


@app.get("/exports/{reference_id}/{filename}")
def export_file(reference_id: str, filename: str) -> FileResponse:
    project = PIPELINE.store.load_project(reference_id)
    exports = (Path(project.workspace_path) / "exports").resolve()
    target = (exports / Path(filename).name).resolve()
    if exports not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(target, filename=target.name)
