from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 35

BG = "#0b0e11"
SURFACE = "#11161b"
SURFACE_2 = "#151b21"
LINE = "#252d35"
LINE_BRIGHT = "#3a4651"
TEXT = "#d7dde5"
WHITE = "#f0f2f4"
MUTED = "#7d8994"
ACCENT = "#dfaf4b"
MINT = "#8bc7b1"
DANGER = "#e47768"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "media" / "klib-forge-ab-tests.mp4"
DEFAULT_THUMBNAIL = (
    ROOT / "dist" / "media" / "klib-forge-ab-tests-thumbnail.png"
)
DEFAULT_FFMPEG = Path(r"D:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")

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


F10 = font(20, "mono")
F12 = font(24, "mono")
F14 = font(28, "regular")
F16 = font(32, "regular")
F18 = font(36, "semibold")
F20 = font(40, "semibold")
F24 = font(48, "semibold")
F28 = font(56, "bold")
F36 = font(72, "bold")
F48 = font(96, "bold")
F72 = font(144, "bold")


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def base_canvas() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), rgb(BG))
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 80):
        draw.line((x, 0, x, HEIGHT), fill="#0e1216", width=1)
    for y in range(0, HEIGHT, 80):
        draw.line((0, y, WIDTH, y), fill="#0e1216", width=1)
    draw.ellipse((1420, -360, 2260, 480), fill="#13150f")
    draw.ellipse((-440, 720, 340, 1500), fill="#0e1716")
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


def wrap(
    draw: ImageDraw.ImageDraw,
    value: str,
    face: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in value.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=face) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    face: ImageFont.FreeTypeFont,
    max_width: int,
    fill: str = TEXT,
    spacing: int = 12,
) -> int:
    x, y = xy
    lines = wrap(draw, value, face, max_width)
    line_height = face.getbbox("Ag")[3] - face.getbbox("Ag")[1]
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += line_height + spacing
    return y


def panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    outline: str = LINE,
    fill: str = SURFACE,
    radius: int = 12,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    color: str,
    face: ImageFont.FreeTypeFont = F10,
) -> int:
    x, y = xy
    bounds = draw.textbbox((0, 0), value, font=face)
    w = bounds[2] - bounds[0] + 30
    h = bounds[3] - bounds[1] + 20
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=5,
        fill=tuple((*rgb(color), 26)),
        outline=color,
        width=2,
    )
    text(draw, (x + 15, y + h // 2), value, face, color, anchor="lm")
    return w


def brand(
    draw: ImageDraw.ImageDraw,
    x: int = 96,
    y: int = 70,
    subtitle: str = "BIOLOGICAL A/B TEST",
) -> None:
    draw.polygon(
        [(x, y), (x + 52, y), (x + 68, y + 16), (x + 68, y + 68), (x, y + 68)],
        fill=ACCENT,
    )
    text(draw, (x + 34, y + 34), "K", F20, "#17130b", anchor="mm")
    text(draw, (x + 88, y + 7), "K-LIB Forge", F18, WHITE)
    text(draw, (x + 89, y + 49), subtitle, F10, MUTED)


def footer(draw: ImageDraw.ImageDraw, active: int) -> None:
    y = HEIGHT - 58
    draw.line((96, y, WIDTH - 96, y), fill=LINE, width=2)
    labels = [
        "BIO QUESTION",
        "BIO NO K-LIB",
        "BIO + K-LIB",
        "BIO RESULT",
        "MATH TEST",
        "MATH RESULT",
        "LIMIT",
        "K-LIB FORGE",
    ]
    segment = (WIDTH - 192) / len(labels)
    for index, label in enumerate(labels):
        x = int(96 + segment * index)
        color = ACCENT if index == active else "#4c5660"
        text(draw, (x, y + 20), f"0{index + 1} {label}", F10, color)


def scene_intro() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw)
    text(draw, (96, 300), "SAME MODEL.", F72, WHITE)
    text(draw, (96, 462), "DIFFERENT EVIDENCE.", F72, ACCENT)
    text(
        draw,
        (100, 655),
        "NVIDIA MiniMax M3  /  temperature 0  /  primary-literature biology",
        F16,
        MUTED,
    )
    x = 100
    x += pill(draw, (x, 735), "CONTROLLED A/B", MINT, F12) + 18
    x += pill(draw, (x, 735), "SAME QUESTIONS", ACCENT, F12) + 18
    pill(draw, (x, 735), "KEYS SWAPPED", ACCENT, F12)
    footer(draw, 0)
    return image


def scene_question() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw)
    text(draw, (96, 215), "THE QUESTION", F12, ACCENT)
    text(
        draw,
        (96, 266),
        "What changed when DL lipids",
        F48,
        WHITE,
    )
    text(draw, (96, 378), "increased by 20%?", F48, WHITE)
    panel(draw, (96, 545, 1824, 845), outline=LINE_BRIGHT, fill="#0f1418")
    text(draw, (134, 584), "PRIMARY-STUDY TARGETS", F10, MUTED)
    targets = [
        ("01", "Lipid composition"),
        ("02", "Free-energy shift"),
        ("03", "Dissociation constant"),
        ("04", "Numeric citation"),
    ]
    for index, (number, label) in enumerate(targets):
        x = 134 + index * 410
        text(draw, (x, 665), number, F14, ACCENT)
        text(draw, (x + 52, 665), label, F14, TEXT)
        draw.line((x, 725, x + 330, 725), fill=LINE, width=2)
    text(
        draw,
        (134, 785),
        "Nature Chemical Biology (2025)  /  DOI 10.1038/s41589-025-02032-w",
        F12,
        MUTED,
    )
    footer(draw, 0)
    return image


