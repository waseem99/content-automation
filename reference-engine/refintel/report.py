from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, StrictUndefined, select_autoescape

from .models import ReferenceProject


REPORT_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ project.source.title }} — Reference Analysis</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#f4f5f7;background:#0b0d12}
*{box-sizing:border-box}body{margin:0}.shell{max-width:1480px;margin:auto;padding:24px}
.header{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:22px}
.kicker{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#ffcf33}.title{font-size:34px;margin:6px 0 8px}
.muted{color:#a7adbb}.pill{display:inline-block;border:1px solid #343947;border-radius:999px;padding:6px 10px;margin:3px;font-size:12px}
.grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(360px,.65fr);gap:18px}.card{background:#151821;border:1px solid #282d39;border-radius:16px;padding:16px;overflow:hidden}
video{width:100%;max-height:70vh;background:#000;border-radius:12px}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.tab{border:0;border-radius:9px;padding:9px 12px;background:#242936;color:#fff;cursor:pointer}.tab.active{background:#ffcf33;color:#151515}
.panel{display:none}.panel.active{display:block}.timeline{position:relative;height:52px;background:#202531;border-radius:10px;margin:12px 0}.marker{position:absolute;top:0;bottom:0;width:2px;background:#ffcf33}.marker span{position:absolute;top:6px;left:5px;font-size:10px;white-space:nowrap;color:#ffcf33}
.transcript{max-height:520px;overflow:auto}.segment{padding:10px;border-bottom:1px solid #292e3a;cursor:pointer}.segment:hover{background:#222733}.time{color:#ffcf33;font-variant-numeric:tabular-nums;font-size:12px}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}.frame{background:#0e1117;border:1px solid #2b303c;border-radius:10px;overflow:hidden;cursor:pointer}.frame img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}.frame div{padding:8px;font-size:12px}.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.score{padding:14px;background:#10131a;border-radius:11px}.score strong{font-size:30px;color:#ffcf33;display:block}
.finding{padding:12px 0;border-bottom:1px solid #2a2f3a}.story{display:grid;gap:8px}.story-item{display:grid;grid-template-columns:130px 1fr;gap:10px;padding:10px;background:#10131a;border-radius:8px}
pre{white-space:pre-wrap;word-break:break-word;background:#0c0f15;padding:12px;border-radius:9px}.warning{border-left:4px solid #ffcf33;padding:12px;background:#211e12;border-radius:8px}
@media(max-width:960px){.grid{grid-template-columns:1fr}.header{flex-direction:column}.shell{padding:14px}}
</style>
</head>
<body><main class="shell">
<header class="header"><div><div class="kicker">P66 Local Reference Intelligence</div><h1 class="title">{{ project.source.title }}</h1><div class="muted">{{ project.source.platform.value }} · {{ duration }}s · {{ project.access.declaration.value }} · {{ project.status.value }}</div></div><div><span class="pill">{{ project.reference_id }}</span><span class="pill">Human review required</span></div></header>
<div class="warning">This report supports internal research and original content development. Do not reuse source footage, wording, branding, music, voices, or proprietary artwork without permission.</div>
<section class="grid" style="margin-top:18px">
<div class="card"><video id="player" controls preload="metadata" src="{{ video_src }}"></video>
<div class="timeline" id="timeline">{% for item in story_arc %}<button class="marker" style="left:{{ item.start_percent }}%" data-time="{{ item.start_seconds }}" title="{{ item.stage }}"><span>{{ item.stage }}</span></button>{% endfor %}</div>
<div class="tabs"><button class="tab active" data-panel="transcript">Transcript</button><button class="tab" data-panel="frames">Frames</button><button class="tab" data-panel="story">Story</button><button class="tab" data-panel="findings">Findings</button><button class="tab" data-panel="raw">Measured data</button></div>
<div class="panel active" id="panel-transcript"><div class="transcript">{% if project.transcript %}{% for segment in project.transcript %}<div class="segment seek" data-time="{{ segment.start_seconds }}"><span class="time">{{ '%.2f'|format(segment.start_seconds) }}s</span> {{ segment.text }}</div>{% endfor %}{% else %}<p class="muted">No speech transcript is available. Install the speech extra and reprocess to add local transcription.</p>{% endif %}</div></div>
<div class="panel" id="panel-frames"><div class="gallery">{% for frame in project.frames %}<div class="frame seek" data-time="{{ frame.timestamp_seconds }}"><img loading="lazy" src="{{ frame.report_src }}" alt="Frame at {{ frame.timestamp_seconds }} seconds"><div><span class="time">{{ '%.2f'|format(frame.timestamp_seconds) }}s</span> · {{ frame.kind }} · score {{ '%.2f'|format(frame.quality_score) }}</div></div>{% endfor %}</div></div>
<div class="panel" id="panel-story"><div class="story">{% for item in story_arc %}<div class="story-item seek" data-time="{{ item.start_seconds }}"><strong>{{ item.stage }}</strong><span>{{ '%.2f'|format(item.start_seconds) }}–{{ '%.2f'|format(item.end_seconds) }}s<br><span class="muted">{{ item.basis }}</span></span></div>{% endfor %}</div></div>
<div class="panel" id="panel-findings">{% for finding in findings %}<div class="finding seek" data-time="{{ finding.start_seconds or 0 }}"><div class="kicker">{{ finding.category }} · {{ finding.label }}</div><p>{{ finding.summary }}</p><div class="muted">confidence {{ '%.0f'|format(finding.confidence*100) }}% · {{ 'measured' if finding.measured else 'automated observation' }}</div></div>{% endfor %}</div>
<div class="panel" id="panel-raw"><pre>{{ raw_json }}</pre></div>
</div>
<aside class="card"><h2>Objective profile</h2><div class="scores">{% for name, score in scores.items() %}<div class="score"><strong>{{ score.score }}</strong><span>{{ name.replace('_',' ') }}</span></div>{% endfor %}</div><h2>Hook</h2><pre>{{ hook_json }}</pre><h2>Pacing</h2><pre>{{ pacing_json }}</pre><h2>Source and tools</h2><pre>{{ source_json }}</pre></aside>
</section>
</main>
<script>
const player=document.getElementById('player');
function seek(time){player.currentTime=Number(time)||0;player.play().catch(()=>{});window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('.seek,.marker').forEach(el=>el.addEventListener('click',()=>seek(el.dataset.time)));
document.querySelectorAll('.tab').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));button.classList.add('active');document.getElementById('panel-'+button.dataset.panel).classList.add('active');}));
</script></body></html>"""


def generate_report(project: ReferenceProject, workspace: Path) -> Path:
    if not project.media or not project.analysis:
        raise ValueError("Media and analysis are required before report generation")
    report_dir = workspace / "reports"
    assets_dir = report_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    source_video = workspace / "media" / "analysis.mp4"
    report_video = assets_dir / "analysis.mp4"
    if source_video.exists():
        shutil.copy2(source_video, report_video)
    frame_payloads: list[dict[str, object]] = []
    for frame in project.frames:
        source = workspace / frame.relative_path
        target = assets_dir / source.name
        if source.exists():
            shutil.copy2(source, target)
        payload = frame.model_dump(mode="json")
        payload["report_src"] = f"assets/{target.name}"
        frame_payloads.append(payload)
    duration = max(project.media.duration_seconds, 0.001)
    story_arc = []
    for item in project.analysis.story_arc:
        payload = dict(item)
        payload["start_percent"] = min(100, max(0, float(item["start_seconds"]) / duration * 100))
        story_arc.append(payload)
    environment = Environment(
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
    )
    template = environment.from_string(REPORT_TEMPLATE)
    project_payload = project.model_dump(mode="json")
    project_payload["frames"] = frame_payloads
    html = template.render(
        project=project_payload,
        duration=round(duration, 2),
        video_src="assets/analysis.mp4",
        story_arc=story_arc,
        findings=project.analysis.findings,
        scores=project.analysis.objective_scores,
        hook_json=json.dumps(project.analysis.hook, indent=2, ensure_ascii=False),
        pacing_json=json.dumps(project.analysis.pacing, indent=2, ensure_ascii=False),
        source_json=json.dumps(
            {
                "source": project.source.model_dump(mode="json"),
                "rights": project.access.model_dump(mode="json"),
                "tools": project.tool_versions,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        raw_json=json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
    )
    target = report_dir / "index.html"
    target.write_text(html, encoding="utf-8")
    return target
