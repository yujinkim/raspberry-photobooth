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
    p = EscposFile(PRINTER_DEVICE)
    try:
        p._raw(b"\x1b\x40")              # ESC @ - initialize
        time.sleep(0.1)
        p._raw(b"\x12\x23\x0A")          # DC2 # 10 - density ~100%
        p._raw(b"\x1b\x37\x07\x50\x02")  # ESC 7 - default heat params
        time.sleep(0.1)

        img = Image.open(image_path)
        size = min(img.width, img.height)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((PRINTER_WIDTH_PX, PRINTER_WIDTH_PX), Image.LANCZOS)
        img = img.rotate(180)            # Flip 180 so it prints right-side-up
        img = img.convert("L")

        p.image(img, impl="bitImageRaster")
        p.text("\n\n\n\n")
        time.sleep(2)
    finally:
        p.close()


def main():
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    # Start camera in preview mode so AEC/AWB stay converged between shots
    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration(
        main={"size": CAMERA_RES, "format": "RGB888"}
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
