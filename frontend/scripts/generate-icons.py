"""Génère les icônes PWA de la maquette à partir d'un motif simple."""

from pathlib import Path

from PIL import Image, ImageDraw

PURPLE = (118, 82, 165, 255)
PURPLE_DARK = (96, 65, 138, 255)
WHITE = (255, 255, 255, 255)
OUTPUT = Path(__file__).resolve().parent.parent / "public"


def draw_icon(size: int, padding_ratio: float = 0.0) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = int(size * 0.22)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=PURPLE,
    )

    padding = int(size * padding_ratio)
    left = int(size * 0.18) + padding
    right = int(size * 0.82) - padding
    top = int(size * 0.30) + padding
    bottom = int(size * 0.70) - padding
    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=int(size * 0.07),
        fill=WHITE,
    )
    draw.rounded_rectangle(
        (left, top, right, int(top + size * 0.12)),
        radius=int(size * 0.04),
        fill=PURPLE_DARK,
    )
    draw.ellipse(
        (
            int(size * 0.62),
            int(size * 0.45),
            int(size * 0.72),
            int(size * 0.55),
        ),
        fill=PURPLE_DARK,
    )
    return image


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192).save(OUTPUT / "pwa-192x192.png")
    draw_icon(512).save(OUTPUT / "pwa-512x512.png")
    draw_icon(512, padding_ratio=0.12).save(OUTPUT / "maskable-512x512.png")
    draw_icon(180).save(OUTPUT / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
