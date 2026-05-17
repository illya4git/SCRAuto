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
        h, w = dial_img.shape[:2]
        center = (w // 2, h // 2)

        # --- NEW: "Donut" (Annulus) Mask ---
        # We only want to look at the specific ring where the indicator travels.
        # Based on your 464x464 ROI, these radii limit the search area to the outer edge.
        # You may need to tweak the 'inner_radius' slightly if the indicator gets cut off.
        outer_radius = (min(w, h) // 2) - 10
        inner_radius = (min(w, h) // 2) - 80

        donut_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(donut_mask, center, outer_radius, 255, -1)  # Draw the full circle
        cv2.circle(donut_mask, center, inner_radius, 0, -1)  # Cut out the middle

        # Apply the donut mask
        masked_img = cv2.bitwise_and(dial_img, dial_img, mask=donut_mask)
        # -----------------------------------

        bgr = cv2.cvtColor(masked_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, np.array(config.GREEN_LOWER), np.array(config.GREEN_UPPER))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        target_speed = None
        if contours:
            # Filter out tiny noise artifacts that might still slip through
            valid_contours = [c for c in contours if cv2.contourArea(c) > 15]

            if valid_contours:
                # Grab the largest remaining blob
                c = max(valid_contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX, cY = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])

                    angle_deg = math.degrees(math.atan2(cY - center[1], cX - center[0]))
                    angle_deg = (angle_deg + 360) % 360

                    target_speed = int(round(np.interp(angle_deg, self.angles, self.speeds)))

        return target_speed

    def is_aws_active(self, dial_img):
        """Checks if the large orange/yellow AWS confirmation button is present."""
        bgr = cv2.cvtColor(dial_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(config.AWS_LOWER), np.array(config.AWS_UPPER))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            c = max(contours, key=cv2.contourArea)
            # The button is huge. A threshold of 5000 ensures we don't trigger on tiny yellow pixels.
            if cv2.contourArea(c) > 5000:
                return True
        return False

    def extract_signal_state(self, signal_img):
        """
        Analyzes the signal UI block and returns the current signal state:
        'proceed', 'caution', 'preliminary_caution', 'danger', 'shunt_proceed', or 'unknown'.
        """
        bgr = cv2.cvtColor(signal_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Helper function to count valid circular blobs of a certain color
        def count_blobs(lower, upper, min_area=30):
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # Filter out tiny noise
            valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
            return len(valid_contours)

        # Count the lights
        green_count = count_blobs(config.GREEN_LOWER, config.GREEN_UPPER)
        yellow_count = count_blobs(config.YELLOW_LOWER, config.YELLOW_UPPER)
        white_count = count_blobs(config.WHITE_LOWER, config.WHITE_UPPER)

        # Red requires combining two masks because it wraps around the HSV spectrum
        mask_red1 = cv2.inRange(hsv, np.array(config.RED_LOWER_1), np.array(config.RED_UPPER_1))
        mask_red2 = cv2.inRange(hsv, np.array(config.RED_LOWER_2), np.array(config.RED_UPPER_2))
        mask_red_full = cv2.bitwise_or(mask_red1, mask_red2)
        red_contours, _ = cv2.findContours(mask_red_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        red_count = len([c for c in red_contours if cv2.contourArea(c) > 30])

        # State Mapping Logic
        if green_count > 0:
            return "proceed"  # 4-aspect proceed
        elif red_count > 0:
            return "danger"  # Covers both 4-aspect (1 red) and Shunt (2 reds)
        elif yellow_count == 2:
            return "preliminary_caution"  # 4-aspect preliminary (2 yellows)
        elif yellow_count == 1:
            return "caution"  # 4-aspect caution (1 yellow)
        elif white_count > 0:
            return "shunt_proceed"  # Shunt proceed (2 whites)

        return "unknown"  # Failsafe if no lights are detected