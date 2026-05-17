# vision.py
import cv2
import numpy as np
import pytesseract
import math
import config

pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


class VisionExtractor:
    def __init__(self):
        self.calibration_points = sorted(config.DIAL_CALIBRATION_POINTS, key=lambda x: x[1])
        self.speeds = [point[0] for point in self.calibration_points]
        self.angles = [point[1] for point in self.calibration_points]

    def clean_tesseract_image(self, thresh_img):
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

    def extract_panel_info(self, img_info):
        gray = cv2.cvtColor(img_info, cv2.COLOR_BGRA2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        text = pytesseract.image_to_string(thresh, config='--psm 6')

        next_stop = config.PATTERNS["next_stop"].search(text)
        distance = config.PATTERNS["distance"].search(text)
        platform = config.PATTERNS["platform"].search(text)

        return {
            "next_stop": next_stop.group(1) if next_stop else None,
            "distance": float(distance.group(1)) if distance else None,
            "platform": platform.group(1) if platform else None
        }, thresh

    def extract_speeds(self, img_speed):
        h = img_speed.shape[0]
        curr_img = img_speed[0:h // 2, :]
        limit_img = img_speed[h // 2:h, :]

        # Process Current Speed (White text)
        curr_img = cv2.resize(curr_img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray_c = cv2.cvtColor(curr_img, cv2.COLOR_BGRA2GRAY)
        _, thresh_c = cv2.threshold(gray_c, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thresh_c = self.clean_tesseract_image(thresh_c)
        thresh_c = cv2.copyMakeBorder(thresh_c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])

        # Process Limit Speed (Black text)
        limit_img = cv2.resize(limit_img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray_l = cv2.cvtColor(limit_img, cv2.COLOR_BGRA2GRAY)
        _, thresh_l = cv2.threshold(gray_l, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_l = self.clean_tesseract_image(thresh_l)
        thresh_l = cv2.copyMakeBorder(thresh_l, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])

        curr_speed_str = pytesseract.image_to_string(thresh_c,
                                                     config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()
        limit_speed_str = pytesseract.image_to_string(thresh_l,
                                                      config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()

        curr_speed = int(curr_speed_str) if curr_speed_str.isdigit() else None
        limit_speed = int(limit_speed_str) if limit_speed_str.isdigit() else None

        return curr_speed, limit_speed, thresh_c, thresh_l

    def extract_dial_speed(self, dial_img):
        bgr = cv2.cvtColor(dial_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        lower_green = np.array(config.GREEN_LOWER)
        upper_green = np.array(config.GREEN_UPPER)
        mask = cv2.inRange(hsv, lower_green, upper_green)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        target_speed = None
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 10:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX, cY = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                    dial_center_x, dial_center_y = bgr.shape[1] // 2, bgr.shape[0] // 2

                    angle_deg = math.degrees(math.atan2(cY - dial_center_y, cX - dial_center_x))
                    angle_deg = (angle_deg + 360) % 360

                    target_speed = int(round(np.interp(angle_deg, self.angles, self.speeds)))

        return target_speed