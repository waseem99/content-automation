"""Build a complete, review-first month of production packages for one brand."""

from __future__ import annotations

import hashlib
import json
from typing import Any


EDITORIAL: dict[str, tuple[str, str, str, str]] = {
    "The blind spot predators exploit": ("A prey animal can look alert and still never see the predator coming.", "Eye placement creates broad awareness, but the remaining visual gap can become an approach lane.", "Survival can turn on the few degrees an animal cannot monitor.", "THE GAP IT CAN'T SEE"),
    "Why owl flight sounds like nothing": ("An owl does not merely fly quietly. Its wings dismantle the sound before prey can react.", "Comb-like leading edges and soft fringes break turbulent airflow into smaller, quieter patterns.", "The silence is not magic; it is feather structure controlling air.", "WHY OWLS FLY SILENT"),
    "The shrimp punch that flashes": ("This strike is so fast that the water delivers a second hit.", "The club accelerates water into a low-pressure cavitation bubble that collapses with shock, heat, and a tiny flash.", "The prey faces the punch—and then the bubble's collapse.", "A PUNCH THAT FLASHES"),
    "A shark's hidden electric map": ("Even buried prey cannot hide its heartbeat from this shark.", "Gel-filled pores around the snout conduct weak electrical changes toward sensory cells.", "In dark or cloudy water, electricity becomes another map of life.", "SHARKS SENSE ELECTRICITY"),
    "The lizard that shoots blood": ("Corner this lizard and the defence may come from its eyes.", "Pressure around the eye sinuses can rupture tiny vessels and direct a blood stream toward a threat.", "Against some predators, the surprise—and the chemistry—can end the attack.", "BLOOD FROM ITS EYES?"),
    "Do camels really store water?": ("A camel's hump is not a water tank.", "It stores fat, while the rest of the body limits water loss and tolerates dehydration unusually well.", "The hump stores fuel; the camel's whole physiology saves water.", "NO WATER IN THE HUMP"),
    "How a gecko defeats gravity": ("A gecko climbs glass without glue, suction, or sticky liquid.", "Microscopic setae branch into vast numbers of close contacts that add weak molecular attractions together.", "By changing toe angle, the same powerful grip releases in an instant.", "NO GLUE. STILL GRIPS."),
    "The snake that sees body heat": ("In darkness, this snake can detect the warm outline of prey.", "Pit membranes respond to infrared energy and the brain combines that signal with ordinary vision.", "The result is not a photograph, but a second channel for locating heat.", "IT CAN SENSE YOUR HEAT"),
    "This frog freezes and wakes up": ("This frog can stop moving, partly freeze, and wake when winter releases it.", "Ice forms mainly outside cells while glucose rises through vulnerable tissues and limits damaging dehydration.", "Its winter survival is controlled freezing—not invulnerability to ice.", "FROZEN—BUT NOT DEAD"),
    "Why zebras are hard to bite": ("Zebra stripes may confuse something much smaller than a lion.", "Experiments show biting flies struggle with their final approach and landing on striped surfaces.", "The strongest evidence points to disrupted landings, not camouflage from big predators.", "STRIPES VS BITING FLIES"),
    "The beetle that drinks fog": ("In a desert with almost no rain, this beetle waits for water in the air.", "It raises its body into fog so droplets collect, merge, and travel down its surface toward the mouth.", "A change in posture turns moving mist into a drink.", "DRINKING WATER FROM FOG"),
    "A crocodile's face can feel ripples": ("A crocodile can detect a disturbance too small for us to notice.", "Dome pressure receptors around the jaws respond when surface ripples bend the skin by tiny amounts.", "At the waterline, its face works like a field of motion sensors.", "ITS FACE FEELS WATER"),
    "Why goats have rectangle pupils": ("A goat's rectangular pupil is a panoramic survival tool.", "Horizontal pupils admit a broad strip of the horizon, and the eyes rotate as the head lowers to graze.", "The landscape stays level even while the animal's head points down.", "WHY GOAT EYES ARE RECTANGLES"),
    "The fish wearing its own flashlight": ("This fish carries living lights beneath its eyes.", "Symbiotic bacteria produce the glow, while the fish can cover or rotate the light organs to control flashes.", "The light can help with orientation, signalling, and feeding in darkness.", "A FISH WITH HEADLIGHTS"),
    "Can porcupines shoot their quills?": ("Porcupines cannot fire their quills across a room.", "The quills detach during direct contact, and microscopic barbs can make some of them difficult to remove.", "The danger is real—but the projectile story is a myth.", "NO, THEY DON'T SHOOT"),
    "The bird that fakes an injury": ("This bird appears to break a wing exactly when a predator gets close.", "A killdeer moves away from its ground nest while exaggerating a vulnerable, dragging-wing display.", "Once the threat follows far enough, the injured bird suddenly flies normally.", "THE BROKEN-WING TRICK"),
    "How seals sleep without drowning": ("Sleeping at sea requires remembering every breath.", "Some seals rest at the surface or sleep with one brain hemisphere more alert while breathing remains deliberate.", "Their sleep strategy changes with species, location, and danger.", "HOW SEALS SLEEP AT SEA"),
    "The insect that hears with its knees": ("A cricket's ears are not on its head.", "Thin tympanal membranes on the forelegs vibrate with sound and transmit the pattern into sensory pathways.", "Its knees place hearing close to the ground—and close to danger.", "EARS ON ITS KNEES"),
    "Why vultures rarely get sick": ("A meal full of dangerous microbes enters this bird—and most do not survive the journey.", "Highly acidic digestion destroys many pathogens, while immune and microbial defences add protection.", "Vultures are resilient, not disease-proof; the defence has limits.", "HOW VULTURES EAT CARRION"),
    "The spider that becomes an ant": ("This spider walks like an ant because being mistaken can keep it alive.", "Body shape, raised front legs, stop-start movement, and association with ants strengthen the disguise.", "For some species, the mimicry also helps them approach prey.", "THE SPIDER PRETENDING TO BE AN ANT"),
    "A whale's ear is not where you think": ("A toothed whale receives much of its underwater sound through the lower jaw.", "Specialized fatty tissues guide vibration toward the middle and inner ear complexes.", "Underwater hearing reshapes the pathway, not the need for an ear.", "A WHALE HEARS THROUGH ITS JAW"),
    "The octopus disappearing act": ("An octopus does not change only its colour—it rebuilds the visible surface of its body.", "Chromatophores, reflective cells, skin papillae, and posture combine in a coordinated display.", "The disguise works because colour, texture, shape, and movement change together.", "FOUR LAYERS OF CAMOUFLAGE"),
    "Do bats really have bad eyesight?": ("Bats are not blind.", "Many species use useful vision alongside echolocation, shifting between channels as light, distance, and task change.", "Echolocation is an extra sense—not proof that the eyes do not work.", "BATS ARE NOT BLIND"),
    "The fox that dives into snow": ("A fox can locate prey it cannot see beneath deep snow.", "It pauses, rotates its ears toward faint movement, estimates position, and commits to a steep head-first pounce.", "The spectacular dive begins with patient listening.", "THE FOX'S SNOW DIVE"),
}


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _platform_packages(title: str, hook: str, payoff: str, pillar: str) -> list[dict[str, Any]]:
    tags = ["Wildlife", "AnimalFacts", "Nature", pillar.replace(" ", "")]
    return [
        {"platform": "facebook", "caption": f"{hook} {payoff}", "title": title, "hashtags": tags[:4], "cta": "Which animal should we decode next?"},
        {"platform": "youtube_shorts", "caption": payoff, "title": title[:100], "hashtags": tags[:3], "cta": "Subscribe for the next animal mechanism."},
        {"platform": "tiktok", "caption": f"{hook} Watch the mechanism unfold.", "title": title, "hashtags": tags, "cta": "Follow for more wildlife reveals."},
    ]