def scene_without() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw)
    text(draw, (96, 210), "WITHOUT K-LIB", F12, DANGER)
    text(draw, (96, 262), "The model has no study evidence.", F36, WHITE)
    panel(draw, (96, 390, 1500, 820), outline="#553238", fill="#121316")
    text(draw, (138, 432), "MINIMAX M3", F10, MUTED)
    baseline = (
        '"I don\'t have the specific CLC-ec1 study in my training data, '
        'so I can\'t give the exact lipid composition, free-energy change, '
        'or dissociation constant shift..."'
    )
    multiline(draw, (138, 505), baseline, F20, 1285, fill=TEXT, spacing=20)
    panel(draw, (1540, 390, 1824, 820), outline=DANGER, fill="#171215")
    text(draw, (1682, 470), "SCORE", F12, MUTED, anchor="mm")
    text(draw, (1682, 610), "0%", F72, DANGER, anchor="mm")
    text(draw, (1682, 735), "0 / 6 checks", F12, DANGER, anchor="mm")
    footer(draw, 1)
    return image


def scene_with() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw)
    text(draw, (96, 210), "WITH K-LIB", F12, MINT)
    text(draw, (96, 262), "Retrieved evidence makes the answer exact.", F36, WHITE)
    panel(draw, (96, 390, 1500, 820), outline="#36524c", fill="#101716")
    text(draw, (138, 432), "GROUNDED ANSWER", F10, MINT)
    entries = [
        ("+20%", "DL lipids"),
        ("~2.5 kcal/mol", "net solvation free-energy shift"),
        ("~70-fold", "change in dimer dissociation constant"),
    ]
    y = 505
    for value, label in entries:
        text(draw, (138, y), value, F28, ACCENT)
        text(draw, (510, y + 10), label, F16, TEXT)
        y += 92
    text(
        draw,
        (138, 770),
        "[1] Nature Chemical Biology (2025)  /  DOI 10.1038/s41589-025-02032-w",
        F12,
        MUTED,
    )
    panel(draw, (1540, 390, 1824, 820), outline=MINT, fill="#101716")
    text(draw, (1682, 470), "SCORE", F12, MUTED, anchor="mm")
    text(draw, (1682, 610), "100%", F48, MINT, anchor="mm")
    text(draw, (1682, 735), "6 / 6 checks", F12, MINT, anchor="mm")
    footer(draw, 2)
    return image


