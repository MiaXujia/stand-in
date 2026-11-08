"""生成 PWA 图标（需要 Pillow）。用仓库自带的 python 跑：
    python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BG = (121, 87, 108, 255)
FG = (255, 250, 248, 255)


def make(size: int, path: Path) -> None:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), BG)
    draw = ImageDraw.Draw(image)
    petals = [
        (.42, .17, .58, .52),
        (.48, .42, .83, .58),
        (.42, .48, .58, .83),
        (.17, .42, .52, .58),
    ]
    for left, top, right, bottom in petals:
        draw.ellipse(
            [left * canvas, top * canvas, right * canvas, bottom * canvas],
            outline=FG,
            width=max(3, int(canvas * .013)),
        )
    radius = canvas * .026
    center = canvas / 2
    draw.ellipse([center - radius, center - radius, center + radius, center + radius], fill=FG)
    image.resize((size, size), Image.Resampling.LANCZOS).save(path)


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "web" / "public" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    make(192, out / "icon-192.png")
    make(512, out / "icon-512.png")
    print(f"icons -> {out}")


if __name__ == "__main__":
    main()
