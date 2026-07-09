"""P41 rights and monetization safety intelligence engine.

This module analyzes a P40-style video package before production. It identifies
copyright, trademark, likeness, commercial music, third-party footage, copied
premise/style, unclear source, and monetization safety issues. It produces safer
rewrite suggestions, an asset/source manifest, scores, and a publish gate.

It does not call external services, scrape rights databases, provide legal advice,
claim legal clearance, download assets, render video, upload, or publish.
"""

from __future__ import annotations

import json
from typing import Any

P41_REPORT_VERSION = "p41.rights_safety_report.v1"

RISK_RULES = {
    "copyrighted_franchise_or_character": {
        "severity": "high",
        "terms": ["marvel", "disney", "pixar", "batman", "superman", "spider-man", "spiderman", "harry potter", "star wars", "pokemon", "naruto", "dragon ball", "mickey mouse", "barbie"],
        "why": "Protected franchises or characters can create copyright/trademark risk if reused without permission.",
        "safer": "Replace with an original character, generic archetype, or abstract visual metaphor.",
    },
    "celebrity_likeness_or_voice": {
        "severity": "high",
        "terms": ["mrbeast", "elon musk voice", "taylor swift voice", "celebrity voice", "deepfake", "ai clone", "voice clone"],
        "why": "Real-person likeness, voice imitation, or deepfake references can trigger publicity and platform risk.",
        "safer": "Use an original narrator persona and avoid imitating real people.",
    },
    "commercial_music_or_audio": {
        "severity": "high",
        "terms": ["famous song", "copyrighted music", "tiktok audio", "chart song", "popular song", "use this song"],
        "why": "Commercial audio often requires licensing and can block monetization.",
        "safer": "Use owned, licensed, or royalty-free music with documented proof.",
    },
    "third_party_clip_or_footage": {
        "severity": "high",
        "terms": ["movie clip", "netflix clip", "sports clip", "news clip", "podcast clip", "youtube clip", "screen record someone else's video"],
        "why": "Third-party footage can create reuse, copyright, and monetization problems.",
        "safer": "Use owned footage, licensed stock, original animation, or recreated abstract visuals.",
    },
    "copied_premise_or_style": {
        "severity": "medium",
        "terms": ["in the style of", "exactly like", "copy the", "shot for shot", "same plot", "remake scene", "make it like"],
        "why": "Copying a protected premise, sequence, or signature expression reduces originality and increases rights risk.",
        "safer": "Preserve the emotion or structure but create original framing, examples, and visuals.",
    },
    "brand_or_trademark_dependency": {
        "severity": "medium",
        "terms": ["nike", "apple", "tesla", "coca-cola", "netflix", "youtube", "instagram", "tiktok", "openai"],
        "why": "Brand-heavy concepts can become dependent on trademarks or imply affiliation.",
        "safer": "Use category language unless the reference is factual, necessary, and reviewed.",
    },
    "unclear_ai_or_stock_source": {
        "severity": "medium",
        "terms": ["ai generated", "stock", "found online", "random image", "internet image", "free download"],
        "why": "Unclear asset provenance can weaken monetization and clearance confidence.",
        "safer": "Record source, license, generation tool, prompt notes, and usage rights.",
    },
}