def score_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    baseline: str,
    klib: str,
) -> None:
    x1, y1, x2, y2 = box
    panel(draw, box, outline=LINE_BRIGHT, fill=SURFACE)
    text(draw, (x1 + 34, y1 + 34), title, F12, MUTED)
    text(draw, (x1 + 34, y1 + 105), baseline, F48, DANGER)
    text(draw, (x1 + 34, y1 + 225), "BASELINE", F10, DANGER)
    draw.line((x1 + 275, y1 + 70, x1 + 275, y2 - 50), fill=LINE, width=2)
    text(draw, (x1 + 320, y1 + 105), klib, F48, MINT)
    text(draw, (x1 + 320, y1 + 225), "WITH K-LIB", F10, MINT)


def scene_crossover() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw)
    text(draw, (96, 205), "CROSSOVER VERIFIED", F12, ACCENT)
    text(draw, (96, 258), "The result held when key assignments swapped.", F36, WHITE)
    score_card(draw, (96, 410, 916, 750), "ASSIGNMENT A / B", "8%", "100%")
    score_card(draw, (1004, 410, 1824, 750), "ASSIGNMENT B / A", "4%", "100%")
    text(
        draw,
        (960, 835),
        "5 held-out primary-literature questions  /  same model  /  same settings",
        F14,
        MUTED,
        anchor="mm",
    )
    footer(draw, 3)
    return image


def scene_math_intro() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw, subtitle="LOCAL MATH A/B TEST")
    text(draw, (96, 275), "NEXT TEST:", F12, ACCENT)
    text(draw, (96, 330), "GEMMA 4.  LOCAL OLLAMA.", F48, WHITE)
    text(draw, (96, 455), "WITHOUT K-LIB  vs  WITH K-LIB", F36, ACCENT)
    text(
        draw,
        (100, 625),
        "gemma4:e4b  /  8B Q4_K_M  /  temperature 0  /  five math tasks",
        F16,
        MUTED,
    )
    x = 100
    x += pill(draw, (x, 710), "FULLY LOCAL", MINT, F12) + 18
    x += pill(draw, (x, 710), "SAME MODEL", ACCENT, F12) + 18
    pill(draw, (x, 710), "SAME SETTINGS", ACCENT, F12)
    footer(draw, 4)
    return image


def scene_math_results() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw, subtitle="LOCAL MATH A/B TEST")
    text(draw, (96, 205), "GEMMA 4 MATH RESULT", F12, ACCENT)
    text(draw, (96, 258), "Grounded specifications changed the result.", F36, WHITE)

    panel(draw, (96, 405, 860, 790), outline="#553238", fill="#171215")
    text(draw, (140, 450), "WITHOUT K-LIB", F12, DANGER)
    text(draw, (140, 535), "20.00%", F72, DANGER)
    text(draw, (140, 700), "Only the ordinary algebra control passed.", F14, MUTED)

    panel(draw, (960, 405, 1824, 790), outline=MINT, fill="#101716")
    text(draw, (1004, 450), "WITH K-LIB", F12, MINT)
    text(draw, (1004, 535), "93.33%", F72, MINT)
    text(draw, (1004, 700), "+73.33 percentage points", F14, MINT)

    text(
        draw,
        (960, 865),
        "4 fictional specification tasks + 1 ordinary algebra control",
        F14,
        MUTED,
        anchor="mm",
    )
    footer(draw, 5)
    return image


def scene_math_detail() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw, subtitle="LOCAL MATH A/B TEST")
    text(draw, (96, 205), "WHAT THE SCORE MEANS", F12, ACCENT)
    text(draw, (96, 258), "Retrieval succeeded. One calculation still slipped.", F36, WHITE)

    panel(draw, (96, 400, 1165, 815), outline="#36524c", fill="#101716")
    text(draw, (138, 440), "WITH K-LIB TASK SCORES", F10, MINT)
    rows = [
        ("Aster yield", "100%"),
        ("Nemor thermal load", "100%"),
        ("Velar distance", "100%"),
        ("Algebra control", "100%"),
    ]
    y = 505
    for label, value in rows:
        text(draw, (138, y), label, F16, TEXT)
        text(draw, (1085, y), value, F18, MINT, anchor="ra")
        draw.line((138, y + 54, 1085, y + 54), fill=LINE, width=2)
        y += 72

    panel(draw, (1210, 400, 1824, 815), outline=DANGER, fill="#171215")
    text(draw, (1252, 440), "QUENBY RECURRENCE", F10, DANGER)
    text(draw, (1252, 515), "66.67%", F48, DANGER)
    multiline(
        draw,
        (1252, 645),
        "Formula and citation were correct. Gemma returned 88.87; expected 87.87.",
        F14,
        510,
        fill=TEXT,
        spacing=12,
    )
    footer(draw, 6)
    return image


