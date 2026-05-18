import cv2
import numpy as np
import math


class UIDetector:
    def __init__(self, config):
        self.config = config
        self.calibration_points = sorted(self.config.DIAL_CALIBRATION_POINTS, key=lambda x: x[1])
        self.speeds = [point[0] for point in self.calibration_points]
        self.angles = [point[1] for point in self.calibration_points]

    def _get_contours(self, img, lower_hsv, upper_hsv):
        """Internal helper to standardize HSV masking and contour detection."""
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours, mask

    def extract_dial_speed(self, dial_img):
        h, w = dial_img.shape[:2]
        center = (w // 2, h // 2)

        outer_radius = (min(w, h) // 2) - 10
        inner_radius = (min(w, h) // 2) - 80

        donut_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(donut_mask, center, outer_radius, 255, -1)
        cv2.circle(donut_mask, center, inner_radius, 0, -1)

        masked_img = cv2.bitwise_and(dial_img, dial_img, mask=donut_mask)
        contours, _ = self._get_contours(masked_img, self.config.GREEN_LOWER, self.config.GREEN_UPPER)

        if contours:
            valid_contours = [c for c in contours if cv2.contourArea(c) > 15]
            if valid_contours:
                c = max(valid_contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX, cY = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                    angle_deg = (math.degrees(math.atan2(cY - center[1], cX - center[0])) + 360) % 360
                    return int(round(np.interp(angle_deg, self.angles, self.speeds)))
        return None

    def is_aws_active(self, dial_img):
        contours, _ = self._get_contours(dial_img, self.config.AWS_LOWER, self.config.AWS_UPPER)
        if contours:
            c = max(contours, key=cv2.contourArea)
            return cv2.contourArea(c) > 5000
        return False

    def is_spad_active(self, dial_img):
        bgr = cv2.cvtColor(dial_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        mask_red1 = cv2.inRange(hsv, np.array(self.config.RED_LOWER_1), np.array(self.config.RED_UPPER_1))
        mask_red2 = cv2.inRange(hsv, np.array(self.config.RED_LOWER_2), np.array(self.config.RED_UPPER_2))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            c = max(contours, key=cv2.contourArea)
            return cv2.contourArea(c) > 10000
        return False

    def is_loading_active(self, banner_img):
        _, mask = self._get_contours(banner_img, self.config.PURPLE_LOWER, self.config.PURPLE_UPPER)
        return cv2.countNonZero(mask) > 500

    def extract_signal_state(self, signal_img):
        def count_blobs(lower, upper, min_area=30):
            contours, _ = self._get_contours(signal_img, lower, upper)
            return len([c for c in contours if cv2.contourArea(c) > min_area])

        green_count = count_blobs(self.config.GREEN_LOWER, self.config.GREEN_UPPER)
        yellow_count = count_blobs(self.config.YELLOW_LOWER, self.config.YELLOW_UPPER)
        white_count = count_blobs(self.config.WHITE_LOWER, self.config.WHITE_UPPER)

        bgr = cv2.cvtColor(signal_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask_red1 = cv2.inRange(hsv, np.array(self.config.RED_LOWER_1), np.array(self.config.RED_UPPER_1))
        mask_red2 = cv2.inRange(hsv, np.array(self.config.RED_LOWER_2), np.array(self.config.RED_UPPER_2))
        red_contours, _ = cv2.findContours(cv2.bitwise_or(mask_red1, mask_red2), cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
        red_count = len([c for c in red_contours if cv2.contourArea(c) > 30])

        if green_count > 0:
            return "proceed"
        elif red_count > 0:
            return "danger"
        elif yellow_count == 2:
            return "preliminary_caution"
        elif yellow_count == 1:
            return "caution"
        elif white_count > 0:
            return "shunt_proceed"
        return "unknown"

    def find_next_leg_button(self, popup_img):
        contours, _ = self._get_contours(popup_img, self.config.NEXT_LEG_BLUE_LOWER, self.config.NEXT_LEG_BLUE_UPPER)
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 2000:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
        return None