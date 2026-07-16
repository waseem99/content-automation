"""Deterministic motion graphics for P68 scientific/mechanism shots.

These shots are code-authored rather than generative-model guesses. They are
intended for mechanisms where visual precision and repeatability matter more
than photorealistic subject movement.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFilter

from src.p68_clip_stitcher import probe_media, sha256_file
from src.p68_job_state import atomic_write_json


ANIMATION_VERSION = "p68.scientific_animation.v4"
CANVAS = (540, 960)
FPS = 30


def _ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def _gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", CANVAS)
    pixels = image.load()
    for y in range(CANVAS[1]):
        amount = y / (CANVAS[1] - 1)
        color = tuple(round(a + (b - a) * amount) for a, b in zip(top, bottom))
        for x in range(CANVAS[0]):
            pixels[x, y] = color
    return image


def _glow(base: Image.Image, shapes: Callable[[ImageDraw.ImageDraw], None], radius: int = 16) -> None:
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    shapes(ImageDraw.Draw(layer))
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    base.paste(blurred, (0, 0), blurred)
    base.paste(layer, (0, 0), layer)


def _eye_optics_frame(progress: float) -> Image.Image:
    image = _gradient((7, 13, 24), (2, 4, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    center = (285, 475)
    # Eyeball cross section, cornea/lens at left and retina at right.
    draw.ellipse((90, 270, 480, 680), fill=(28, 48, 66, 255), outline=(112, 185, 210, 255), width=4)
    draw.ellipse((105, 285, 465, 665), fill=(12, 24, 38, 255))
    draw.arc((110, 292, 458, 660), -75, 75, fill=(255, 205, 92, 235), width=14)
    draw.ellipse((155, 390, 218, 560), fill=(82, 160, 186, 100), outline=(153, 226, 238, 220), width=3)
    draw.ellipse((132, 405, 170, 545), fill=(94, 177, 199, 80), outline=(161, 224, 231, 180), width=2)
    beam_x = 70 + 330 * _ease(progress)
    beam_points = [(40, 452), (beam_x, 476), (40, 504)]
    draw.polygon(beam_points, fill=(255, 216, 104, 45))
    _glow(
        image,
        lambda glow: glow.line((45, 478, beam_x, 478), fill=(255, 221, 112, 230), width=5),
        13,
    )
    hit = _ease((progress - 0.68) / 0.22)
    if hit:
        radius = 8 + 28 * hit
        draw.ellipse((442 - radius, 476 - radius, 442 + radius, 476 + radius), outline=(255, 213, 88, int(230 * (1 - hit / 2))), width=5)
    for index in range(16):
        angle = index / 16 * math.tau
        x = center[0] + math.cos(angle) * 230
        y = center[1] + math.sin(angle) * 230
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(112, 189, 210, 120))
    return image


def _retina_disc_frame(progress: float) -> Image.Image:
    image = _gradient((20, 8, 20), (4, 6, 14))
    draw = ImageDraw.Draw(image, "RGBA")
    disc = (365, 480)
    rng = random.Random(3105)
    reveal = _ease(progress / 0.45)
    for _ in range(330):
        x, y = rng.randrange(35, 505), rng.randrange(230, 735)
        distance = math.dist((x, y), disc)
        if distance < 58:
            continue
        alpha = int(55 + 125 * reveal)
        length = 5 + int(6 * (1 - min(distance / 400, 1)))
        color = (248, 170, 94, alpha) if (x + y) % 3 else (112, 205, 196, alpha)
        draw.line((x, y, x + math.sin(y) * 3, y + length), fill=color, width=2)
    pulse = 1 + 0.06 * math.sin(progress * math.tau * 2)
    radius = 56 * pulse
    _glow(
        image,
        lambda glow: glow.ellipse(
            (disc[0] - radius, disc[1] - radius, disc[0] + radius, disc[1] + radius),
            fill=(255, 196, 105, 90),
            outline=(255, 220, 150, 220),
            width=5,
        ),
        22,
    )
    # Fibres converge toward the optic disc while the central area remains cell-free.
    for index in range(22):
        y = 275 + index * 19
        draw.bezier if False else None
        draw.line((55, y, disc[0] - 58, disc[1] + (y - 480) * 0.15), fill=(196, 118, 94, 70), width=2)
    ring = 42 + 18 * _ease((progress - 0.5) / 0.4)
    draw.ellipse((disc[0] - ring, disc[1] - ring, disc[0] + ring, disc[1] + ring), outline=(255, 238, 190, 220), width=4)
    return image


def _optic_nerve_frame(progress: float) -> Image.Image:
    image = _gradient((5, 13, 22), (2, 4, 9))
    draw = ImageDraw.Draw(image, "RGBA")
    eye = (240, 440)
    draw.ellipse((60, 255, 420, 625), fill=(22, 45, 61, 255), outline=(114, 198, 214, 220), width=4)
    draw.arc((78, 273, 402, 607), -72, 72, fill=(255, 198, 92, 230), width=13)
    # Optic nerve physically exits the rear of the eye.
    points = [(405, 418), (520, 400), (540, 420), (540, 535), (515, 548), (405, 514)]
    draw.polygon(points, fill=(210, 135, 93, 210), outline=(255, 188, 116, 235))
    signal = _ease(progress)
    for index in range(9):
        offset = index * 16
        x = 402 + ((signal * 180 + offset) % 170)
        y = 445 + math.sin(index * 1.7) * 28
        _glow(
            image,
            lambda glow, x=x, y=y: glow.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(116, 226, 232, 230)),
            9,
        )
    opening = 35 + 9 * math.sin(progress * math.tau)
    draw.ellipse((395 - opening, 466 - opening, 395 + opening, 466 + opening), outline=(255, 224, 161, 235), width=5)
    return image


def _dot_test_frame(progress: float) -> Image.Image:
    image = _gradient((10, 15, 24), (3, 6, 12))
    draw = ImageDraw.Draw(image, "RGBA")
    fixation = (170, 470)
    draw.line((fixation[0] - 22, fixation[1], fixation[0] + 22, fixation[1]), fill=(235, 243, 248, 255), width=5)
    draw.line((fixation[0], fixation[1] - 22, fixation[0], fixation[1] + 22), fill=(235, 243, 248, 255), width=5)
    travel = _ease(min(progress / 0.72, 1))
    dot_x = 475 - 190 * travel
    blind_center = 320
    distance = abs(dot_x - blind_center)
    alpha = int(255 * min(1, distance / 38))
    if progress > 0.78:
        alpha = int(255 * _ease((progress - 0.78) / 0.2))
    _glow(
        image,
        lambda glow: glow.ellipse((dot_x - 13, 457, dot_x + 13, 483), fill=(255, 210, 77, alpha)),
        10,
    )
    # A restrained guide arc communicates movement without adding words.
    draw.arc((270, 405, 485, 540), 190, 330, fill=(105, 178, 204, 70), width=2)
    return image


def _reconstruction_frame(progress: float) -> Image.Image:
    image = _gradient((8, 12, 20), (2, 4, 9))
    draw = ImageDraw.Draw(image, "RGBA")
    rng = random.Random(6806)
    tiles = []
    for row in range(11):
        for column in range(7):
            x, y = 48 + column * 64, 170 + row * 58
            hue = 105 + rng.randrange(-35, 36)
            color = (hue, 125 + rng.randrange(-20, 26), 150 + rng.randrange(-25, 30), 220)
            tiles.append((x, y, color))
    gap = (3, 5)
    for index, (x, y, color) in enumerate(tiles):
        column, row = index % 7, index // 7
        if (column, row) == gap:
            continue
        draw.rounded_rectangle((x, y, x + 54, y + 48), radius=9, fill=color)
    fill = _ease((progress - 0.28) / 0.58)
    x, y = 48 + gap[0] * 64, 170 + gap[1] * 58
    if fill:
        neighbor = (118, 139, 165, int(235 * fill))
        spread = 18 * (1 - fill)
        draw.rounded_rectangle((x - spread, y - spread, x + 54 + spread, y + 48 + spread), radius=9, fill=neighbor)
    ring_alpha = int(180 * (1 - fill))
    draw.rounded_rectangle((x - 6, y - 6, x + 60, y + 54), radius=12, outline=(255, 207, 101, ring_alpha), width=4)
    return image


def _draw_elephant_leg(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, seed: int) -> None:
    left, top, right, bottom = box
    width = right - left
    ankle = bottom - int((bottom - top) * 0.18)
    outline = [
        (left + int(width * 0.18), top),
        (right - int(width * 0.14), top),
        (right - int(width * 0.06), ankle),
        (right, bottom - int(width * 0.10)),
        (right - int(width * 0.09), bottom),
        (left + int(width * 0.05), bottom),
        (left, bottom - int(width * 0.12)),
        (left + int(width * 0.10), ankle),
    ]
    draw.polygon(outline, fill=(91, 78, 66, 255), outline=(157, 137, 113, 235))
    # Horizontal folds and small skin creases provide elephant-specific texture.
    for index in range(10):
        y = top + 45 + index * max(22, int((ankle - top - 60) / 10))
        inset = 13 + (index % 3) * 4
        draw.arc((left + inset, y - 12, right - inset, y + 17), 8, 172, fill=(58, 49, 43, 125), width=3)
    rng = random.Random(seed)
    for _ in range(55):
        x, y = rng.randrange(left + 15, right - 14), rng.randrange(top + 15, bottom - 25)
        draw.line((x, y, x + rng.randrange(-5, 6), y + rng.randrange(3, 11)), fill=(55, 47, 41, 80), width=1)
    # Four rounded toenails at the broad front edge.
    nail_width = int(width * 0.16)
    start = left + int(width * 0.14)
    for index in range(4):
        x = start + index * int(width * 0.19)
        draw.pieslice(
            (x, bottom - int(width * 0.21), x + nail_width, bottom + int(width * 0.03)),
            180,
            360,
            fill=(175, 156, 130, 220),
            outline=(202, 181, 150, 210),
        )


def _ground_signal_frame(progress: float) -> Image.Image:
    image = _gradient((86, 112, 125), (43, 28, 19))
    draw = ImageDraw.Draw(image, "RGBA")
    horizon = 290
    draw.rectangle((0, horizon, 540, 960), fill=(78, 52, 33, 255))
    for depth, color in ((350, (111, 75, 44, 255)), (500, (71, 47, 31, 255)), (690, (48, 34, 27, 255))):
        draw.line((0, depth, 540, depth + 25), fill=color, width=55)
    # Stylized planted elephant foot at frame right; deliberately not a claim
    # about an exact sensory organ.
    _draw_elephant_leg(draw, (340, 120, 515, 710), seed=3303)
    center = 45 + 335 * _ease(progress)
    for ring in range(5):
        radius = 18 + ring * 27
        alpha = max(0, 190 - ring * 28)
        draw.arc((center - radius, 610 - radius / 2, center + radius, 610 + radius / 2), 200, 340, fill=(239, 190, 94, alpha), width=5)
    for index in range(36):
        x = (index * 73 + int(progress * 330)) % 540
        y = 565 + (index * 41) % 85
        draw.ellipse((x, y, x + 3, y + 3), fill=(226, 181, 104, 100))
    return image


def _foot_pathway_frame(progress: float) -> Image.Image:
    image = _gradient((28, 42, 44), (35, 24, 19))
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_elephant_leg(draw, (120, 55, 430, 905), seed=3404)
    # Abstract upward pathway, explicitly presented as explanatory overlay.
    path = [(270, 820), (252, 700), (292, 585), (260, 465), (300, 345), (280, 205)]
    draw.line(path, fill=(94, 161, 161, 110), width=8, joint="curve")
    count = min(len(path), 1 + int(_ease(progress) * len(path)))
    for point in path[:count]:
        _glow(
            image,
            lambda glow, point=point: glow.ellipse((point[0] - 10, point[1] - 10, point[0] + 10, point[1] + 10), fill=(111, 231, 216, 235)),
            13,
        )
    travel = _ease(progress) * (len(path) - 1)
    segment = min(int(travel), len(path) - 2)
    amount = travel - segment
    arrival = (
        path[segment][0] + (path[segment + 1][0] - path[segment][0]) * amount,
        path[segment][1] + (path[segment + 1][1] - path[segment][1]) * amount,
    )
    _glow(
        image,
        lambda glow: glow.ellipse(
            (arrival[0] - 14, arrival[1] - 14, arrival[0] + 14, arrival[1] + 14),
            fill=(161, 255, 232, 245),
        ),
        15,
    )
    draw.ellipse((arrival[0] - 16, arrival[1] - 16, arrival[0] + 16, arrival[1] + 16), outline=(224, 255, 232, 230), width=4)
    return image


def _glass_stage() -> Image.Image:
    image = _gradient((7, 18, 27), (2, 6, 12))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((72, 80, 470, 900), radius=26, fill=(64, 112, 130, 32), outline=(136, 213, 226, 120), width=3)
    for offset in range(7):
        x = 105 + offset * 54
        draw.line((x, 105, x - 35, 875), fill=(125, 205, 218, 22), width=2)
    draw.line((455, 100, 455, 875), fill=(255, 191, 88, 90), width=4)
    return image


def _draw_gecko(draw: ImageDraw.ImageDraw, center: tuple[float, float], *, stride: float = 0, scale: float = 1.0) -> None:
    cx, cy = center
    body_w, body_h = 112 * scale, 260 * scale
    skin, outline, spots = (73, 116, 132, 255), (145, 208, 211, 230), (232, 132, 62, 235)
    draw.ellipse((cx - body_w / 2, cy - body_h / 2, cx + body_w / 2, cy + body_h / 2), fill=skin, outline=outline, width=max(2, round(3 * scale)))
    draw.ellipse((cx - 48 * scale, cy - 180 * scale, cx + 48 * scale, cy - 90 * scale), fill=skin, outline=outline, width=max(2, round(3 * scale)))
    draw.ellipse((cx - 23 * scale, cy - 155 * scale, cx - 7 * scale, cy - 138 * scale), fill=(245, 205, 92, 255))
    draw.ellipse((cx + 7 * scale, cy - 155 * scale, cx + 23 * scale, cy - 138 * scale), fill=(245, 205, 92, 255))
    for index in range(11):
        x = cx + math.sin(index * 2.1) * body_w * 0.28
        y = cy - body_h * 0.35 + index * body_h * 0.07
        draw.ellipse((x - 7 * scale, y - 5 * scale, x + 7 * scale, y + 5 * scale), fill=spots)
    tail = [(cx, cy + body_h / 2 - 8), (cx + 28 * scale, cy + 190 * scale), (cx - 6 * scale, cy + 260 * scale)]
    draw.line(tail, fill=skin, width=max(8, round(28 * scale)), joint="curve")
    for side in (-1, 1):
        for pair in range(2):
            anchor_y = cy - 65 * scale + pair * 125 * scale
            phase = stride + pair * math.pi + (0 if side == 1 else math.pi)
            lift = math.sin(phase) * 24 * scale
            elbow = (cx + side * 75 * scale, anchor_y + lift)
            foot = (cx + side * 118 * scale, anchor_y - 22 * scale + lift)
            draw.line((cx + side * 35 * scale, anchor_y, *elbow, *foot), fill=skin, width=max(5, round(14 * scale)), joint="curve")
            for toe in range(4):
                angle = -0.55 + toe * 0.34
                end = (foot[0] + side * math.cos(angle) * 34 * scale, foot[1] + math.sin(angle) * 22 * scale)
                draw.line((*foot, *end), fill=outline, width=max(2, round(5 * scale)))


def _gecko_climb_frame(progress: float) -> Image.Image:
    image = _glass_stage()
    draw = ImageDraw.Draw(image, "RGBA")
    rise = 390 * _ease(progress)
    _draw_gecko(draw, (275, 680 - rise), stride=progress * math.tau * 3, scale=0.82)
    for index in range(3):
        pulse = (progress * 3 - index) % 1
        y = 705 - index * 125 - rise * 0.4
        draw.ellipse((118, y - 18 - pulse * 22, 154, y + 18 + pulse * 22), outline=(255, 210, 88, int(180 * (1 - pulse))), width=4)
    return image


def _toe_setae_frame(progress: float) -> Image.Image:
    image = _gradient((8, 20, 28), (3, 8, 14))
    draw = ImageDraw.Draw(image, "RGBA")
    zoom = _ease(progress)
    pad_left, pad_top, pad_right, pad_bottom = 65, 255, 475, 705
    draw.rounded_rectangle((pad_left, pad_top, pad_right, pad_bottom), radius=90, fill=(65, 112, 125, 255), outline=(147, 218, 218, 220), width=4)
    for ridge in range(12):
        y = pad_top + 38 + ridge * 31
        draw.arc((95, y - 15, 445, y + 28), 185, 355, fill=(171, 224, 216, 180), width=5)
    count = 35 + int(110 * zoom)
    for index in range(count):
        x = 95 + (index * 37) % 350
        y = 325 + (index * 53) % 320
        length = 18 + 38 * zoom
        draw.line((x, y, x + math.sin(index) * 7, y + length), fill=(108, 225, 218, 150), width=2)
    ring = 150 - 85 * zoom
    draw.ellipse((270 - ring, 485 - ring, 270 + ring, 485 + ring), outline=(255, 195, 83, 190), width=5)
    return image


def _seta_branch_frame(progress: float) -> Image.Image:
    image = _gradient((8, 15, 24), (2, 5, 10))
    draw = ImageDraw.Draw(image, "RGBA")
    trunk_x, base_y = 270, 800
    reveal = _ease(progress)
    draw.line((trunk_x, base_y, trunk_x, 420), fill=(97, 196, 188, 230), width=13)
    branches = 8
    for index in range(branches):
        amount = _ease((reveal * branches - index) / 1.8)
        if amount <= 0:
            continue
        side = -1 if index % 2 else 1
        start_y = 470 + index * 36
        end_x = trunk_x + side * 150 * amount
        end_y = start_y - 105 * amount
        draw.line((trunk_x, start_y, end_x, end_y), fill=(126, 224, 213, 220), width=6)
        for tip in range(4):
            tx = end_x + side * (18 + tip * 13) * amount
            ty = end_y + (tip - 1.5) * 13
            draw.ellipse((tx - 15, ty - 5, tx + 15, ty + 5), fill=(232, 180, 82, 210))
    draw.line((48, 305, 492, 305), fill=(166, 218, 229, 170), width=5)
    return image


def _molecular_contact_frame(progress: float) -> Image.Image:
    image = _seta_branch_frame(1.0)
    draw = ImageDraw.Draw(image, "RGBA")
    wave = _ease(progress)
    for index in range(24):
        x = 70 + index * 17
        active = max(0.0, 1 - abs(index / 23 - wave) * 5)
        if active:
            _glow(image, lambda glow, x=x, active=active: glow.line((x, 280, x, 340), fill=(92, 232, 238, int(240 * active)), width=5), 10)
        draw.line((x, 292, x, 318), fill=(96, 214, 220, 80 + int(110 * active)), width=2)
    return image


def _toe_release_frame(progress: float) -> Image.Image:
    image = _gradient((8, 18, 26), (2, 6, 11))
    draw = ImageDraw.Draw(image, "RGBA")
    glass_x = 420
    draw.line((glass_x, 90, glass_x, 875), fill=(142, 218, 229, 180), width=6)
    peel = _ease(progress)
    angle = peel * 0.9
    origin = (glass_x - 5, 520)
    pad_length = 285
    end = (origin[0] - math.cos(angle) * pad_length, origin[1] - math.sin(angle) * pad_length)
    draw.line((*origin, *end), fill=(70, 121, 133, 255), width=72)
    for toe in range(5):
        amount = toe / 4
        x = origin[0] + (end[0] - origin[0]) * amount
        y = origin[1] + (end[1] - origin[1]) * amount
        draw.ellipse((x - 22, y - 15, x + 22, y + 15), outline=(149, 225, 217, 220), width=4)
    draw.arc((205, 355, 485, 650), 120, 225, fill=(255, 193, 82, 180), width=5)
    return image


def _gecko_payoff_frame(progress: float) -> Image.Image:
    image = _glass_stage()
    draw = ImageDraw.Draw(image, "RGBA")
    settle = math.sin(_ease(progress) * math.pi) * 8
    _draw_gecko(draw, (275, 325 + settle), stride=math.pi * 0.25, scale=0.88)
    glow = _ease((progress - 0.45) / 0.45)
    if glow:
        _glow(image, lambda layer: layer.ellipse((115, 120, 425, 535), outline=(255, 199, 82, int(190 * glow)), width=6), 22)
    return image


RENDERERS: dict[tuple[str, str], Callable[[float], Image.Image]] = {
    ("rawr-blind-spot", "S02"): _eye_optics_frame,
    ("rawr-blind-spot", "S03"): _retina_disc_frame,
    ("rawr-blind-spot", "S04"): _optic_nerve_frame,
    ("rawr-blind-spot", "S05"): _dot_test_frame,
    ("rawr-blind-spot", "S06"): _reconstruction_frame,
    ("animal-elephant-signals", "S03"): _ground_signal_frame,
    ("animal-elephant-signals", "S04"): _foot_pathway_frame,
    ("rawr-gecko-grip", "S01"): _gecko_climb_frame,
    ("rawr-gecko-grip", "S02"): _toe_setae_frame,
    ("rawr-gecko-grip", "S03"): _seta_branch_frame,
    ("rawr-gecko-grip", "S04"): _molecular_contact_frame,
    ("rawr-gecko-grip", "S05"): _toe_release_frame,
    ("rawr-gecko-grip", "S06"): _gecko_payoff_frame,
}


def render_animation(renderer: Callable[[float], Image.Image], output: Path, duration_seconds: float) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    frames = max(2, round(duration_seconds * FPS))
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{CANVAS[0]}x{CANVAS[1]}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-vf",
        "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for index in range(frames):
            image = renderer(index / max(frames - 1, 1)).convert("RGB")
            process.stdin.write(image.tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
        code = process.wait(timeout=300)
    except Exception:
        process.kill()
        raise
    if code:
        raise RuntimeError(stderr[-4000:])
    return probe_media(output)


def render_pilot_science(plan: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    pilot_id = plan["pilot_id"]
    records = []
    for shot in plan["shots"]:
        key = (pilot_id, shot["shot_id"])
        renderer = RENDERERS.get(key)
        if renderer is None:
            continue
        duration = float(shot["duration_seconds"]) + float(shot.get("transition_handle_seconds") or 0.5)
        output = output_dir / f"{shot['shot_id']}.mp4"
        fingerprint = hashlib.sha256(f"{ANIMATION_VERSION}:{pilot_id}:{shot['shot_id']}:{duration}".encode()).hexdigest()
        sidecar = output.with_suffix(".json")
        cached = output.is_file() and sidecar.is_file() and json.loads(sidecar.read_text()).get("fingerprint") == fingerprint
        probe = probe_media(output) if cached else render_animation(renderer, output, duration)
        if not cached:
            atomic_write_json(sidecar, {"fingerprint": fingerprint, "probe": probe})
        records.append(
            {
                "shot_id": shot["shot_id"],
                "path": str(output),
                "provider": ANIMATION_VERSION,
                "model_id": None,
                "prompt_or_asset_reference": f"code:{ANIMATION_VERSION}:{pilot_id}:{shot['shot_id']}",
                "rights_status": "owned",
                "human_review_status": "pending_final_review",
                "output_sha256": sha256_file(output),
                "preview_only": False,
                "probe": probe,
            }
        )
    manifest = {
        "schema_version": ANIMATION_VERSION,
        "pilot_id": pilot_id,
        "clips": records,
        "quality_approved": False,
        "publish_allowed": False,
    }
    path = output_dir / "scientific-animation-manifest.json"
    atomic_write_json(path, manifest)
    return {**manifest, "manifest_path": str(path)}
