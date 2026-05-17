# config.py
import re

# Tesseract Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Regions of Interest (ROIs)
ROIS = {
    "info_panel": {"top": 1200, "left": 15, "width": 300, "height": 160},
    "digital_speed": {"top": 1200, "left": 2045, "width": 70, "height": 160},
    "dial": {"top": 1010, "left": 2190, "width": 464, "height": 464}
}

# Dial Calibration (Speed in MPH, Angle in Degrees)
DIAL_CALIBRATION_POINTS = [
    (0, 148.3),
    (30, 184.6),
    (60, 221.0),
    (90, 257.3),
]

# HSV Color range for the green dial indicator
GREEN_LOWER = [40, 100, 100]
GREEN_UPPER = [80, 255, 255]

# Pre-compiled Regex patterns for optimization
PATTERNS = {
    "next_stop": re.compile(r'Next stop\n(.*)'),
    "distance": re.compile(r'([\d.]+)\s*mi'),
    "platform": re.compile(r'Platform\s*(\d+)')
}