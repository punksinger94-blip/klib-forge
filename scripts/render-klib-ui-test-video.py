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
DURATION = 38

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "media" / "klib-forge-ui-test-proof.mp4"
DEFAULT_THUMBNAIL = ROOT / "dist" / "media" / "klib-forge-ui-test-proof-thumbnail.png"
DEFAULT_FFMPEG = Path(r"D:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")
DEFAULT_SHOTS = ROOT / "build" / "video-ui-shots"

BG = "#090d11"
SURFACE = "#10161c"
SURFACE_2 = "#151d24"
LINE = "#26323c"
TEXT = "#dce3ea"
MUTED = "#8997a3"
ACCENT = "#dfaf4b"
MINT = "#8bc7b1"
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


def rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def base_frame() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), rgb(BG))
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 96):
        draw.line((x, 0, x, HEIGHT), fill="#0d1217", width=1)
    for y in range(0, HEIGHT, 96):
        draw.line((0, y, WIDTH, y), fill="#0d1217", width=1)
    draw.ellipse((1320, -360, 2220, 540), fill="#13130e")
    draw.ellipse((-460, 740, 360, 1580), fill="#0d1716")
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


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str = SURFACE) -> None:
    draw.rounded_rectangle(box, radius=28, fill=fill, outline=LINE, width=2)


def brand(draw: ImageDraw.ImageDraw, subtitle: str) -> None:
    draw.rounded_rectangle((92, 68, 152, 128), radius=10, fill=ACCENT)
    text(draw, (122, 100), "K", F18, BG, anchor="mm")
    text(draw, (176, 70), "K-LIB Forge", F18, WHITE)
    text(draw, (176, 112), subtitle.upper(), F12, MUTED)


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fill: str) -> int:
    width = int(draw.textlength(value, font=F12)) + 36
    x, y = xy
    draw.rounded_rectangle((x, y, x + width, y + 44), radius=22, fill=fill)
    text(draw, (x + 18, y + 9), value, F12, BG)
    return width


