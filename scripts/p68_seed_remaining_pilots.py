#!/usr/bin/env python3
"""Seed the four remaining original P68 pilot briefs.

The briefs are editorial inputs only. Facts, generated media, creative quality,
and publication remain human-review blocked.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MECHANICS = [
    "first-second visual contradiction",
    "one continuous subject or mechanism",
    "cause revealed after visible evidence",
    "short memorable payoff",
]


def segment(stage: str, seconds: float, narration: str, caption: str, visual: str, entry: str, exit: str, camera: str, sfx: str) -> dict:
    return {
        "story_stage": stage, "duration_seconds": seconds, "narration": narration,
        "caption": caption, "visual_action": visual, "entry_action": entry,
        "exit_action": exit, "camera": camera,
        "ambience": "One continuous location ambience and restrained cinematic music bed",
        "sfx": sfx,
    }


PILOTS = {
    "rawr-gecko-grip": {
        "brand_profile": "rawr_nation",
        "topic": "how gecko toe structures create dry adhesion",
        "subject": "the same tokay gecko with blue-gray skin, orange spots, intact toes, and anatomically consistent feet",
        "environment": "one charcoal macro-science set built around the same vertical glass panel",
        "lighting": "soft cool key from upper left and narrow amber rim from camera right",
        "color": "photoreal blue-gray gecko, charcoal glass, restrained cyan microscopy accents",
        "direction": "the gecko and magnified contact sequence progress bottom-left to top-right",
        "camera": "natural wildlife macro joined to precise microscopy scale transitions",
        "concept": "rawr_nation-concept-1",
        "facts": [
            ("Gecko adhesive toe pads contain microscopic setae that branch into smaller contacts.", "https://doi.org/10.1073/pnas.192252799", "Evidence for van der Waals adhesion in gecko setae"),
            ("The many close contacts generate dry adhesion without liquid glue.", "https://doi.org/10.1073/pnas.1219317110", "How geckos stick and unstick"),
        ],
        "segments": [
            segment("hook", 4.5, "This gecko can sprint up glass without glue, suction, or sticky liquid.", "NO GLUE. NO SUCTION.", "The gecko takes three clearly visible steps straight up clean glass", "Open on a planted rear foot as the front foot lifts", "End when one front toe pad contacts the glass", "85mm wildlife macro tracking upward", "Three light toe taps"),
            segment("evidence", 5.0, "The secret begins under each wide toe, where ridges divide into dense microscopic hairs.", "MILLIONS OF TINY CONTACTS", "A motivated match move enters the same front toe and reveals dense branching setae", "Continue through the contacting toe pad", "Settle beside one branching seta", "Controlled macro-to-micro push", "Soft scale-shift sweep"),
            segment("mechanism", 5.0, "Each hair branches again, creating enormous contact with the surface at tiny scales.", "CONTACT AT TINY SCALES", "One seta branches into spatula-shaped tips meeting the glass", "Begin on the same seta", "Track the contact wave left-to-right", "Lateral microscopy track", "Fine contact ticks"),
            segment("cause", 5.0, "At that distance, weak molecular attractions add up across the whole foot.", "WEAK FORCES ADD UP", "Restrained cyan force lines appear only at touching tips and spread across the planted foot", "Continue the contact wave", "Force pattern resolves into the full toe silhouette", "Slow pullback through scale", "Low cohesive pulse"),
            segment("release", 5.0, "To let go, the gecko changes the angle of its toes and peels them away.", "ANGLE TO RELEASE", "The same toe hyperextends and peels cleanly from glass in one natural action", "Enter on the resolved toe silhouette", "Finish as the foot swings upward", "High-speed side macro", "Single soft peel accent"),
            segment("payoff", 5.5, "So the grip is powerful, reversible, and dry: geometry turns tiny forces into a climbing system.", "GEOMETRY BECOMES GRIP", "Return to the same gecko completing the climb and pausing above the glass edge", "Match the upward foot swing", "Hold the gecko safely perched for half a second", "Measured pullback to hero frame", "Warm resolve"),
        ],
    },
    "rawr-archerfish-aim": {
        "brand_profile": "rawr_nation",
        "topic": "how archerfish compensate for refraction while targeting prey",
        "subject": "the same banded archerfish with five dark bars, intact fins, and consistent scale pattern",
        "environment": "one shallow mangrove tank with the same branch, waterline, and single insect above it",
        "lighting": "dappled daylight from upper left with stable caustics below the surface",
        "color": "natural olive water, silver fish, dark mangrove wood, restrained amber trajectory accents",
        "direction": "the fish approaches left-to-right and the water jet travels lower-left to upper-right",
        "camera": "split-level wildlife cinematography with restrained explanatory overlays",
        "concept": "rawr_nation-concept-2",
        "facts": [
            ("Archerfish shoot water jets to dislodge aerial prey.", "https://doi.org/10.1016/j.cub.2006.06.033", "Archerfish actively control the hydrodynamics of their jets"),
            ("They can account for the optical displacement caused by refraction at the water surface.", "https://doi.org/10.1242/jeb.02348", "Visual processing and target selection in archerfish"),
        ],
        "segments": [
            segment("hook", 4.5, "This fish hits a target above water even though the surface makes it appear displaced.", "THE TARGET IS NOT WHERE IT LOOKS", "A split-level view holds fish below and insect above while one apparent ray bends", "Open on the insect reflection rippling", "End as the fish settles beneath the branch", "Locked split-level 70mm view", "Waterline shimmer"),
            segment("setup", 5.0, "Light changes direction when it crosses from air into water, shifting the insect's apparent position.", "THE SURFACE BENDS LIGHT", "Clean rays from the insect bend at the same waterline toward the same fish", "Continue from the rippling reflection", "Converge rays at the fish's eye", "Slow push along waterline", "Quiet refractive chime"),
            segment("aim", 5.0, "The archerfish learns the relationship between what it sees and where the target really is.", "VISION BECOMES A MAP", "The fish holds position while a restrained true-position marker separates from the apparent position", "Begin at the same eye-line", "Fish rotates its body into firing posture", "Underwater profile track", "Subtle lock-on pulse"),
            segment("jet", 4.5, "Then its mouth shapes a fast water jet aimed through the surface.", "A WATER JET FIRES", "One continuous high-speed shot shows the mouth jet crossing the waterline", "Start on firing posture", "Follow the jet toward the insect", "High-speed action track", "Sharp water launch"),
            segment("impact", 5.0, "The jet strengthens toward the front, concentrating the impact near the target.", "THE IMPACT CONCENTRATES", "Macro slow motion follows later water catching the leading jet just before impact", "Continue along the same jet", "Insect releases from branch without distress", "Telephoto high-speed macro", "Clean droplet impact"),
            segment("payoff", 5.5, "It is not a lucky shot. The fish combines optics, learned calibration, and precise fluid control.", "OPTICS + CONTROL", "The insect lands on the surface and the same fish turns toward it in one natural motion", "Match the falling insect", "End before feeding on a clean water ripple", "Gentle overhead pullback", "Restrained payoff rise"),
        ],
    },
    "animal-prairie-dog-alarm": {
        "brand_profile": "animal_x",
        "topic": "how prairie dog alarm calls carry information about threats",
        "subject": "the same adult black-tailed prairie dog with a small notch in the right ear and natural proportions",
        "environment": "one shortgrass colony beside the same burrow mound under clear late-afternoon sky",
        "lighting": "warm sun from camera left with stable long shadows and a soft blue sky fill",
        "color": "natural tawny fur, ochre soil, sage grass, restrained rust-red threat accents",
        "direction": "the prairie dog faces frame right and colony response moves right-to-left toward burrows",
        "camera": "patient low wildlife telephoto with behavior-led cuts and no anthropomorphic staging",
        "concept": "animal_x-concept-1",
        "facts": [
            ("Prairie dog alarm calls vary with predator category and can encode descriptive information.", "https://doi.org/10.1016/S0003-3472(05)80948-1", "Semantic information in prairie dog alarm calls"),
            ("Black-tailed prairie dogs use alarm calling and vigilance as anti-predator behavior.", "https://www.nps.gov/articles/000/black-tailed-prairie-dogs.htm", "National Park Service — Black-tailed prairie dogs"),
        ],
        "segments": [
            segment("hook", 4.5, "One prairie dog's call can change how an entire colony reacts to danger.", "ONE CALL CHANGES THE COLONY", "The notched-ear prairie dog rises on the mound as distant heads turn", "Open at grass height with calm foraging", "End on the caller inhaling", "Low 300mm push", "Natural wind and one breath"),
            segment("threat", 5.0, "The call is not simply noise. Its pattern can vary with the kind of threat detected.", "THE PATTERN CHANGES", "A distant coyote crosses frame right while the caller gives a natural alarm posture", "Continue from the inhale", "Hold on one completed call", "Telephoto rack focus from caller to coyote", "One naturalistic call accent"),
            segment("signal", 5.0, "Changes in pitch and timing carry information through the colony.", "PITCH + TIMING", "Restrained waveform traces the real call while neighboring animals listen", "Match the completed call", "Waveform fades before behavior changes", "Locked respectful medium shot", "Call tail bridges the cut"),
            segment("response", 5.0, "Nearby animals become vigilant and choose cover according to what they detect.", "THE COLONY RESPONDS", "Three prairie dogs turn toward frame right then move toward separate burrows", "Begin as the waveform fades", "Follow the last animal to the mound edge", "Ground-level lateral track", "Grass movement and footfalls"),
            segment("network", 5.0, "Because many animals can hear and answer, warning spreads beyond the first lookout.", "A LIVING WARNING NETWORK", "A wide shot reveals calls and movement passing across the connected colony", "Rise from the mound edge", "Settle on the original caller still scanning", "Slow crane to wide geography", "Distant call-and-response bed"),
            segment("payoff", 5.5, "The result is a warning system built from attention, sound, and coordinated behavior.", "ATTENTION BECOMES SAFETY", "The coyote exits far away and the same caller lowers naturally as calm returns", "Return to the original mound", "End on resumed foraging with no staged celebration", "Patient telephoto pullback", "Wind resolves without a sting"),
        ],
    },
    "animal-octopus-arms": {
        "brand_profile": "animal_x",
        "topic": "how octopus arms use distributed neural control and local sensing",
        "subject": "the same common octopus with a pale crescent scar above the left eye, seven visible intact arms, and consistent mantle pattern",
        "environment": "one rocky Mediterranean reef ledge with the same red sponge and narrow crevice",
        "lighting": "soft underwater daylight from upper left with stable particulate and no artificial spotlight",
        "color": "natural rust-brown octopus, blue-green water, pale limestone, restrained violet neural accents",
        "direction": "the octopus travels left-to-right and the explored crevice remains frame right",
        "camera": "observational underwater macro connected by motivated arm-led moves",
        "concept": "animal_x-concept-2",
        "facts": [
            ("A large proportion of octopus neurons are located in the arms and peripheral nervous system.", "https://doi.org/10.1016/j.cub.2013.05.010", "How nervous systems evolve in relation to their embodiment"),
            ("Octopus arms combine local sensory processing with coordination from the central brain.", "https://doi.org/10.1016/j.cub.2020.08.001", "Octopus arm nervous-system organization and control"),
        ],
        "segments": [
            segment("hook", 4.5, "An octopus arm can explore, taste, and adjust before the whole animal changes course.", "AN ARM EXPLORES FIRST", "One arm of the scar-marked octopus enters a crevice while the mantle remains still", "Open on the same crevice and approaching arm tip", "End as two suckers contact stone", "Underwater 90mm macro", "Natural water and soft sucker contacts"),
            segment("sensing", 5.0, "Its suckers are packed with sensors that sample touch and chemicals on the surface.", "SUCKERS TOUCH AND TASTE", "Macro follows the same suckers rolling sequentially across textured limestone", "Continue from the first two contacts", "Arm tip curls around the corner", "Arm-level tracking macro", "Fine tactile clicks"),
            segment("network", 5.0, "Much of the octopus nervous system lies outside the central brain, including dense networks in the arms.", "A NERVOUS SYSTEM IN THE ARMS", "Restrained violet paths reveal local neural networks inside the moving arm without changing anatomy", "Follow the curl around the corner", "Neural activity travels back toward the arm base", "Transparent anatomical match move", "Low neural pulse"),
            segment("control", 5.0, "Those networks handle local details while still coordinating with signals from the brain.", "LOCAL CONTROL, SHARED GOAL", "The explored arm adjusts grip as two neighboring arms brace the same octopus", "Continue activity toward the body", "Body begins a measured turn frame right", "Medium observational profile", "Three soft grip accents"),
            segment("movement", 5.0, "That division of work helps a soft body control many flexible joints at once.", "COORDINATING A SOFT BODY", "The same octopus flows through the narrow crevice with coordinated arm waves", "Match the measured turn", "Mantle clears the crevice", "Stable lateral underwater track", "Water rush kept subtle"),
            segment("payoff", 5.5, "It is one animal, but movement emerges from a conversation between brain, arms, and environment.", "ONE BODY, DISTRIBUTED CONTROL", "The octopus settles beyond the crevice and resumes natural exploration", "Continue after the mantle clears", "Hold on calm arm-by-arm exploration", "Slow respectful pullback", "Ambient reef resolve"),
        ],
    },
}


def build_brief(pilot_id: str, data: dict) -> dict:
    return {
        "pilot_id": pilot_id, "brand_profile": data["brand_profile"], "topic": data["topic"],
        "selected_concept_id": data["concept"], "reusable_mechanics": MECHANICS,
        "continuity_bible": {
            "subject_identity": data["subject"], "environment": data["environment"],
            "lighting": data["lighting"], "color_treatment": data["color"],
            "screen_direction": data["direction"], "camera_language": data["camera"],
        },
        "factual_notes": [
            {"claim": claim, "source_url": url, "source_title": title, "review_status": "pending_human_fact_review"}
            for claim, url, title in data["facts"]
        ],
        "source_phrases_for_originality_check": [],
        "script_segments": data["segments"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="p68-pilots")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    written = []
    for pilot_id, data in PILOTS.items():
        path = root / pilot_id / "source-brief.json"
        if path.exists() and not args.overwrite:
            raise SystemExit(f"Refusing to overwrite {path}; pass --overwrite intentionally")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(build_brief(pilot_id, data), indent=2) + "\n", encoding="utf-8")
        written.append(str(path))
    print(json.dumps({"written": written, "media_generated": False, "publish_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
