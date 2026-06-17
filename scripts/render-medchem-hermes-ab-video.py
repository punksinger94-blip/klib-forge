from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 24

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "media" / "klib-forge-medchem-hermes-ab.mp4"
DEFAULT_THUMBNAIL = (
    ROOT / "dist" / "media" / "klib-forge-medchem-hermes-ab-thumbnail.png"
)
DEFAULT_FFMPEG = Path(r"D:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")

BG = "#090d11"
SURFACE = "#10161c"
SURFACE_2 = "#151d24"
LINE = "#26323c"
TEXT = "#dce3ea"
MUTED = "#8997a3"
ACCENT = "#dfaf4b"
MINT = "#8bc7b1"
RED = "#e47768"
WHITE = "#f5f7f8"

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_SEMIBOLD = Path(r"C:\Windows\Fonts\seguisb.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")
FONT_MONO = Path(r"C:\Windows\Fonts\CascadiaMono.ttf")


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = {
        "regular": [FONT_REGULAR, Path(r"C:\Windows\Fonts\arial.ttf")],
        "semibold": [FONT_SEMIBOLD, FONT_BOLD, Path(r"C:\Windows\Fonts\arialbd.ttf")],
        "bold": [FONT_BOLD, FONT_SEMIBOLD, Path(r"C:\Windows\Fonts\arialbd.ttf")],
        "mono": [FONT_MONO, Path(r"C:\Windows\Fonts\consola.ttf")],
    }
    for candidate in candidates[weight]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


F12 = font(24, "mono")
F14 = font(28)
F16 = font(32)
F18 = font(36, "semibold")
F22 = font(44, "semibold")
F28 = font(56, "bold")
F36 = font(72, "bold")
F48 = font(96, "bold")
F64 = font(128, "bold")


def rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def latest_medchem_report() -> Path:
    reports = sorted(
        (ROOT / "build" / "experiments").glob("medchem-ab-*/report.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        raise SystemExit("No MedChem A/B report found under build/experiments.")
    return reports[0]


def latest_hermes_report() -> Path:
    reports = sorted(
        (ROOT / "build" / "experiments").glob("hermes-klib-ab-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        raise SystemExit("No Hermes A/B report found under build/experiments.")
    return reports[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def base_frame() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), rgb(BG))
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 96):
        draw.line((x, 0, x, HEIGHT), fill="#0d1217", width=1)
    for y in range(0, HEIGHT, 96):
        draw.line((0, y, WIDTH, y), fill="#0d1217", width=1)
    draw.ellipse((1280, -420, 2240, 540), fill="#13130e")
    draw.ellipse((-480, 740, 360, 1580), fill="#0d1716")
    return image


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    face: ImageFont.FreeTypeFont,
    fill: str = TEXT,
    anchor: str | None = None,
) -> None:
    draw.text(xy, value, font=face, fill=fill, anchor=anchor)


def panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = SURFACE,
    outline: str = LINE,
) -> None:
    draw.rounded_rectangle(box, radius=28, fill=fill, outline=outline, width=2)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    fill: str,
    face: ImageFont.FreeTypeFont = F12,
) -> int:
    x, y = xy
    width = int(draw.textlength(value, font=face)) + 36
    draw.rounded_rectangle((x, y, x + width, y + 44), radius=22, fill=fill)
    text(draw, (x + 18, y + 9), value, face, BG)
    return width


def brand(draw: ImageDraw.ImageDraw, subtitle: str) -> None:
    draw.rounded_rectangle((96, 72, 152, 128), radius=10, fill=ACCENT)
    text(draw, (124, 100), "K", F18, BG, anchor="mm")
    text(draw, (174, 72), "K-LIB Forge", F18, WHITE)
    text(draw, (174, 112), subtitle.upper(), F12, MUTED)


def metric_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    score: float,
    color: str,
) -> None:
    panel(draw, box, SURFACE_2)
    x1, y1, x2, y2 = box
    text(draw, (x1 + 36, y1 + 34), label.upper(), F12, MUTED)
    text(draw, (x1 + 36, y1 + 92), f"{score:.2f}", F64, color)
    bar_y = y2 - 58
    draw.rounded_rectangle((x1 + 36, bar_y, x2 - 36, bar_y + 16), radius=8, fill="#242d35")
    draw.rounded_rectangle(
        (x1 + 36, bar_y, x1 + 36 + int((x2 - x1 - 72) * score), bar_y + 16),
        radius=8,
        fill=color,
    )