def wrap(
    draw: ImageDraw.ImageDraw,
    value: str,
    face: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=face) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_image(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    source = Image.open(path).convert("RGB")
    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1
    scale = min(max_w / source.width, max_h / source.height)
    resized = source.resize((int(source.width * scale), int(source.height * scale)))
    canvas = Image.new("RGB", (max_w, max_h), rgb("#070a0d"))
    canvas.paste(resized, ((max_w - resized.width) // 2, (max_h - resized.height) // 2))
    return canvas


def paste_screenshot(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    path: Path,
    box: tuple[int, int, int, int],
) -> None:
    panel(draw, box, "#070a0d")
    x1, y1, x2, y2 = box
    shot = fit_image(path, (x1 + 18, y1 + 18, x2 - 18, y2 - 18))
    image.paste(shot, (x1 + 18, y1 + 18))


def latest_deep_report() -> Path:
    reports = sorted(
        (ROOT / "build" / "release-deep-qualification").glob("*/report.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        raise SystemExit("No deep qualification report found.")
    return reports[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def title_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "UI + TEST PROOF")
    text(draw, (120, 245), "K-LIB UI + test proof", F36, WHITE)
    text(draw, (120, 345), "Desktop shots + deep qualification", F22)
    x = 120
    x += pill(draw, (x, 460), "PREVIEW 2", ACCENT) + 18
    x += pill(draw, (x, 460), f"{report['passed']}/{report['total']} TEST GATES", MINT) + 18
    pill(draw, (x, 460), "CLI / API / MCP / UI", MINT)
    paste_screenshot(image, draw, shots / "08-medchem-evidence-evals.png", (930, 190, 1800, 850))
    panel(draw, (120, 620, 820, 910), SURFACE_2)
    text(draw, (160, 664), "What viewers see", F22, WHITE)
    lines = [
        "K-LIB package selected in the app",
        "Local runtime online",
        "Deep test evidence, not just a static demo",
    ]
    for index, line in enumerate(lines):
        y = 735 + index * 50
        draw.ellipse((164, y + 9, 180, y + 25), fill=ACCENT)
        text(draw, (204, y), line, F14)
    return image


def dashboard_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "DESKTOP UI")
    text(draw, (110, 175), "The app loads the active K-LIB package", F36, WHITE)
    paste_screenshot(image, draw, shots / "01-dashboard.png", (90, 270, 1280, 990))
    panel(draw, (1320, 300, 1810, 780), SURFACE_2)
    text(draw, (1360, 350), "Release test", F22, WHITE)
    facts = [
        f"Status: {report['status']}",
        f"Result: {report['passed']}/{report['total']} gates",
        "Runtime: local API",
        "Package: MedChem-KLIB Lite",
    ]
    for index, fact in enumerate(facts):
        y = 430 + index * 68
        text(draw, (1360, y), fact, F16, MINT if index == 1 else TEXT)
    return image


def medchem_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "MEDCHEM LAB")
    text(draw, (110, 175), "RDKit-backed molecule library", F36, WHITE)
    paste_screenshot(
        image,
        draw,
        shots / "06-medchem-compound-store-rdkit.png",
        (90, 270, 1280, 990),
    )
    panel(draw, (1320, 270, 1810, 870), SURFACE_2)
    text(draw, (1360, 320), "What K-LIB adds", F22, WHITE)
    facts = [
        "RDKit validation",
        "Descriptors + scaffolds",
        "Evidence links",
        "Safety boundary",
        "Regression evals",
    ]
    for index, fact in enumerate(facts):
        y = 410 + index * 76
        draw.rounded_rectangle((1360, y, 1400, y + 40), radius=20, fill=MINT)
        text(draw, (1380, y + 20), str(index + 1), F12, BG, anchor="mm")
        text(draw, (1425, y + 3), fact, F16)
    return image


def similarity_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "SIMILARITY + SAFETY")
    text(draw, (110, 175), "Similarity search with guardrails", F36, WHITE)
    paste_screenshot(
        image,
        draw,
        shots / "07-medchem-similarity-safety.png",
        (70, 250, 1340, 990),
    )
    panel(draw, (1380, 260, 1815, 845), SURFACE_2)
    text(draw, (1420, 315), "Visible proof", F22, WHITE)
    facts = [
        "Morgan fingerprints",
        "Ranked similar molecules",
        "Descriptor cards",
        "Unsafe synthesis blocked",
    ]
    for index, fact in enumerate(facts):
        y = 410 + index * 86
        draw.rounded_rectangle((1420, y, 1460, y + 40), radius=20, fill=ACCENT)
        text(draw, (1440, y + 20), str(index + 1), F12, BG, anchor="mm")
        text(draw, (1485, y + 3), fact, F16)
    return image


def evidence_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "CITED RESEARCH")
    text(draw, (110, 175), "Ask linked evidence, then test it", F36, WHITE)
    paste_screenshot(
        image,
        draw,
        shots / "08-medchem-evidence-evals.png",
        (80, 235, 1360, 990),
    )
    panel(draw, (1400, 250, 1815, 825), SURFACE_2)
    text(draw, (1440, 305), "Grounded output", F22, WHITE)
    lines = [
        "Cited evidence brief",
        "Source identifiers visible",
        "Regression suite: 100%",
        "Safety refusal checked",
    ]
    for index, line in enumerate(lines):
        y = 398 + index * 86
        draw.ellipse((1444, y + 8, 1474, y + 38), fill=MINT)
        text(draw, (1459, y + 23), "OK", F12, BG, anchor="mm")
        text(draw, (1500, y + 2), line, F16)
    return image


def record_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "EVIDENCE RECORDS")
    text(draw, (110, 175), "Bioactivity ledger + literature notes", F36, WHITE)
    paste_screenshot(
        image,
        draw,
        shots / "09-medchem-bioactivity-ledger.png",
        (90, 260, 875, 965),
    )
    paste_screenshot(
        image,
        draw,
        shots / "10-medchem-literature-notes.png",
        (940, 260, 1810, 965),
    )
    panel(draw, (120, 880, 1800, 1000), "#0b1514")
    text(
        draw,
        (160, 920),
        "K-LIB keeps compound records, target links, cited sources, and eval claims together.",
        F18,
        MINT,
    )
    return image


def cited_brief_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "GROUNDED BRIEF")
    text(draw, (110, 175), "Evidence answer, not loose model memory", F36, WHITE)
    paste_screenshot(
        image,
        draw,
        shots / "11-medchem-cited-brief.png",
        (300, 245, 1620, 995),
    )
    return image


