"""
Photobooth (headless) - arcade button triggers countdown, capture, and thermal print.
No display or touchscreen required.
"""
import time
import math
import urllib.request
from pathlib import Path
from datetime import datetime

from picamera2 import Picamera2
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button
from escpos.printer import File as EscposFile

# --- Configuration ---
CAMERA_RES = (800, 480)
CAPTURE_RES = (1920, 1080)
COUNTDOWN_SECONDS = 3
PRINTER_DEVICE = "/dev/usb/lp0"
PRINTER_WIDTH = 384
PADDING = 16
BUTTON_PIN = 17
DEBOUNCE = 1.0

PHOTOS_DIR = Path.home() / "photobooth" / "captures"
FONTS_DIR = Path.home() / "photobooth"


# --- Fonts ---
def get_fonts():
    font_path = FONTS_DIR / "SpaceMono-Regular.ttf"
    font_bold_path = FONTS_DIR / "SpaceMono-Bold.ttf"
    if not font_path.exists():
        urllib.request.urlretrieve(
            "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Regular.ttf",
            str(font_path)
        )
    if not font_bold_path.exists():
        urllib.request.urlretrieve(
            "https://github.com/google/fonts/raw/main/ofl/spacemono/SpaceMono-Bold.ttf",
            str(font_bold_path)
        )
    return (
        ImageFont.truetype(str(font_bold_path), 20),
        ImageFont.truetype(str(font_path), 16),
        ImageFont.truetype(str(font_path), 13),
    )


# --- Star header ---
def star_polygon(cx, cy, r_outer, r_inner, points=5, angle_offset=0):
    coords = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2 + math.radians(angle_offset)
        r = r_outer if i % 2 == 0 else r_inner
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return coords


def point_in_polygon(x, y, polygon):
    n, inside, px, py = len(polygon), False, x, y
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_near_edge(x, y, polygon, threshold=4):
    min_dist = float('inf')
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            continue
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (length * length)))
        dist = math.sqrt((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2)
        min_dist = min(min_dist, dist)
    return min_dist <= threshold


def draw_dotted_star(draw, cx, cy, r_outer, r_inner, points=5, dot_spacing=4,
                     dot_r=1, angle_offset=0, filled=True, edge_thickness=5):
    poly = star_polygon(cx, cy, r_outer, r_inner, points, angle_offset)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1 = int(min(xs)) - 2, int(max(xs)) + 2
    y0, y1 = int(min(ys)) - 2, int(max(ys)) + 2
    for y in range(y0, y1, dot_spacing):
        for x in range(x0, x1, dot_spacing):
            if point_in_polygon(x, y, poly):
                if filled or point_near_edge(x, y, poly, edge_thickness):
                    draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=0)


def make_star_header():
    h_img = Image.new("L", (PRINTER_WIDTH, 160), color=255)
    d = ImageDraw.Draw(h_img)
    stars = [
        (55,  90,  55, 26, -15, True,  4, 1),
        (298, 72,  44, 22,  10, False, 4, 1),
        (148, 32,  32, 15,  22, False, 4, 1),
        (218, 38,  22, 10,  15, True,  3, 1),
        (192, 118, 25, 11,   7, False, 3, 1),
        (255, 130, 28, 13, -10, True,  4, 1),
        (105, 145, 18,  8,  35, True,  3, 1),
        (355, 140, 18,  8,  -5, True,  3, 1),
        (135, 75,  12,  5,  18, True,  3, 1),
        (78,  28,  16,  7,   0, False, 3, 1),
        (348, 28,  16,  7,   0, True,  3, 1),
    ]
    for cx, cy, ro, ri, ao, filled, ds, dr in stars:
        draw_dotted_star(d, cx, cy, ro, ri, dot_spacing=ds, dot_r=dr,
                         angle_offset=ao, filled=filled)
    return h_img


# --- Receipt compositor ---
def build_receipt(image_path):
    font_title, font_date, font_time = get_fonts()

    star_img = make_star_header()
    star_h = star_img.height
    photo_size = PRINTER_WIDTH - PADDING * 2
    gap_after_stars = 20
    divider_h = 14
    title_h = 28
    date_h = 22
    time_h = 18

    total_h = (star_h + gap_after_stars + title_h + 10 +
               divider_h + photo_size + divider_h +
               date_h + 4 + time_h + PADDING)

    canvas = Image.new("L", (PRINTER_WIDTH, total_h), color=255)
    draw = ImageDraw.Draw(canvas)

    y = 0

    # Stars
    canvas.paste(star_img, (0, y))
    y += star_h + gap_after_stars

    # Title
    draw.text((PRINTER_WIDTH // 2, y), "yujin's nest",
              font=font_title, fill=0, anchor="ma")
    y += title_h + 10

    # Divider
    for x in range(0, PRINTER_WIDTH, 8):
        draw.line([(x, y + 5), (x + 4, y + 5)], fill=180, width=1)
    y += divider_h

    # Photo
    img = Image.open(image_path)
    size = min(img.width, img.height)
    left = (img.width - size) // 2
    top = (img.height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    img = img.resize((photo_size, photo_size), Image.LANCZOS)
    img = img.convert("L")
    canvas.paste(img, (PADDING, y))
    y += photo_size + 4

    # Divider
    for x in range(0, PRINTER_WIDTH, 8):
        draw.line([(x, y + 5), (x + 4, y + 5)], fill=180, width=1)
    y += divider_h

    # Date + time
    now = datetime.now()
    draw.text((PRINTER_WIDTH // 2, y), now.strftime("%B %-d, %Y"),
              font=font_date, fill=0, anchor="ma")
    y += date_h + 4
    draw.text((PRINTER_WIDTH // 2, y), now.strftime("%-I:%M %p"),
              font=font_time, fill=80, anchor="ma")

    return canvas


# --- Print ---
def print_photo(image_path):
    receipt = build_receipt(image_path)
    receipt = receipt.rotate(180)

    p = EscposFile(PRINTER_DEVICE)
    try:
        p._raw(b"\x1b\x40")
        time.sleep(0.1)
        p._raw(b"\x12\x23\x0A")
        p._raw(b"\x1b\x37\x07\x50\x02")
        time.sleep(0.1)
        p.image(receipt, impl="bitImageRaster")
        p.text("\n\n\n\n")
        time.sleep(2)
    finally:
        p.close()


# --- Main ---
def main():
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration(
        main={"size": CAMERA_RES, "format": "RGB888"},
        raw=None,
        buffer_count=4
    )
    picam2.configure(preview_config)
    picam2.start()

    button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)

    print("Photobooth ready. Press the button to take a photo. Ctrl+C to quit.")

    try:
        while True:
            print("Waiting for button press...")
            button.wait_for_press()
            time.sleep(DEBOUNCE)

            for i in range(COUNTDOWN_SECONDS, 0, -1):
                print(f"{i}...")
                time.sleep(1)

            print("Capturing...")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_path = PHOTOS_DIR / f"photo_{ts}.jpg"

            capture_config = picam2.create_still_configuration(
                main={"size": CAPTURE_RES}
            )
            picam2.switch_mode_and_capture_file(capture_config, str(photo_path))

            picam2.stop()
            picam2.configure(preview_config)
            picam2.start()

            print(f"Saved: {photo_path}")

            print("Printing...")
            try:
                print_photo(photo_path)
                print("Done. Ready for next photo.")
            except Exception as e:
                print(f"Print error: {e}")

    except KeyboardInterrupt:
        print("\nPhotobooth stopped.")
    finally:
        picam2.stop()


if __name__ == "__main__":
    main()