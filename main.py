import cv2
import numpy as np
import mss
import pytesseract
import time
import re
import math

# IMPORTANT: Point this to your tesseract executable if it's not in your PATH
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Define Regions of Interest (ROIs) - ADJUST THESE TO YOUR RESOLUTION
monitor_info_panel = {"top": 1200, "left": 15, "width": 300, "height": 160}
monitor_digital_speed = {"top": 1200, "left": 2045, "width": 70, "height": 160}
monitor_dial = {"top": 1010, "left": 2190, "width": 464, "height": 464}

# --- DIAL CALIBRATION DATA ---
# Format is: (Speed in MPH, Angle in Degrees)
# REPLACE THESE WITH YOUR OWN RECORDED VALUES
DIAL_CALIBRATION_POINTS = [
    (0, 148.3),   # Example: 0 mph is pointing straight left
    (30, 184.6),   # Example: 30 mph is pointing straight up
    (60, 221.0),     # Example: 60 mph is pointing straight right
    (90, 257.3),    # Example: 90 mph is pointing straight down
]


def clean_tesseract_image(thresh_img):
    """Removes border boxes and horizontal lines that confuse Tesseract."""
    img = thresh_img.copy()
    h, w = img.shape

    # 1. Floodfill corners to remove the giant black box (fixes the bottom limit speed)
    # The mask needs to be 2 pixels larger than the image for OpenCV's floodFill
    mask = np.zeros((h + 2, w + 2), np.uint8)
    corners = [(0, 0), (0, h - 1), (w - 1, 0), (w - 1, h - 1)]

    for pt in corners:
        # If the corner pixel is black, fill it with white
        if img[pt[1], pt[0]] == 0:
            cv2.floodFill(img, mask, pt, 255)

    # 2. Contour filtering to remove horizontal lines and stray arcs
    # We invert to find contours of the black text/lines
    inv = cv2.bitwise_not(img)
    contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # If the object is wide and thin (horizontal line) OR touches the very top edge (the arc)
        if (cw > ch * 3) or (y < 5):
            # Paint a white rectangle over it to erase it completely
            cv2.rectangle(img, (x, y), (x + cw, y + ch), 255, -1)

    return img

