# Photobooth

A Raspberry Pi 5 photobooth with arcade button trigger and thermal receipt printer output. No touchscreen or display required.

## Features

- Trigger via arcade button press
- 3-second countdown (printed to terminal)
- Auto-print captured photo on a thermal receipt printer
- Photos saved to `~/photobooth/captures/`

## Hardware

- Raspberry Pi 5
- OV5647 camera module (Pi Camera v1 compatible)
- CSN-A4L thermal receipt printer (USB)
- Arcade-style illuminated push button
- 12V LiPo battery + 12V to 5V DC-DC converter (printer power)

Thermal printer: [Mini Thermal Receipt Printer (The Pi Hut)](https://thepihut.com/products/mini-thermal-receipt-printer?srsltid=AfmBOoqyFy_vYgifQd-CT2KruQv0nRyC9_tgL9VE92RPIDdgnvrLr6e5)

See [`hardware.md`](hardware.md) for wiring details.

## Software setup

### 1. Flash Raspberry Pi OS (64-bit) and enable SSH/Wi-Fi via Pi Imager.

### 2. Install system packages

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-pil python3-pip python3-venv git rpicam-apps
```

### 3. Clone and set up the project

```bash
cd ~
git clone https://github.com/yujinkim/raspberry-photobooth photobooth
cd photobooth
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure `/boot/firmware/config.txt`

Make sure these are set:

```
camera_auto_detect=1
dtoverlay=vc4-kms-v3d
```

### 5. Connect the printer via USB

The printer should appear at `/dev/usb/lp0`. Verify:

```bash
ls /dev/usb/lp*
```

### 6. Wire the arcade button

- Microswitch → GPIO 17 (Pi pin 11) and GND (Pi pin 9)
- LED → 5V (Pi pin 2) and GND (Pi pin 14)

### 7. Run

```bash
sudo ~/photobooth/venv/bin/python ~/photobooth/photobooth.py
```

Or set up an alias (recommended):

```bash
echo 'alias photobooth="sudo ~/photobooth/venv/bin/python ~/photobooth/photobooth.py"' >> ~/.bashrc
source ~/.bashrc
photobooth
```

## Flow

1. **Idle** — Script prints "Waiting for button press..." and blocks.
2. **Countdown** — Button press triggers a 3-second countdown printed to the terminal.
3. **Capture** — Full-resolution photo taken and saved.
4. **Print** — Photo is cropped, resized, and sent to the thermal printer.
5. **Repeat** — Returns to idle immediately after printing.

## Configuration

Edit constants at the top of `photobooth.py`:

- `CAPTURE_RES` — capture resolution (1920x1080 default)
- `COUNTDOWN_SECONDS` — countdown duration (3 default)
- `PRINTER_DEVICE` — printer device path (`/dev/usb/lp0` default)
- `BUTTON_PIN` — GPIO pin for the arcade button (17 default)
- `DEBOUNCE` — seconds to ignore after a press (1.0 default)

### Print quality

In the `print_photo()` function, adjust:

- Density (`b"\x12\x23\x0A"`) — change `0x0A` (100%) higher for darker, lower for lighter
- Heating (`b"\x1b\x37\x07\x50\x02"`) — see CSN-A4L manual for details

## Photo storage

Captured photos are saved to `~/photobooth/captures/photo_YYYYMMDD_HHMMSS.jpg`.

## Quitting

Press `Ctrl+C` in the terminal.

## License

MIT