def title_scene(_: float, medchem: dict[str, Any], hermes: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "A/B TEST EVIDENCE")
    text(draw, (140, 250), "Without K-LIB vs With K-LIB", F48, WHITE)
    text(draw, (140, 374), "MedChem workflow + Hermes Agent MCP", F28, TEXT)
    pill(draw, (140, 480), "FULL TEST GATE PASSED", MINT)
    pill(draw, (520, 480), "GEMMA4:E4B", ACCENT)
    pill(draw, (770, 480), "HERMES MCP", MINT)
    metric_card(
        draw,
        (140, 620, 520, 880),
        "MedChem delta",
        float(medchem["score_delta"]),
        MINT,
    )
    metric_card(
        draw,
        (580, 620, 960, 880),
        "Hermes delta",
        float(hermes["score_delta"]),
        MINT,
    )
    panel(draw, (1060, 590, 1760, 900))
    text(draw, (1108, 642), "What the test proves", F22, WHITE)
    lines = [
        "Base model cannot know local K-LIB records.",
        "K-LIB supplies compiled RDKit facts and citations.",
        "Hermes retrieves private facts through MCP.",
    ]
    for index, line in enumerate(lines):
        y = 710 + index * 58
        draw.ellipse((1110, y + 8, 1128, y + 26), fill=ACCENT)
        text(draw, (1150, y), line, F16)
    return image


def medchem_scene(progress: float, medchem: dict[str, Any], _: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "MEDCHEM WORKFLOW A/B")
    text(draw, (120, 190), "MedChem-KLIB Lite", F36, WHITE)
    text(draw, (120, 278), "Exact RDKit diagnostics beat generic model memory.", F18, TEXT)
    metric_card(
        draw,
        (120, 392, 520, 704),
        "Without K-LIB",
        float(medchem["baseline_average"]),
        RED,
    )
    metric_card(
        draw,
        (575, 392, 975, 704),
        "With K-LIB",
        float(medchem["klib_average"]),
        MINT,
    )
    x = 1070
    panel(draw, (x, 330, 1780, 810))
    text(draw, (x + 48, 384), "Passed workflow facts", F22, WHITE)
    rows = [
        ("Aspirin", "C9H8O4 · MW 180.16 · CHEM-W040"),
        ("Ibuprofen", "CMPD_000005 · undefined stereo · CHEM-W020"),
        ("Evidence suite", "8 checks · 100% · provenance + safety"),
        ("Aspirin evidence", "PTGS1/PTGS2 with citation markers"),
    ]
    for index, (label, value) in enumerate(rows):
        y = 460 + index * 78
        draw.rounded_rectangle((x + 48, y, x + 640, y + 54), radius=14, fill="#0d1217")
        text(draw, (x + 70, y + 13), label, F14, ACCENT)
        text(draw, (x + 240, y + 13), value, F14, TEXT)
    reveal = ease(progress)
    draw.rounded_rectangle((120, 800, 1780, 828), radius=14, fill="#252d35")
    draw.rounded_rectangle((120, 800, 120 + int(1660 * reveal), 828), radius=14, fill=ACCENT)
    text(draw, (120, 872), f"Score delta: +{float(medchem['score_delta']):.2f}", F28, MINT)
    return image


def hermes_scene(progress: float, _: dict[str, Any], hermes: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "HERMES AGENT MCP A/B")
    text(draw, (120, 190), "Hermes without tools vs with K-LIB MCP", F36, WHITE)
    text(
        draw,
        (120, 278),
        "Same question. One answer refuses to guess. One retrieves exact evidence.",
        F18,
    )
    metric_card(
        draw,
        (120, 380, 520, 692),
        "Without tools",
        float(hermes["baseline"]["score"]),
        RED,
    )
    metric_card(
        draw,
        (575, 380, 975, 692),
        "With K-LIB MCP",
        float(hermes["klib"]["score"]),
        MINT,
    )
    panel(draw, (1050, 330, 1780, 822))
    text(draw, (1098, 384), "Retrieved from biology-core-reference", F22, WHITE)
    facts = [
        "Primer ratio: 7.5 uL per 2.0 mL",
        "Readout: minute 11",
        "Abort: >34.2 C or ratio >2.10 before minute 4",
        "Source: 10-aster-9-internal-assay.md",
    ]
    for index, fact in enumerate(facts):
        y = 468 + index * 74
        draw.ellipse((1100, y + 7, 1122, y + 29), fill=MINT)
        text(draw, (1150, y), fact, F16)
    width = int(620 * ease(progress))
    draw.rounded_rectangle((1050, 878, 1050 + width, 910), radius=16, fill=ACCENT)
    text(draw, (1050, 938), f"Score delta: +{float(hermes['score_delta']):.2f}", F28, MINT)
    return image