def _scenes(*, hook: str, concept: str, truth: str, payoff: str, feature: bool) -> list[dict[str, Any]]:
    durations = [4, 7, 9, 8, 7] if feature else [3, 6, 8, 7, 6]
    lines = [hook, "Watch the visible clue first.", concept, truth, payoff]
    purposes = ["hook", "observable_evidence", "mechanism", "clarifier", "payoff"]
    visuals = [
        "Immediate behavior-led close-up; movement begins in frame one.",
        "One continuous wildlife action with a restrained tracking move.",
        "Macro-to-micro transition or clean anatomical cutaway showing cause and effect.",
        "Return to real behavior; one minimal label separates evidence from myth.",
        "Complete the action in a wider hero frame and hold the final readable pose.",
    ]
    cursor, result = 0, []
    for index, (duration, narration, purpose, visual) in enumerate(zip(durations, lines, purposes, visuals), 1):
        result.append({
            "scene": index, "start_seconds": cursor, "end_seconds": cursor + duration,
            "purpose": purpose, "narration": narration, "visual_direction": visual,
            "preview_route": "open_source_motion", "final_route": "premium_video" if index in {1, 2, 5} else "deterministic_or_premium",
            "continuity": "same subject, location, light direction, markings, and screen direction",
        })
        cursor += duration
    return result


