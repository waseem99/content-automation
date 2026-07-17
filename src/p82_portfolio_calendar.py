"""Build four 30-day, four-per-day brand calendars from editorial seed catalogs."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

from src.p80_brand_month_studio import _fingerprint
from src.p81_high_volume_calendar import ANGLE_LABELS, SLOT_POLICY, _angle as animal_angle


CURRENT_BRANDS = ("rawr-nation", "animal-x", "historiq", "ani-films")

HISTORIQ_SEEDS = [
    ("The map that put north on top", "Trace how convention, navigation, printing, and power—not nature—helped north-up maps become dominant.", "Hidden history"),
    ("Why ancient statues lost their colour", "Reconstruct the pigments once visible on Greek and Roman sculpture and why the white-marble image survived.", "Myth versus record"),
    ("The year summer almost disappeared", "Explain how the 1815 Tambora eruption disrupted weather, harvests, migration, and culture in 1816.", "Historical turning points"),
    ("How coffeehouses became information networks", "Show how early modern coffeehouses connected merchants, writers, politics, news, and financial exchange.", "Ideas that changed society"),
    ("The error that preserved a language", "Explore how copying, translation, inscriptions, and chance survival let scholars reconstruct lost scripts.", "Hidden history"),
    ("Why purple became the colour of power", "Connect scarce dyes, labour-intensive production, trade control, and sumptuary rules to elite status.", "Ideas that changed society"),
    ("The clock that reorganized daily life", "Trace the shift from seasonal and religious timekeeping toward standardized public and industrial time.", "Historical turning points"),
    ("Did people really think Earth was flat?", "Separate medieval cosmological evidence from the later myth that educated Europeans universally believed in a flat Earth.", "Myth versus record"),
    ("The tiny document that changed citizenship", "Use passports and identity papers to show how modern states increasingly categorized and controlled movement.", "Ideas that changed society"),
    ("How salt financed empires", "Follow salt production, taxation, monopolies, smuggling, and protest across several historical states.", "Hidden history"),
    ("The volcanic glass network before money", "Map obsidian exchange to reveal long-distance trust and specialization before modern currency systems.", "Hidden history"),
    ("Why cities built walls after cannons", "Show how gunpowder artillery transformed tall medieval walls into lower, angled star-fort defenses.", "Historical turning points"),
    ("The trial that put a book on the defensive", "Examine how censorship, evidence, patronage, and institutions shaped a famous clash over published knowledge.", "Ideas that changed society"),
    ("How paper defeated parchment", "Compare material cost, production speed, bureaucracy, literacy, and printing to explain paper's expansion.", "Historical turning points"),
    ("The plague rule that created quarantine", "Trace maritime isolation rules and the gradual institutional response to epidemic uncertainty.", "Ideas that changed society"),
    ("What ancient graffiti actually says", "Use surviving wall writing to reveal jokes, advertising, affection, insults, and ordinary urban life.", "Hidden history"),
    ("Why the zero was revolutionary", "Explain how positional notation and a symbol for zero transformed calculation, trade, astronomy, and later mathematics.", "Ideas that changed society"),
    ("The treaty line drawn across a world", "Visualize how distant powers divided claimed territory on maps while ignoring people already living there.", "Historical turning points"),
    ("Did Vikings really wear horned helmets?", "Trace the small archaeological record and the much later artistic tradition behind the horned-Viking image.", "Myth versus record"),
    ("How a postal relay outran an army", "Show how horses, stations, roads, and administrative discipline moved information across large empires.", "Hidden history"),
    ("The crop that changed European population", "Explain how potatoes affected nutrition and population while keeping regional timing, dependency, and famine risk visible.", "Historical turning points"),
    ("Why public libraries were politically radical", "Connect access to books with education, civic participation, philanthropy, and debates over who deserved knowledge.", "Ideas that changed society"),
    ("The photograph that changed what war looked like", "Separate documentation, staging, technology, circulation, and public interpretation in early war photography.", "Myth versus record"),
    ("How fingerprints became state evidence", "Trace the move from local observation to classification systems used for identity, policing, and administration.", "Hidden history"),
]

ANI_FILMS_SEEDS = [
    ("How a zipper locks without a knot", "Animate the slider forcing alternating teeth into one interlocking chain and separating them in reverse.", "How systems work"),
    ("Why bridges expand in hot weather", "Show thermal expansion and the joints, bearings, and gaps that let structures move without uncontrolled cracking.", "Everyday science"),
    ("Inside the algorithm that sorts a feed", "Turn signals, candidate selection, ranking, feedback, and uncertainty into a clear non-proprietary visual model.", "Big ideas made simple"),
    ("How noise cancelling headphones erase a hum", "Visualize microphones, phase inversion, timing, and why irregular nearby speech is harder to cancel.", "Visual explainers"),
    ("Why airplane windows have a tiny hole", "Explain pressure equalization across window panes and why the outer pane carries the main cabin pressure load.", "Everyday science"),
    ("How a refrigerator moves heat", "Follow refrigerant through compression, condensation, expansion, and evaporation rather than describing cold as a substance.", "How systems work"),
    ("What happens when you scan a QR code", "Animate finder patterns, perspective correction, modules, error correction, decoding, and the resulting data action.", "Visual explainers"),
    ("Why traffic waves appear without a crash", "Model reaction delay and over-braking as a disturbance that travels backward through dense traffic.", "Big ideas made simple"),
    ("How a microphone turns air into data", "Follow pressure waves through a transducer, analog voltage, sampling, quantization, and stored numbers.", "How systems work"),
    ("Why soap defeats grease", "Show amphiphilic molecules surrounding oily material so water can carry it away.", "Everyday science"),
    ("Inside a password hash", "Distinguish encryption from one-way hashing, salts, verification, and why weak passwords remain vulnerable.", "Big ideas made simple"),
    ("How elevators know where to stop", "Visualize requests, scheduling, position sensing, door safety, counterweights, braking, and controller decisions.", "How systems work"),
    ("Why ice is slippery", "Compare pressure, frictional heating, and the mobile surface layer without reducing every condition to one cause.", "Everyday science"),
    ("How GPS finds you without seeing you", "Use signal travel time from multiple satellites, clock correction, and trilateration to locate a receiver.", "Visual explainers"),
    ("What a bank transfer actually moves", "Separate account-ledger updates, messages, settlement, reconciliation, and the absence of physically moving money.", "Big ideas made simple"),
    ("How a camera freezes motion", "Connect exposure time, aperture, light, sensor readout, blur, and rolling-shutter trade-offs.", "Visual explainers"),
    ("Why popcorn explodes", "Follow water trapped inside the kernel until steam pressure ruptures the shell and starch rapidly expands.", "Everyday science"),
    ("How a search engine finds one page", "Animate crawling, indexing, query interpretation, retrieval, ranking, and result presentation at a conceptual level.", "How systems work"),
    ("Why a curve makes a stronger arch", "Show compression forces moving through voussoirs toward supports and what happens when thrust is not contained.", "Everyday science"),
    ("Inside two-factor authentication", "Separate the password, second factor, challenge, verification, recovery, and common phishing limitations.", "Big ideas made simple"),
    ("How a thermostat prevents constant switching", "Explain setpoints, sensors, feedback, hysteresis, and delayed system response.", "How systems work"),
    ("Why metal feels colder than wood", "Show faster heat transfer from skin into metal even when both objects begin at the same room temperature.", "Everyday science"),
    ("How compression makes a video smaller", "Visualize spatial similarity, motion prediction, residual data, keyframes, and the quality-size trade-off.", "Visual explainers"),
    ("Why queues sometimes move faster when they merge", "Model service capacity, arrival patterns, fairness, and the difference between one shared line and multiple lines.", "Big ideas made simple"),
]


def _generic_angle(base: dict[str, Any], angle: str, brand_slug: str) -> dict[str, str]:
    title, concept = base["title"], base["concept"]
    subject = title.removeprefix("The ").removeprefix("Why ").removeprefix("How ").removeprefix("Inside ")
    is_history = brand_slug == "historiq"
    treatments = {
        "reveal": (title, f"The familiar version of {subject.lower()} leaves out the part that changes the story.", concept, "End on the strongest documented visual that resolves the opening question."),
        "mechanism": (f"How it worked: {subject}", f"To understand {subject.lower()}, follow the system one step at a time.", f"Break the process into causes, constraints, and consequences: {concept}", "Replay the full chain only after every moving part is clear."),
        "myth_check": (f"Myth check: {subject}", f"A clean story about {subject.lower()} spread further than the complicated evidence.", f"Place the popular claim beside the narrower record: {concept}", "Keep what the evidence supports and visibly discard the exaggeration."),
        "sensory_pov": (f"See it from inside: {subject}", f"Change the point of view and {subject.lower()} becomes a different system.", f"Use a grounded participant perspective while labelling reconstruction and uncertainty: {concept}", "Return to the wide view with one new detail the audience can now recognize."),
        "survival_stakes": (f"The decision that shaped {subject}", f"One constraint turned {subject.lower()} from an idea into a real-world consequence.", f"Stage the trade-off, failure mode, and human stakes without inventing certainty: {concept}", "The payoff is not inevitability; it is the consequence of choices under pressure."),
    }
    name, hook, setup, payoff = treatments[angle]
    truth = "Separate primary evidence, later interpretation, and reconstruction." if is_history else "Separate the simplified visual model from implementation details and edge cases."
    return {"title": name, "hook": hook, "setup": setup, "truth": truth, "payoff": payoff}


def _scenes(treatment: dict[str, str], concept: str, feature: bool, brand_slug: str) -> list[dict[str, Any]]:
    durations = [4, 7, 9, 8, 7] if feature else [3, 6, 8, 7, 6]
    lines = [treatment["hook"], treatment["setup"], concept, treatment["truth"], treatment["payoff"]]
    purposes = ["hook", "evidence", "mechanism", "clarifier", "payoff"]
    visuals = [
        "Immediate motion-led visual question; readable without sound in frame one.",
        "One continuous setup that establishes subject, place, scale, and constraint.",
        "Controlled diagram, cutaway, map, timeline, or macro transition showing cause and effect.",
        "Return to evidence; one minimal label separates fact, model, myth, and uncertainty.",
        "Complete the visual action and hold a clean final frame for the takeaway.",
    ]
    cursor, result = 0, []
    for number, (duration, line, purpose, visual) in enumerate(zip(durations, lines, purposes, visuals), 1):
        result.append({"scene": number, "start_seconds": cursor, "end_seconds": cursor + duration, "purpose": purpose, "narration": line, "visual_direction": visual, "preview_route": "open_source_motion", "final_route": "premium_video" if number in {1, 3, 5} else "deterministic_or_premium", "continuity": f"consistent {brand_slug} visual grammar, palette, scale, and screen direction"})
        cursor += duration
    return result


def _platform_packages(brand: dict[str, Any], title: str, hook: str, payoff: str, pillar: str) -> list[dict[str, Any]]:
    brand_tag = brand["display_name"].replace(" ", "")
    tags = [brand_tag, pillar.replace(" ", ""), "Explained", "ShortVideo"]
    return [
        {"platform": "facebook", "title": title, "caption": f"{hook} {payoff}", "hashtags": tags, "cta": "What should we explain next?"},
        {"platform": "youtube_shorts", "title": title[:100], "caption": payoff, "hashtags": tags[:3], "cta": "Subscribe for the next visual explanation."},
        {"platform": "tiktok", "title": title, "caption": f"{hook} Watch the full reveal.", "hashtags": tags, "cta": "Follow for the next breakdown."},
    ]


def _seed_ideas(brand: dict[str, Any]) -> list[dict[str, Any]]:
    existing = list(brand.get("ideas") or [])
    if existing:
        return existing
    catalog = HISTORIQ_SEEDS if brand["slug"] == "historiq" else ANI_FILMS_SEEDS
    return [{"title": title, "concept": concept, "pillar": pillar, "format_name": "vertical_short"} for title, concept, pillar in catalog]


def expand_portfolio_config(config: dict[str, Any], *, target: int = 120) -> dict[str, Any]:
    result = copy.deepcopy(config)
    start = date.fromisoformat(result["month_start"])
    for brand in result["brands"]:
        if brand["slug"] not in CURRENT_BRANDS:
            continue
        source = _seed_ideas(brand)
        ideas = []
        for index in range(target):
            base = source[index % len(source)]
            angle = ANGLE_LABELS[(index // len(source)) % len(ANGLE_LABELS)]
            treatment = animal_angle(base, angle) if brand["slug"] in {"rawr-nation", "animal-x"} else _generic_angle(base, angle, brand["slug"])
            clock, slot_name, tier = SLOT_POLICY[index % 4]
            ideas.append({"scheduled_for": (start + timedelta(days=index // 4)).isoformat(), "scheduled_time_local": clock, "title": treatment["title"], "concept": treatment["setup"], "format_name": "vertical_feature" if tier == "premium" else "vertical_short", "pillar": base["pillar"], "editorial_angle": angle, "daily_slot": slot_name, "production_tier": tier, "source_title": base["title"]})
        brand["monthly_target"] = target
        brand["metadata"]["cadence"] = "4 original Facebook-first videos daily; capacity 8 after analytics approval"
        brand["ideas"] = ideas
    return result


def build_brand_studio(config: dict[str, Any], brand_slug: str, rawr_base: dict[str, Any] | None = None) -> dict[str, Any]:
    expanded = expand_portfolio_config(config)
    brand = next(item for item in expanded["brands"] if item["slug"] == brand_slug)
    originals = {item["title"]: item for item in _seed_ideas(next(item for item in config["brands"] if item["slug"] == brand_slug))}
    rawr_sources = {item["title"]: item["script"] for item in (rawr_base or {}).get("items", [])}
    items = []
    for index, idea in enumerate(brand["ideas"], 1):
        base = originals[idea["source_title"]]
        treatment = animal_angle(base, idea["editorial_angle"]) if brand_slug in {"rawr-nation", "animal-x"} else _generic_angle(base, idea["editorial_angle"], brand_slug)
        scenes = _scenes(treatment, base["concept"], idea["production_tier"] == "premium", brand_slug)
        narration = " ".join(scene["narration"] for scene in scenes)
        inherited = rawr_sources.get(idea["source_title"], {})
        item = {"id": f"{brand_slug}-{expanded['month_start']}-{index:03d}", "scheduled_for": idea["scheduled_for"], "scheduled_time_local": idea["scheduled_time_local"], "title": treatment["title"], "concept": treatment["setup"], "pillar": idea["pillar"], "format": idea["format_name"], "batch": ((index - 1) // 20) + 1, "daily_slot": idea["daily_slot"], "editorial_angle": idea["editorial_angle"], "production_tier": idea["production_tier"], "source_title": idea["source_title"], "duration_seconds": scenes[-1]["end_seconds"], "workflow_stage": "preview_queue" if index <= 6 else "script_review", "scene_plan": scenes}
        item["script"] = {"hook": treatment["hook"], "narration": narration, "payoff": treatment["payoff"], "word_count": len(narration.split()), "fact_review_required": True, "fact_status": inherited.get("fact_status", "research_pending"), "sources": inherited.get("sources", []), "source_scope_note": "Every production treatment requires human claim-by-claim source review."}
        item["voice"] = {"development_provider": "kokoro_local", "style": "credible, energetic explainer", "pace": "fast but intelligible", "production_provider": "human-approved premium or retained local voice"}
        item["thumbnail"] = {"primary_text": treatment["title"].upper()[:48], "alternates": [treatment["hook"].upper()[:48]], "composition": "one dominant subject, one visual question, clean negative space, no collage"}
        item["platform_packages"] = _platform_packages(brand, item["title"], treatment["hook"], treatment["payoff"], item["pillar"])
        item["production"] = {"free_preview": "queued" if index <= 6 else "after_script_review", "premium_render": "blocked_pending_human_approval", "publish": "blocked"}
        item["review"] = {"idea": "ready", "script": "pending_human_review", "voice": "pending_preview", "visual": "pending_preview", "premium_spend": "blocked"}
        item["content_fingerprint"] = _fingerprint({"brand": brand_slug, "title": item["title"], "narration": narration})
        items.append(item)
    return {"schema_version": "p82.portfolio_brand_calendar.v1", "brand": {"slug": brand_slug, "name": brand["display_name"], "primary_platform": brand["primary_platform"], "cadence": brand["metadata"]["cadence"], "pillars": brand["content_pillars"]}, "month_start": expanded["month_start"], "coverage_days": 30, "cadence_policy": {"baseline_per_day": 4, "capacity_per_day": 8, "timezone": "Asia/Karachi", "slots": [dict(time=x[0], purpose=x[1], tier=x[2]) for x in SLOT_POLICY]}, "storage_policy": {"database": "metadata, scripts, approvals, schedules, checksums, analytics", "media": "local filesystem through content:// locators", "database_blobs": False}, "items": items, "summary": {"masters": len(items), "days": 30, "daily_baseline": 4, "facebook_packages": len(items), "youtube_shorts_packages": len(items), "tiktok_packages": len(items), "platform_exports": len(items) * 3, "paid_jobs_started": 0, "publish_jobs_started": 0}}


def build_portfolio_studio(config: dict[str, Any], rawr_base: dict[str, Any] | None = None) -> dict[str, Any]:
    brands = [build_brand_studio(config, slug, rawr_base) for slug in CURRENT_BRANDS]
    return {"schema_version": "p82.portfolio_calendar.v1", "month_start": config["month_start"], "brand_count": len(brands), "brands": brands, "items": [item for brand in brands for item in brand["items"]], "summary": {"masters": sum(brand["summary"]["masters"] for brand in brands), "platform_exports": sum(brand["summary"]["platform_exports"] for brand in brands), "daily_per_brand": 4, "days": 30}}
