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
                img_signal = np.array(sct.grab(config.ROIS["signal"]))
                img_speed = np.array(sct.grab(config.ROIS["digital_speed"]))
                img_dial = np.array(sct.grab(config.ROIS["dial"]))

                # 2. Extract Data
                panel_data, info_thresh = vision.extract_panel_info(img_info)
                curr_speed, limit_speed, thresh_c, thresh_l = vision.extract_speeds(img_speed)
                dial_target_speed = vision.extract_dial_speed(img_dial)
                signal_state = vision.extract_signal_state(img_signal)
                signal_distance, sig_thresh = vision.extract_signal_distance(img_signal)
                aws_active = vision.is_aws_active(img_dial)

                # 3. Execute Control Actions
                if aws_active:
                    print("AWS Alarm detected! Acknowledging...")
                    controller.acknowledge_aws()

                # --- NEW: Autopilot Signal Logic ---
                # Default to track limit if the signal is "proceed", "shunt_proceed", or "unknown"
                signal_limit = limit_speed

                if signal_state == "danger":
                    signal_limit = 0
                elif signal_state == "caution":
                    signal_limit = 45
                elif signal_state == "preliminary_caution":
                    signal_limit = 70

                # Determine the effective target speed
                effective_limit = None
                if limit_speed is not None and signal_limit is not None:
                    # Always pick the safest (slowest) speed.
                    # E.g., if track is 30 but signal is 70, go 30.
                    effective_limit = min(limit_speed, signal_limit)
                elif signal_limit is not None:
                    effective_limit = signal_limit
                elif limit_speed is not None:
                    effective_limit = limit_speed

                # Execute Cruise Control with the newly calculated effective limit
                #controller.cruise_control(dial_target_speed, effective_limit)

                # --- Debug Output ---
                fps = 1.0 / (time.time() - start_time)
                print(
                    f"FPS: {fps:.1f} | Sig: {signal_state}, {signal_distance}mi | AWS: {aws_active} | Target: {dial_target_speed} | Track: {limit_speed} | Effective: {effective_limit}")

                # Show debug windows
                cv2.imshow("Signal Distance OCR", sig_thresh)
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