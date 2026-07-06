import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# PFADE ANPASSEN
SOURCE_DIR = "./test_originale"
TARGET_DIR = "./test_vorschau_degraded"

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
TEXT = "VORSCHAU"
ROTATION_DEG = 30
ALPHA = 230         # 0-255, Sichtbarkeit des Textes
FONT_WIDTH_RATIO = 0.06   # Schriftgröße relativ zur Bildbreite
TILE_MARGIN = 1.1        # Abstand zwischen den Wiederholungen (>1.0)
MAX_DIMENSION = 1200     # Vorschau-Bilder werden auf diese lange Kante herunterskaliert
JPEG_QUALITY = 40        # Niedrige Qualität erschwert eine spätere Restaurierung zusätzlich
BLUR_RADIUS = 3          # Zusätzliche Unschärfe auf dem Foto selbst (nicht nur das Wasserzeichen)


def build_tile(width):
    font_size = max(8, int(width * FONT_WIDTH_RATIO))
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except IOError:
        font = ImageFont.load_default()

    # Textgröße VOR der Kachel-Erstellung messen, damit die Kachel
    # groß genug ist, um den Text (auch nach der Rotation) vollständig
    # aufzunehmen - sonst wird er an den Kachelrändern abgeschnitten.
    stroke_width = max(1, font_size // 20)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), TEXT, font=font, stroke_width=stroke_width)
    t_width, t_height = box[2] - box[0], box[3] - box[1]

    rad = math.radians(ROTATION_DEG)
    rotated_w = abs(t_width * math.cos(rad)) + abs(t_height * math.sin(rad))
    rotated_h = abs(t_width * math.sin(rad)) + abs(t_height * math.cos(rad))
    tile_size = int(max(rotated_w, rotated_h) * TILE_MARGIN)

    tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    d_tile = ImageDraw.Draw(tile)
    tx = (tile_size - t_width) // 2 - box[0]
    ty = (tile_size - t_height) // 2 - box[1]
    # Schwarzer Rand, damit der Text auf hellem UND dunklem Untergrund sichtbar bleibt.
    outline_alpha = int(ALPHA * 0.9)
    stroke_width = max(1, font_size // 20)
    d_tile.text((tx, ty), TEXT, fill=(255, 255, 255, ALPHA), font=font,
                stroke_width=stroke_width, stroke_fill=(0, 0, 0, outline_alpha))

    return tile.rotate(ROTATION_DEG, resample=Image.BICUBIC), tile_size


def add_tiled_watermark():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    for filename in os.listdir(SOURCE_DIR):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            print(f"Verarbeite: {filename}")

            img = Image.open(os.path.join(SOURCE_DIR, filename)).convert("RGBA")

            # Vorschau vor dem Wasserzeichen verkleinern: reduziert dauerhaft die
            # Detailtiefe, sodass eine KI-Restaurierung kein hochauflösendes
            # Ausgangsmaterial mehr vorfindet (das Kachelmuster allein reicht nicht).
            if max(img.size) > MAX_DIMENSION:
                scale = MAX_DIMENSION / max(img.size)
                img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

            # Foto selbst weichzeichnen - nicht nur das Wasserzeichen. Das nimmt
            # dem Bild dauerhaft Detail (v.a. Gesichter), unabhängig vom Muster.
            img = img.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))

            width, height = img.size

            tile, tile_size = build_tile(width)

            # Das Overlay-Bild lückenlos im Kachelmuster füllen - der Bereich
            # deckt das gesamte Bild ab (inkl. angeschnittener Randkacheln).
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            for x in range(0, width, tile_size):
                for y in range(0, height, tile_size):
                    overlay.paste(tile, (x, y), tile)

            watermarked = Image.alpha_composite(img, overlay)

            final_img = watermarked.convert("RGB")
            target_path = os.path.join(TARGET_DIR, filename)
            final_img.save(target_path, "JPEG", quality=JPEG_QUALITY)

            print(f"Erstellt: {target_path}")


if __name__ == "__main__":
    add_tiled_watermark()