def final_scene(_: float, medchem: dict[str, Any], hermes: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "RELEASE PROOF")
    text(draw, (130, 220), "K-LIB makes local knowledge testable.", F48, WHITE)
    text(draw, (130, 344), "Not a prompt trick. A reproducible package + eval workflow.", F22, TEXT)
    panel(draw, (130, 490, 1790, 820))
    rows = [
        ("Full tests", "46 passed · lint passed · desktop build passed"),
        ("MedChem A/B", f"{medchem['baseline_average']:.2f} -> {medchem['klib_average']:.2f}"),
        ("Hermes A/B", f"{hermes['baseline']['score']:.2f} -> {hermes['klib']['score']:.2f}"),
        ("Release asset", "short video + JSON/Markdown reports saved"),
    ]
    for index, (label, value) in enumerate(rows):
        y = 548 + index * 64
        text(draw, (180, y), label, F16, ACCENT)
        text(draw, (500, y), value, F16, TEXT)
    text(draw, (130, 918), "K-LIB Forge · MedChem-KLIB Lite · Hermes Agent MCP", F18, MUTED)
    return image


def frame_at(second: float, medchem: dict[str, Any], hermes: dict[str, Any]) -> Image.Image:
    scenes = [
        (0, 5, title_scene),
        (5, 12, medchem_scene),
        (12, 19, hermes_scene),
        (19, DURATION, final_scene),
    ]
    for start, end, scene in scenes:
        if start <= second < end:
            return scene((second - start) / max(end - start, 0.001), medchem, hermes)
    return final_scene(1.0, medchem, hermes)


def render(
    output: Path,
    thumbnail: Path,
    ffmpeg: Path,
    medchem_path: Path,
    hermes_path: Path,
) -> None:
    medchem = load_json(medchem_path)
    hermes = load_json(hermes_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    thumbnail.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_frame = frame_at(1.5, medchem, hermes)
    thumbnail_frame.save(thumbnail)

    command = [
        str(ffmpeg),
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:
        raise SystemExit("Could not open ffmpeg stdin.")
    total_frames = DURATION * FPS
    try:
        for frame_number in range(total_frames):
            second = frame_number / FPS
            frame = frame_at(second, medchem, hermes)
            draw = ImageDraw.Draw(frame)
            progress = int((WIDTH - 192) * (frame_number + 1) / total_frames)
            draw.rectangle((96, HEIGHT - 8, 96 + progress, HEIGHT - 4), fill=ACCENT)
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()
    return_code = process.wait()
    if return_code:
        raise SystemExit(f"ffmpeg failed with exit code {return_code}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a short MedChem and Hermes A/B test video."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--thumbnail", type=Path, default=DEFAULT_THUMBNAIL)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--medchem-report", type=Path, default=None)
    parser.add_argument("--hermes-report", type=Path, default=None)
    args = parser.parse_args()

    if not args.ffmpeg.exists():
        raise SystemExit(f"ffmpeg was not found at {args.ffmpeg}")
    medchem_report = args.medchem_report or latest_medchem_report()
    hermes_report = args.hermes_report or latest_hermes_report()
    render(
        args.output.resolve(),
        args.thumbnail.resolve(),
        args.ffmpeg.resolve(),
        medchem_report.resolve(),
        hermes_report.resolve(),
    )
    print(args.output.resolve())
    print(args.thumbnail.resolve())
    print(medchem_report.resolve())
    print(hermes_report.resolve())


if __name__ == "__main__":
    main()