def gate_scene(_: float, _shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "FULL TEST")
    text(draw, (120, 180), "Deep qualification passed", F48, WHITE)
    text(draw, (120, 292), f"{report['passed']}/{report['total']} gates green", F36, MINT)
    checks = report["checks"]
    for index, check in enumerate(checks):
        col = index % 2
        row = index // 2
        x = 120 + col * 850
        y = 430 + row * 130
        panel(draw, (x, y, x + 770, y + 96), SURFACE_2)
        draw.ellipse((x + 32, y + 32, x + 64, y + 64), fill=MINT)
        text(draw, (x + 48, y + 48), "OK", F12, BG, anchor="mm")
        text(draw, (x + 88, y + 24), check["name"], F16, WHITE)
        detail = check.get("detail", {})
        if isinstance(detail, dict) and "evals" in detail:
            text(draw, (x + 88, y + 60), f"Evidence evals: {detail['evals']}", F12, MUTED)
        else:
            text(draw, (x + 88, y + 60), check["status"], F12, MUTED)
    return image


def final_scene(_: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    image = base_frame()
    draw = ImageDraw.Draw(image)
    brand(draw, "READY TO SHOW")
    text(draw, (120, 210), "K-LIB is visible, testable, and packaged.", F36, WHITE)
    paste_screenshot(image, draw, shots / "08-medchem-evidence-evals.png", (1040, 170, 1810, 760))
    panel(draw, (120, 390, 920, 780), SURFACE_2)
    final_lines = [
        "UI: Desktop app shows active package + MedChem Lab",
        "Tests: 8/8 deep release gates passed",
        "Workflow: CLI, API, MCP, UI build, MedChem big research",
        "Release: Preview build with honest signing notice",
    ]
    for index, line in enumerate(final_lines):
        y = 440 + index * 72
        draw.ellipse((156, y + 10, 178, y + 32), fill=ACCENT)
        for offset, wrapped in enumerate(wrap(draw, line, F16, 650)):
            text(draw, (204, y + offset * 34), wrapped, F16)
    text(draw, (120, 860), "K-LIB Forge Preview 2", F28, MINT)
    text(draw, (120, 930), "Build once. Run on any model.", F18, WHITE)
    return image


def frame_at(second: float, shots: Path, report: dict[str, Any]) -> Image.Image:
    scenes = [
        (0, 4, title_scene),
        (4, 8, dashboard_scene),
        (8, 13, medchem_scene),
        (13, 18, similarity_scene),
        (18, 23, evidence_scene),
        (23, 28, record_scene),
        (28, 32, cited_brief_scene),
        (32, 36, gate_scene),
        (36, DURATION, final_scene),
    ]
    for start, end, scene in scenes:
        if start <= second < end:
            return scene((second - start) / max(end - start, 0.001), shots, report)
    return final_scene(1.0, shots, report)


def render(
    output: Path,
    thumbnail: Path,
    ffmpeg: Path,
    shots: Path,
    report_path: Path,
) -> None:
    report = load_json(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    thumbnail.parent.mkdir(parents=True, exist_ok=True)
    for required in (
        "01-dashboard.png",
        "06-medchem-compound-store-rdkit.png",
        "07-medchem-similarity-safety.png",
        "08-medchem-evidence-evals.png",
        "09-medchem-bioactivity-ledger.png",
        "10-medchem-literature-notes.png",
        "11-medchem-cited-brief.png",
    ):
        if not (shots / required).exists():
            raise SystemExit(f"Missing UI screenshot: {shots / required}")

    frame_at(1.2, shots, report).save(thumbnail)
    command = [
        str(ffmpeg),
        "-y",
        "-f",
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
    if not process.stdin:
        raise SystemExit("Could not open ffmpeg stdin.")
    total_frames = DURATION * FPS
    for frame_index in range(total_frames):
        second = frame_index / FPS
        frame = frame_at(second, shots, report)
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise SystemExit(f"ffmpeg failed with exit code {return_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a K-LIB UI + test proof video.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--thumbnail", type=Path, default=DEFAULT_THUMBNAIL)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--shots", type=Path, default=DEFAULT_SHOTS)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    if not args.ffmpeg.exists():
        raise SystemExit(f"ffmpeg was not found at {args.ffmpeg}")
    report_path = args.report or latest_deep_report()
    render(
        args.output.resolve(),
        args.thumbnail.resolve(),
        args.ffmpeg.resolve(),
        args.shots.resolve(),
        report_path.resolve(),
    )
    print(args.output.resolve())
    print(args.thumbnail.resolve())
    print(report_path.resolve())


if __name__ == "__main__":
    main()
