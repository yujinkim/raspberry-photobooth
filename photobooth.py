"""
Photobooth (headless) - arcade button triggers countdown, capture, and thermal print.
No display or touchscreen required.
"""
import time
from pathlib import Path
from datetime import datetime

from picamera2 import Picamera2
from PIL import Image
from gpiozero import Button
from escpos.printer import File as EscposFile

# --- Configuration ---
CAMERA_RES = (800, 480)       # Preview resolution (for AEC/AWB settling)
CAPTURE_RES = (1920, 1080)    # Full-resolution still capture
COUNTDOWN_SECONDS = 3
PRINTER_DEVICE = "/dev/usb/lp0"
PRINTER_WIDTH_PX = 384
BUTTON_PIN = 17               # GPIO pin for the arcade button (Pi pin 11)

PHOTOS_DIR = Path.home() / "photobooth" / "captures"

# How long to wait after startup / each print before accepting the next press
DEBOUNCE = 1.0


def print_photo(image_path):
    from PIL import Image, ImageDraw, ImageFont
    import urllib.request

    PRINTER_WIDTH = 384
    PADDING = 16

    # Download Space Mono font if not already present
    font_path = Path.home() / "photobooth" / "SpaceMono-Regular.ttf"
    font_bold_path = Path.home() / "photobooth" / "SpaceMono-Bold.ttf"
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

    font_title = ImageFont.truetype(str(font_bold_path), 20)
    font_date = ImageFont.truetype(str(font_path), 16)
    font_time = ImageFont.truetype(str(font_path), 13)
    font_ascii = ImageFont.truetype(str(font_path), 7)

    ascii_art = (
        "                ⣴⣶⡀   \n"
        "  ⢠⣤⡀        ⣠⣤⣾⠏⠘⠿⣦⣤\n"
        "  ⣾⠉⠻⢶⠶⠛⢻⡇   ⠘⢻⡦   ⢰⡾⠃\n"
        "⢀⣤⠿    ⢠⡟⠁     ⸷⠿⠿⣾⣷ \n"
        "⢿⣥⣀    ⢻⡆               \n"
        " ⠈⠉⣿⣀⣾⠟⠛⠋⠁              \n"
        "   ⠘⠛⠁      ⢀⣾⢻⣆⡀       \n"
        "          ⢀⣤⣾⠃  ⠙⠛⣿⠇    \n"
        "          ⠈⠻⣶⡄   ⢸⣏      \n"
        "           ⢾⡷⠟⠛⠻⠿        "
    )

    # Measure ascii art height
    dummy = Image.new("L", (PRINTER_WIDTH, 1))
    draw_dummy = ImageDraw.Draw(dummy)
    ascii_bbox = draw_dummy.multiline_textbbox((0, 0), ascii_art, font=font_ascii, spacing=1)
    ascii_h = ascii_bbox[3] - ascii_bbox[1]

    title_bbox = draw_dummy.textbbox((0, 0), "yujin's nest", font=font_title)
    title_h = title_bbox[3] - title_bbox[1]

    photo_size = PRINTER_WIDTH - PADDING * 2
    divider_h = 12
    date_h = 20
    time_h = 18

    total_h = (
        PADDING +
        ascii_h + 8 +
        title_h + 12 +
        divider_h +
        photo_size + 
        divider_h +
        date_h + 4 +
        time_h +
        PADDING
    )

    canvas = Image.new("L", (PRINTER_WIDTH, total_h), color=255)
    draw = ImageDraw.Draw(canvas)

    y = PADDING

    # ASCII art centered
    draw.multiline_text(
        (PRINTER_WIDTH // 2, y),
        ascii_art,
        font=font_ascii,
        fill=0,
        anchor="ma",
        align="center",
        spacing=1
    )
    y += ascii_h + 8

    # Title
    draw.text((PRINTER_WIDTH // 2, y), "yujin's nest", font=font_title, fill=0, anchor="ma")
    y += title_h + 12

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

    # Date
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%B %-d, %Y")
    time_str = now.strftime("%-I:%M %p")

    draw.text((PRINTER_WIDTH // 2, y), date_str, font=font_date, fill=0, anchor="ma")
    y += date_h + 4

    draw.text((PRINTER_WIDTH // 2, y), time_str, font=font_time, fill=80, anchor="ma")

    # Send to printer
    p = EscposFile(PRINTER_DEVICE)
    try:
        p._raw(b"\x1b\x40")
        time.sleep(0.1)
        p._raw(b"\x12\x23\x0A")
        p._raw(b"\x1b\x37\x07\x50\x02")
        time.sleep(0.1)
        canvas = canvas.rotate(180)
        p.image(canvas, impl="bitImageRaster")
        p.text("\n\n\n\n")
        time.sleep(2)
    finally:
        p.close()


def main():
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    # Start camera in preview mode so AEC/AWB stay converged between shots
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
            time.sleep(DEBOUNCE)  # ignore held-down presses

            # Countdown
            for i in range(COUNTDOWN_SECONDS, 0, -1):
                print(f"{i}...")
                time.sleep(1)

            # Capture
            print("Capturing...")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_path = PHOTOS_DIR / f"photo_{ts}.jpg"

            capture_config = picam2.create_still_configuration(
                main={"size": CAPTURE_RES}
            )
            picam2.switch_mode_and_capture_file(capture_config, str(photo_path))

            # Resume preview mode for next shot
            picam2.stop()
            picam2.configure(preview_config)
            picam2.start()

            print(f"Saved: {photo_path}")

            # Print
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