ASSET_CATEGORIES = {
    "voiceover": {
        "allowed_sources": ["original human narration", "licensed synthetic voice", "owned voice recording"],
        "prohibited_sources": ["celebrity imitation", "unauthorized voice clone", "deepfake voice"],
        "evidence_required": ["voice source", "license or consent note"],
    },
    "music": {
        "allowed_sources": ["owned composition", "royalty-free library", "licensed music"],
        "prohibited_sources": ["commercial track without license", "ripped platform audio", "famous song without clearance"],
        "evidence_required": ["license URL or library record", "track name", "allowed platform usage"],
    },
    "footage": {
        "allowed_sources": ["owned footage", "licensed stock", "original animation", "screen recordings of owned product"],
        "prohibited_sources": ["movie clips", "TV clips", "sports clips", "unlicensed YouTube/TikTok clips"],
        "evidence_required": ["source", "license", "usage permission"],
    },
    "graphics": {
        "allowed_sources": ["owned design", "licensed templates", "original generated visuals reviewed for rights"],
        "prohibited_sources": ["logos used as decoration", "copied characters", "unlicensed templates"],
        "evidence_required": ["creator/source", "license", "editable/source file location"],
    },
    "fonts": {
        "allowed_sources": ["commercially licensed font", "open-source font", "system font"],
        "prohibited_sources": ["unknown downloaded font", "unlicensed premium font"],
        "evidence_required": ["font name", "license"],
    },
}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def normalize_rights_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a P40 package or direct content payload into analyzable fields."""

    brief = payload.get("brief", {}) if isinstance(payload.get("brief"), dict) else {}
    production = payload.get("production_brief", {}) if isinstance(payload.get("production_brief"), dict) else {}
    fields = {
        "platform": brief.get("platform") or payload.get("platform") or "unknown",
        "titles": payload.get("title_options", payload.get("titles", [])),
        "hook": payload.get("hook", ""),
        "script": payload.get("script", ""),
        "scene_plan": payload.get("scene_plan", []),
        "asset_requirements": payload.get("asset_requirements", []),
        "source_notes": brief.get("source_notes", payload.get("source_notes", [])),
        "production_notes": production,
    }
    analysis_text = " ".join(_stringify(item) for item in fields.values()).lower()
    errors = [] if analysis_text.strip() else ["missing_analyzable_content"]
    return {"is_valid": not errors, "validation_errors": errors, "fields": fields, "analysis_text": analysis_text}


def detect_rights_risks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_rights_payload(payload)
    if not normalized["is_valid"]:
        return []
    text = normalized["analysis_text"]
    findings = []
    for category, rule in RISK_RULES.items():
        for term in rule["terms"]:
            if term in text:
                findings.append({
                    "category": category,
                    "severity": rule["severity"],
                    "evidence": term,
                    "impacted_field": _guess_impacted_field(term, normalized["fields"]),
                    "why_it_matters": rule["why"],
                    "safer_direction": rule["safer"],
                })
    return findings


def _guess_impacted_field(term: str, fields: dict[str, Any]) -> str:
    lowered = term.lower()
    for field, value in fields.items():
        if lowered in _stringify(value).lower():
            return field
    return "combined_payload"


def generate_safer_rewrites(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    rewrites = []
    for finding in findings:
        rewrites.append({
            "risk_category": finding["category"],
            "evidence": finding["evidence"],
            "rewrite_strategy": finding["safer_direction"],
            "example_rewrite": _rewrite_for_category(finding["category"], finding["evidence"]),
        })
    return rewrites


def _rewrite_for_category(category: str, evidence: str) -> str:
    if category == "copyrighted_franchise_or_character":
        return f"Replace '{evidence}' with 'an original heroic archetype designed for this channel'."
    if category == "celebrity_likeness_or_voice":
        return f"Replace '{evidence}' with 'a confident original narrator with no real-person imitation'."
    if category == "commercial_music_or_audio":
        return f"Replace '{evidence}' with 'licensed high-energy background music with documented platform rights'."
    if category == "third_party_clip_or_footage":
        return f"Replace '{evidence}' with 'owned b-roll, licensed stock, or original motion graphics'."
    if category == "copied_premise_or_style":
        return f"Replace '{evidence}' with 'a fresh structure using original examples and pacing'."
    if category == "brand_or_trademark_dependency":
        return f"Replace '{evidence}' with a generic category unless factual reference is required."
    return f"Document the source and license for '{evidence}' before production."


def build_asset_manifest(payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_rights_payload(payload)
    text = normalized.get("analysis_text", "")
    manifest = []
    for category, rules in ASSET_CATEGORIES.items():
        required = category in text or category in ["voiceover", "music", "footage", "graphics"]
        manifest.append({
            "asset_category": category,
            "required": required,
            "allowed_sources": rules["allowed_sources"],
            "prohibited_sources": rules["prohibited_sources"],
            "evidence_required": rules["evidence_required"],
            "clearance_status": "needs_evidence" if required else "not_required_yet",
        })
    return manifest


def score_rights_safety(findings: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> dict[str, Any]:
    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    unclear_assets = sum(1 for item in manifest if item["required"] and item["clearance_status"] == "needs_evidence")
    rights_risk = max(0, 100 - high * 30 - medium * 15)
    asset_clarity = max(0, 100 - unclear_assets * 8)
    originality = max(0, 95 - medium * 10 - high * 20)
    platform_safety = max(0, 92 - high * 25 - medium * 10)
    sponsor_friendliness = max(0, 90 - high * 20 - medium * 8)
    review_readiness = max(0, int((rights_risk + asset_clarity + originality + platform_safety + sponsor_friendliness) / 5))
    return {
        "overall_safety_score": review_readiness,
        "subscores": {
            "rights_risk": rights_risk,
            "asset_clarity": asset_clarity,
            "originality": originality,
            "platform_safety": platform_safety,
            "sponsor_friendliness": sponsor_friendliness,
            "review_readiness": review_readiness,
        },
        "monetization_guaranteed": False,
        "legal_clearance_claimed": False,
    }


def generate_publish_gate(findings: list[dict[str, Any]], manifest: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    high_findings = [item for item in findings if item["severity"] == "high"]
    medium_findings = [item for item in findings if item["severity"] == "medium"]
    missing_evidence = [item for item in manifest if item["required"] and item["clearance_status"] == "needs_evidence"]
    if high_findings:
        gate = "block"
    elif medium_findings or missing_evidence or score["overall_safety_score"] < 85:
        gate = "revise"
    else:
        gate = "pass"
    return {
        "gate": gate,
        "blocker_reasons": [f"{item['category']}: {item['evidence']}" for item in high_findings],
        "required_fixes": _required_fixes(findings, missing_evidence),
        "safe_production_notes": [
            "Use owned, licensed, or clearly documented assets only.",
            "Avoid celebrity imitation, copyrighted characters, unlicensed music, and third-party clips.",
            "Keep evidence of licenses and source notes before publishing.",
        ],
        "human_review_required": True,
    }


def _required_fixes(findings: list[dict[str, Any]], missing_evidence: list[dict[str, Any]]) -> list[str]:
    fixes = [f"Resolve {item['severity']} risk in {item['impacted_field']}: {item['evidence']}" for item in findings]
    fixes.extend(f"Add evidence for {item['asset_category']} assets." for item in missing_evidence)
    return fixes or ["Final human review before publish."]


def analyze_rights_safety(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_rights_payload(payload)
    if not normalized["is_valid"]:
        return {"schema_version": P41_REPORT_VERSION, "is_valid": False, "validation_errors": normalized["validation_errors"]}
    findings = detect_rights_risks(payload)
    rewrites = generate_safer_rewrites(findings)
    manifest = build_asset_manifest(payload)
    score = score_rights_safety(findings, manifest)
    gate = generate_publish_gate(findings, manifest, score)
    return {
        "schema_version": P41_REPORT_VERSION,
        "is_valid": True,
        "platform": normalized["fields"]["platform"],
        "rights_risk_inventory": findings,
        "safer_rewrite_suggestions": rewrites,
        "asset_source_manifest": manifest,
        "originality_and_transformation_notes": _originality_notes(findings),
        "platform_monetization_safety_flags": _platform_flags(findings, gate),
        "scores": score,
        "publish_gate": gate,
    }


def _originality_notes(findings: list[dict[str, Any]]) -> list[str]:
    if not findings:
        return ["Concept appears based on original explanation and production planning. Maintain owned examples and visuals."]
    return ["Increase transformation by using original framing, examples, visuals, narration, and owned/cleared assets."]


def _platform_flags(findings: list[dict[str, Any]], gate: dict[str, Any]) -> list[str]:
    flags = []
    categories = {item["category"] for item in findings}
    if "third_party_clip_or_footage" in categories:
        flags.append("Possible reused-content monetization issue.")
    if "commercial_music_or_audio" in categories:
        flags.append("Possible music-claim or monetization-block issue.")
    if "celebrity_likeness_or_voice" in categories:
        flags.append("Possible synthetic media/likeness policy issue.")
    if gate["gate"] != "pass":
        flags.append("Human review required before production or publishing.")
    return flags or ["No major platform monetization flags detected by static rules."]
