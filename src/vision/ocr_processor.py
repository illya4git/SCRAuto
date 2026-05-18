import re
import cv2
import numpy as np
import pytesseract

class OCRProcessor:
    def __init__(self, config):
        self.config = config
        pytesseract.pytesseract.tesseract_cmd = self.config.TESSERACT_CMD

    def _clean_tesseract_image(self, thresh_img):
        """Internal helper to flood-fill corners and remove long noise lines."""
        img = thresh_img.copy()
        h, w = img.shape
        mask = np.zeros((h + 2, w + 2), np.uint8)
        corners = [(0, 0), (0, h - 1), (w - 1, 0), (w - 1, h - 1)]

        for pt in corners:
            if img[pt[1], pt[0]] == 0:
                cv2.floodFill(img, mask, pt, 255)

        inv = cv2.bitwise_not(img)
        contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if (cw > ch * 3) or (y < 5):
                cv2.rectangle(img, (x, y), (x + cw, y + ch), 255, -1)
        return img

    def _clean_station_name(self, raw_name):
        if not raw_name:
            return None
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', '', raw_name).strip()
        parts = [p.strip() for p in re.split(r'\s{2,}|\n', cleaned) if p.strip()]
        if parts:
            for part in parts:
                if not part.isdigit():
                    return part
        return None

    def extract_panel_info(self, img_info):
        gray = cv2.cvtColor(img_info, cv2.COLOR_BGRA2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        text = pytesseract.image_to_string(thresh, config='--psm 6')

        next_stop_match = self.config.PATTERNS["next_stop"].search(text)
        distance_match = self.config.PATTERNS["distance"].search(text)
        platform_match = self.config.PATTERNS["platform"].search(text)

        raw_station = next_stop_match.group(1) if next_stop_match else None

        return {
            "next_stop": self._clean_station_name(raw_station),
            "distance": float(distance_match.group(1)) if distance_match else None,
            "platform": platform_match.group(1) if platform_match else None
        }, thresh

    def extract_speeds(self, img_speed):
        h = img_speed.shape[0]
        curr_img = cv2.resize(img_speed[0:h // 2, :], None, fx=4.5, fy=3, interpolation=cv2.INTER_CUBIC)
        limit_img = cv2.resize(img_speed[h // 2:h, :], None, fx=4.5, fy=3, interpolation=cv2.INTER_CUBIC)

        gray_c = cv2.cvtColor(curr_img, cv2.COLOR_BGRA2GRAY)
        blur_c = cv2.GaussianBlur(gray_c, (3, 3), 0)
        _, thresh_c = cv2.threshold(blur_c, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thresh_c = self._clean_tesseract_image(thresh_c)

        gray_l = cv2.cvtColor(limit_img, cv2.COLOR_BGRA2GRAY)
        blur_l = cv2.GaussianBlur(gray_l, (3, 3), 0)
        _, thresh_l = cv2.threshold(blur_l, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_l = self._clean_tesseract_image(thresh_l)

        kernel = np.ones((2, 2), np.uint8)
        thresh_c = cv2.copyMakeBorder(cv2.dilate(thresh_c, kernel, iterations=1), 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        thresh_l = cv2.copyMakeBorder(cv2.dilate(thresh_l, kernel, iterations=1), 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])

        ocr_config = '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789'
        curr_speed_str = pytesseract.image_to_string(thresh_c, config=ocr_config).strip()
        limit_speed_str = pytesseract.image_to_string(thresh_l, config=ocr_config).strip()

        curr_speed = int(curr_speed_str) if curr_speed_str.isdigit() else None
        limit_speed = int(limit_speed_str) if limit_speed_str.isdigit() else None

        return curr_speed, limit_speed, thresh_c, thresh_l

    def extract_signal_distance(self, signal_img):
        h = signal_img.shape[0]
        text_img = cv2.resize(signal_img[int(h * 0.6):h, :], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(text_img, cv2.COLOR_BGRA2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        text = pytesseract.image_to_string(thresh, config='--psm 6')
        match = self.config.PATTERNS["distance"].search(text)

        if match:
            try:
                return float(match.group(1)), thresh
            except ValueError:
                pass
        return None, thresh