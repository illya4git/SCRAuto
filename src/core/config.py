# config.py
import re
import os

class AutopilotConfig:
    def __init__(self):
        # Dynamically resolve Tesseract path based on the host OS
        if os.name == 'nt':
            self.TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        else:
            # Standard path for Debian-based systems
            self.TESSERACT_CMD = r'/usr/bin/tesseract'

        # Regions of Interest (ROIs)
        self.ROIS = {
            "info_panel": {"top": 1200, "left": 15, "width": 300, "height": 160},
            "signal": {"top": 1180, "left": 325, "width": 100, "height": 180},
            "digital_speed": {"top": 1200, "left": 2045, "width": 70, "height": 160},
            "dial": {"top": 1010, "left": 2190, "width": 464, "height": 464},
            "door_banner": {"top": 930, "left": 2190, "width": 464, "height": 80},
            "center_popup": {"top": 400, "left": 700, "width": 1000, "height": 600}
        }

        # Color Masks
        self.RED_LOWER_1 = [0, 120, 120]
        self.RED_UPPER_1 = [10, 255, 255]
        self.RED_LOWER_2 = [160, 120, 120]
        self.RED_UPPER_2 = [180, 255, 255]
        self.YELLOW_LOWER = [20, 120, 120]
        self.YELLOW_UPPER = [35, 255, 255]
        self.GREEN_LOWER = [40, 100, 100]
        self.GREEN_UPPER = [80, 255, 255]
        self.WHITE_LOWER = [0, 0, 200]
        self.WHITE_UPPER = [180, 30, 255]
        self.AWS_LOWER = [15, 150, 150]
        self.AWS_UPPER = [30, 255, 255]
        self.PURPLE_LOWER = [125, 50, 50]
        self.PURPLE_UPPER = [155, 255, 255]
        self.NEXT_LEG_BLUE_LOWER = [100, 150, 150]
        self.NEXT_LEG_BLUE_UPPER = [130, 255, 255]

        # Dial Calibration
        self.DIAL_CALIBRATION_POINTS = [
            (0, 148.3), (30, 184.6), (60, 221.0), (90, 257.3),
        ]

        # Pre-compiled Regex patterns
        self.PATTERNS = {
            "next_stop": re.compile(r'Next stop\n(.*)'),
            "distance": re.compile(r'([\d.]+)\s*mi'),
            "platform": re.compile(r'Platform\s*(\d+)')
        }