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
                img_signal = np.array(sct.grab(config.ROIS["signal"]))  # NEW
                img_speed = np.array(sct.grab(config.ROIS["digital_speed"]))
                img_dial = np.array(sct.grab(config.ROIS["dial"]))

                # 2. Extract Data
                panel_data, info_thresh = vision.extract_panel_info(img_info)
                curr_speed, limit_speed, thresh_c, thresh_l = vision.extract_speeds(img_speed)
                dial_target_speed = vision.extract_dial_speed(img_dial)
                signal_state = vision.extract_signal_state(img_signal)

                # --- NEW: AWS Check ---
                aws_active = vision.is_aws_active(img_dial)

                # 3. Execute Control Actions
                if aws_active:
                    print("AWS Alarm detected! Acknowledging...")
                    controller.acknowledge_aws()

                #controller.cruise_control(dial_target_speed, limit_speed)

                # --- Debug Output ---
                fps = 1.0 / (time.time() - start_time)
                print(
                    f"FPS: {fps:.1f} | Sig: {signal_state} | AWS: {aws_active} | Target: {dial_target_speed} | Lim: {limit_speed}")

                # Show the signal box to make sure your ROI coordinates are correct
                cv2.imshow("Signal ROI Debug", img_signal)
                cv2.imshow("Info Panel Debug", info_thresh)
                cv2.imshow("Speed Debug", np.vstack((thresh_c, thresh_l)))

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nAutopilot stopped by user.")
    finally:
        controller.release_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()