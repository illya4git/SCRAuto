# config.py
import re

# Tesseract Configuration
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Regions of Interest (ROIs)
ROIS = {
    "info_panel": {"top": 1200, "left": 15, "width": 300, "height": 160},
    "signal": {"top": 1180, "left": 325, "width": 100, "height": 180},
    "digital_speed": {"top": 1200, "left": 2045, "width": 70, "height": 160},
    "dial": {"top": 1010, "left": 2190, "width": 464, "height": 464},
    "door_banner": {"top": 930, "left": 2190, "width": 464, "height": 80},
    "center_popup": {"top": 400, "left": 700, "width": 1000, "height": 600}
}

# --- Signal & Dial Color Masks (HSV) ---

# Red wraps around the HSV spectrum, so we often define two ranges or a wide one.
RED_LOWER_1 = [0, 120, 120]
RED_UPPER_1 = [10, 255, 255]
RED_LOWER_2 = [160, 120, 120]
RED_UPPER_2 = [180, 255, 255]

YELLOW_LOWER = [20, 120, 120]
YELLOW_UPPER = [35, 255, 255]

GREEN_LOWER = [45, 180, 180]
GREEN_UPPER = [75, 255, 255]

# White has very low saturation and high value
WHITE_LOWER = [0, 0, 200]
WHITE_UPPER = [180, 30, 255]

# Dial Calibration (Speed in MPH, Angle in Degrees)
DIAL_CALIBRATION_POINTS = [
    (0, 148.3),
    (30, 184.6),
    (60, 221.0),
    (90, 257.3),
]

# HSV Color range for the green dial indicator and orange AWS circle
GREEN_LOWER = [40, 100, 100]
GREEN_UPPER = [80, 255, 255]
AWS_LOWER = [15, 150, 150]
AWS_UPPER = [30, 255, 255]

# Matches the purple background of the "Loading in progress..." UI
PURPLE_LOWER = [125, 50, 50]
PURPLE_UPPER = [155, 255, 255]

# Matches the bright blue "Next Leg" button
NEXT_LEG_BLUE_LOWER = [100, 150, 150]
NEXT_LEG_BLUE_UPPER = [130, 255, 255]

# Pre-compiled Regex patterns for optimization
PATTERNS = {
    "next_stop": re.compile(r'Next stop\n(.*)'),
    "distance": re.compile(r'([\d.]+)\s*mi'),
    "platform": re.compile(r'Platform\s*(\d+)')
}