def build_brand_month_studio(config: dict[str, Any], *, brand_slug: str) -> dict[str, Any]:
    brand = next((item for item in config.get("brands", []) if item.get("slug") == brand_slug), None)
    if not brand:
        raise ValueError(f"Unknown brand: {brand_slug}")
    ideas = list(brand.get("ideas") or [])
    if len(ideas) != int(brand["monthly_target"]):
        raise ValueError("Brand inventory must equal its monthly target before package generation")
    items = []
    for index, idea in enumerate(ideas, 1):
        hook, truth, payoff, thumbnail = EDITORIAL[idea["title"]]
        feature = idea["format_name"] == "vertical_feature"
        scenes = _scenes(hook=hook, concept=idea["concept"], truth=truth, payoff=payoff, feature=feature)
        narration = " ".join(scene["narration"] for scene in scenes)
        item = {
            "id": f"{brand_slug}-{config['month_start']}-{index:02d}",
            "scheduled_for": idea["scheduled_for"], "title": idea["title"],
            "concept": idea["concept"], "pillar": idea["pillar"], "format": idea["format_name"],
            "batch": ((index - 1) // 6) + 1, "duration_seconds": scenes[-1]["end_seconds"],
            "workflow_stage": "preview_queue" if index <= 6 else "script_review",
            "script": {"hook": hook, "narration": narration, "payoff": payoff, "word_count": len(narration.split()), "fact_review_required": True},
            "scene_plan": scenes,
            "voice": {"development_provider": "kokoro_local", "style": "energetic, credible wildlife explainer", "pace": "fast but intelligible", "production_provider": "human-approved premium or retained local voice"},
            "thumbnail": {"primary_text": thumbnail, "alternates": [idea["title"].upper(), hook.upper()[:48]], "composition": "single animal, one impossible-looking action, clean dark negative space, no collage"},
            "platform_packages": _platform_packages(idea["title"], hook, payoff, idea["pillar"]),
            "production": {"free_preview": "queued" if index <= 6 else "after_script_review", "premium_render": "blocked_pending_human_approval", "publish": "blocked"},
            "review": {"idea": "ready", "script": "pending_human_review", "voice": "pending_preview", "visual": "pending_preview", "premium_spend": "blocked"},
        }
        item["content_fingerprint"] = _fingerprint({"brand": brand_slug, "title": item["title"], "narration": narration})
        items.append(item)
    return {
        "schema_version": "p80.brand_month_studio.v1",
        "brand": {"slug": brand_slug, "name": brand["display_name"], "primary_platform": brand["primary_platform"], "cadence": brand["metadata"]["cadence"], "pillars": brand["content_pillars"]},
        "month_start": config["month_start"], "coverage_days": 31,
        "reference_intelligence": {"verified_media": 3, "analyzed_media": 3, "status": "verified_local_evidence", "creative_rule": "reuse pacing and reveal mechanics only; never copy source wording, sequence, or assets"},
        "items": items,
        "summary": {"masters": len(items), "facebook_packages": len(items), "youtube_shorts_packages": len(items), "tiktok_packages": len(items), "scripts_ready": len(items), "batch_one_preview_queue": min(6, len(items)), "paid_jobs_started": 0, "publish_jobs_started": 0},
    }
