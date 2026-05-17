# main.py
import cv2
import numpy as np
import mss
import time
import config
from vision import VisionExtractor
from controller import TrainController


def main():
    vision = VisionExtractor()
    controller = TrainController()

    print("Starting SCR Autopilot in 3 seconds. Focus the game window!")
    time.sleep(3)

    try:
        with mss.MSS() as sct:
            while True:
                start_time = time.time()

                # 1. Capture ROIs
                img_info = np.array(sct.grab(config.ROIS["info_panel"]))
                img_speed = np.array(sct.grab(config.ROIS["digital_speed"]))
                img_dial = np.array(sct.grab(config.ROIS["dial"]))

                # 2. Extract Data
                panel_data, info_thresh = vision.extract_panel_info(img_info)
                curr_speed, limit_speed, thresh_c, thresh_l = vision.extract_speeds(img_speed)
                dial_target_speed = vision.extract_dial_speed(img_dial)

                # 3. Execute Cruise Control (Match dial to limit)
                controller.cruise_control(dial_target_speed, limit_speed)

                # --- Debug & Console Output ---
                fps = 1.0 / (time.time() - start_time)
                print(
                    f"FPS: {fps:.1f} | Curr: {curr_speed} | Target Dial: {dial_target_speed} | Limit: {limit_speed} | Input: {controller.current_key}")

                cv2.imshow("Info Panel Debug", info_thresh)
                cv2.imshow("Speed Debug", np.vstack((thresh_c, thresh_l)))

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nAutopilot stopped by user.")
    finally:
        # CRITICAL: Release all keys if the script crashes or is closed
        controller.release_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()