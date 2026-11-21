from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SVG_PATH = Path(__file__).with_name("start.svg")
FONT_PATH = ROOT / "branding" / "fonts" / "PressStart2P.ttf"
OUTPUT_PATH = ROOT / "assets" / "banners" / "start.png"
PREVIEW_PATH = Path(__file__).with_name("previews") / "start-400.png"
EXPECTED_COLORS = {(0, 0, 0), (200, 252, 40), (249, 249, 251)}


def parse_number(value: str) -> int:
    return int(float(value))


def render() -> Image.Image:
    root = ET.parse(SVG_PATH).getroot()
    width = parse_number(root.attrib["width"])
    height = parse_number(root.attrib["height"])
    image = Image.new("RGB", (width, height), "#000000")
    draw = ImageDraw.Draw(image)

    icon = root.find("{http://www.w3.org/2000/svg}g[@id='icon']")
    if icon is None:
        raise ValueError("SVG must contain an icon group")
    transform = icon.attrib["transform"].removeprefix("translate(").removesuffix(")")
    offset_x, offset_y = (int(part) for part in transform.split())
    for rect in icon.findall("{http://www.w3.org/2000/svg}rect"):
        x = offset_x + parse_number(rect.attrib["x"])
        y = offset_y + parse_number(rect.attrib["y"])
        rect_width = parse_number(rect.attrib["width"])
        rect_height = parse_number(rect.attrib["height"])
        draw.rectangle((x, y, x + rect_width - 1, y + rect_height - 1), fill="#C8FC28")

    text = root.find("{http://www.w3.org/2000/svg}text")
    if text is None or text.text is None:
        raise ValueError("SVG must contain a wordmark")
    font = ImageFont.truetype(FONT_PATH, parse_number(text.attrib["font-size"]))
    text_x = parse_number(text.attrib["x"])
    bbox = draw.textbbox((0, 0), text.text, font=font)
    text_y = (height - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((text_x, text_y), text.text, font=font, fill="#F9F9FB")
    return image


def main() -> None:
    image = render()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_PATH, optimize=True)
    image.resize((400, 117), Image.Resampling.NEAREST).save(PREVIEW_PATH, optimize=True)

    colors = {color for _, color in image.getcolors(maxcolors=16) or []}
    if image.size != (2000, 586):
        raise SystemExit(f"unexpected size: {image.size}")
    if colors != EXPECTED_COLORS:
        raise SystemExit(f"unexpected palette: {sorted(colors)}")
    print(f"OK {OUTPUT_PATH}: {image.size}, colors={sorted(colors)}")


if __name__ == "__main__":
    sys.exit(main())