def scene_outro() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    brand(draw, 826, 120, "BIOLOGY + MATH A/B TESTS")
    text(draw, (960, 285), "TWO MODELS. TWO DOMAINS.", F36, WHITE, anchor="mm")
    text(draw, (960, 385), "ONE PORTABLE KNOWLEDGE LAYER.", F36, ACCENT, anchor="mm")

    panel(draw, (335, 500, 930, 690), outline=LINE_BRIGHT, fill=SURFACE)
    text(draw, (375, 535), "MINIMAX M3 / BIOLOGY", F10, MUTED)
    text(draw, (375, 595), "8% / 4%  →  100%", F24, MINT)
    panel(draw, (990, 500, 1585, 690), outline=LINE_BRIGHT, fill=SURFACE)
    text(draw, (1030, 535), "GEMMA 4 / MATH", F10, MUTED)
    text(draw, (1030, 595), "20.00%  →  93.33%", F24, MINT)

    text(
        draw,
        (960, 750),
        "Build once. Run on local or online models.",
        F14,
        MUTED,
        anchor="mm",
    )
    pill_width = 720
    panel(
        draw,
        (960 - pill_width // 2, 805, 960 + pill_width // 2, 875),
        outline="#8bc7b166",
        fill="#101716",
        radius=6,
    )
    text(
        draw,
        (960, 840),
        "github.com/punksinger94-blip/klib-forge",
        F14,
        MINT,
        anchor="mm",
    )
    footer(draw, 7)
    return image


def render(
    output: Path,
    thumbnail: Path,
    ffmpeg: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    thumbnail.parent.mkdir(parents=True, exist_ok=True)

    scenes = [
        scene_intro(),
        scene_question(),
        scene_without(),
        scene_with(),
        scene_crossover(),
        scene_math_intro(),
        scene_math_results(),
        scene_math_detail(),
        scene_outro(),
    ]
    scene_starts = [0.0, 2.5, 5.4, 9.2, 13.2, 17.2, 20.4, 24.8, 29.4]
    transition = 0.65

    scenes[6].save(thumbnail, quality=95)

    command = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
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
        "-preset",
        "medium",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    total_frames = DURATION * FPS
    try:
        for frame_number in range(total_frames):
            seconds = frame_number / FPS
            scene_index = max(
                index
                for index, start in enumerate(scene_starts)
                if seconds >= start
            )
            frame = scenes[scene_index].copy()
            if scene_index + 1 < len(scenes):
                next_start = scene_starts[scene_index + 1]
                if seconds >= next_start - transition:
                    amount = ease((seconds - (next_start - transition)) / transition)
                    frame = Image.blend(frame, scenes[scene_index + 1], amount)

            draw = ImageDraw.Draw(frame)
            progress = int((WIDTH - 192) * (frame_number + 1) / total_frames)
            draw.rectangle(
                (96, HEIGHT - 7, 96 + progress, HEIGHT - 3),
                fill=ACCENT,
            )
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()

    return_code = process.wait()
    if return_code:
        raise SystemExit(f"ffmpeg failed with exit code {return_code}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the K-LIB Forge biology and math A/B comparison video."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--thumbnail", type=Path, default=DEFAULT_THUMBNAIL)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    args = parser.parse_args()

    if not args.ffmpeg.exists():
        raise SystemExit(f"ffmpeg was not found at {args.ffmpeg}")
    render(args.output.resolve(), args.thumbnail.resolve(), args.ffmpeg.resolve())
    print(args.output.resolve())
    print(args.thumbnail.resolve())


if __name__ == "__main__":
    main()