def process_text(img):
    """Converts image to grayscale and applies thresholding for better OCR."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    # Thresholding: Make light text black and dark backgrounds white
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    return thresh


def process_white_text(img):
    """For the top speed (white text on dark background). Inverts to black on white."""
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Run the new cleanup function!
    return clean_tesseract_image(thresh)


def process_black_text(img):
    """For the bottom speed limit (black text on white circle). Keeps it black on white."""
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Run the new cleanup function!
    return clean_tesseract_image(thresh)

def calculate_speed_from_angle(current_angle):
    """Uses linear interpolation to map an angle to a speed value."""
    # numpy.interp requires the x-values (angles) to be sorted from lowest to highest
    sorted_points = sorted(DIAL_CALIBRATION_POINTS, key=lambda x: x[1])

    # Split the tuples into two separate lists
    speeds = [point[0] for point in sorted_points]
    angles = [point[1] for point in sorted_points]

    # np.interp(target_x, known_x_array, known_y_array)
    estimated_speed = np.interp(current_angle, angles, speeds)

    # Return it as a clean integer
    return int(round(estimated_speed))

def get_green_arrow_speed(dial_img):
    """Isolates the green selector, calculates its angle, and returns debug visuals."""
    # 1. Convert BGRA (screen capture) to standard BGR
    bgr = cv2.cvtColor(dial_img, cv2.COLOR_BGRA2BGR)

    # 2. Convert to HSV for robust color isolation
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # 3. Define range for the bright green color (Adjust these if it's not picking it up)
    lower_green = np.array([40, 100, 100])
    upper_green = np.array([80, 255, 255])

    # 4. Create a mask: White pixels where it's green, Black everywhere else
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # 5. Find the shapes (contours) of the green blobs
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Setup variables to return
    debug_img = bgr.copy()
    angle_deg = None
    target_speed_str = "Not found"

    if contours:
        # Assume the largest green object is our selector
        c = max(contours, key=cv2.contourArea)

        # Filter out tiny specks of noise
        if cv2.contourArea(c) > 10:
            # Calculate the "center of mass" of the green blob
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])

                # Assume the center of the image crop is the center of the dial
                dial_center_x = bgr.shape[1] // 2
                dial_center_y = bgr.shape[0] // 2

                # Calculate the angle using atan2 (Note: Y-axis is inverted in image coordinates)
                dy = cY - dial_center_y
                dx = cX - dial_center_x
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)

                # --- THE FIX: Normalize to a 0-360 degree scale ---
                angle_deg = (angle_deg + 360) % 360

                # --- NEW INTERPOLATION CODE ---
                # Calculate the actual speed using our calibration data
                actual_speed = calculate_speed_from_angle(angle_deg)

                # Update the string to show the final result
                target_speed_str = f"{actual_speed} MPH (Raw: {angle_deg:.1f}°)"

                # --- DRAW DEBUG VISUALS ---
                # Draw a red dot at the center of the dial
                cv2.circle(debug_img, (dial_center_x, dial_center_y), 5, (0, 0, 255), -1)
                # Draw a blue dot on the green selector
                cv2.circle(debug_img, (cX, cY), 5, (255, 0, 0), -1)
                # Draw a yellow line connecting them
                cv2.line(debug_img, (dial_center_x, dial_center_y), (cX, cY), (0, 255, 255), 2)

    return target_speed_str, angle_deg, debug_img, mask


def main():
    with mss.MSS() as sct:
        while True:
            start_time = time.time()

            # 1. Capture the ROIs
            img_info = np.array(sct.grab(monitor_info_panel))
            img_speed = np.array(sct.grab(monitor_digital_speed))
            img_dial = np.array(sct.grab(monitor_dial))

            # 2. Process Left Panel (Next Stop, Distance, Platform)
            info_thresh = process_text(img_info)
            # Use psm 6 (Assume a single uniform block of text)
            info_text = pytesseract.image_to_string(info_thresh, config='--psm 6')

            # Basic parsing using Regex
            next_stop = re.search(r'Next stop\n(.*)', info_text)
            distance = re.search(r'([\d.]+)\s*mi', info_text)
            platform = re.search(r'Platform\s*(\d+)', info_text)

            # 3. Process Right Panel (Digital Speeds)
            h = img_speed.shape[0]
            current_speed_img = img_speed[0:h // 2, :]
            speed_limit_img = img_speed[h // 2:h, :]

            # Apply the CORRECT thresholding to each half
            curr_thresh = process_white_text(current_speed_img)
            limit_thresh = process_black_text(speed_limit_img)

            # Add white padding so Tesseract doesn't choke on edge-to-edge text
            curr_thresh = cv2.copyMakeBorder(curr_thresh, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])
            limit_thresh = cv2.copyMakeBorder(limit_thresh, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])

            # config outputbase digits restricts Tesseract to numbers only
            # Try changing --psm 8 to --psm 7
            curr_speed = pytesseract.image_to_string(curr_thresh,
                                                     config='--psm 7 -c tessedit_char_whitelist=0123456789')
            limit_speed = pytesseract.image_to_string(limit_thresh,
                                                      config='--psm 8 -c tessedit_char_whitelist=0123456789')

            # 4. Process Dial for Green Arrow
            # Catch the new outputs: the string, the raw angle, and the two debug images
            target_speed_str, raw_angle, dial_debug, dial_mask = get_green_arrow_speed(img_dial)

            # ... (Keep your print statements here) ...
            # Update the Selector print statement to use the new variable:
            print(f"Selector:  {target_speed_str}")

            # ... (Keep your FPS calculation here) ...

            # Show the preprocessed images for debugging
            cv2.imshow("Info Panel Debug", info_thresh)

            stacked_speed_debug = np.vstack((curr_thresh, limit_thresh))
            cv2.imshow("Speed Debug", stacked_speed_debug)

            # --- NEW DIAL DEBUG WINDOWS ---
            cv2.imshow("Dial Mask (Should be just the green arrow)", dial_mask)
            cv2.imshow("Dial Tracking", dial_debug)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()