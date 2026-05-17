# main.py
import cv2
import numpy as np
import mss
import time
import config
from vision import VisionExtractor
from controller import TrainController
from calibration import TrainCalibrator
from autopilot import AutopilotLogic  # <-- Import the new module


def main():
    print("=======================================")
    print("      SCR Autopilot Framework          ")
    print("=======================================")
    print("1. Autopilot Mode (Drive automatically)")
    print("2. Calibration Mode (Record offsets manually)")
    print("=======================================")

    mode = input("Select mode (1 or 2): ").strip()
    train_model = input("Enter the Train Model (e.g., 'Class 357 4-car'): ").strip()

    calibrator = None
    pilot = None

    if mode == '2':
        calibrator = TrainCalibrator(train_model)
        print(f"Calibration mode activated for {train_model}.")
    elif mode == '1':
        pilot = AutopilotLogic(train_model)
        print("Autopilot mode activated.")
    else:
        print("Invalid selection. Defaulting to Autopilot.")
        mode = '1'
        pilot = AutopilotLogic(train_model)

    vision = VisionExtractor()
    controller = TrainController()

    print("\nStarting in 3 seconds. Focus the game window!")
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

                # 3. Handle AWS universally
                if aws_active:
                    print("AWS Alarm detected! Acknowledging...")
                    controller.acknowledge_aws()

                # 4. MODE SPECIFIC LOGIC
                if mode == '2':
                    calibrator.update(curr_speed, panel_data)
                    fps = 1.0 / (time.time() - start_time)
                    print(
                        f"FPS: {fps:.1f} | Calibrating... | Speed: {curr_speed} | Station: {panel_data.get('next_stop')}")

                else:
                    # --- AUTOPILOT MODE ---
                    effective_limit, pilot_state = pilot.update(
                        curr_speed, limit_speed, signal_state, signal_distance, panel_data
                    )

                    # Execute Cruise Control with dynamic braking curve
                    controller.cruise_control(dial_target_speed, effective_limit)

                    fps = 1.0 / (time.time() - start_time)
                    print(
                        f"FPS: {fps:.1f} | State: {pilot_state} | Sig: {signal_state} | Tgt: {dial_target_speed} | Eff: {effective_limit}")

                # Show debug windows
                cv2.imshow("Signal Distance OCR", sig_thresh)
                cv2.imshow("Signal ROI Debug", img_signal)
                cv2.imshow("Info Panel Debug", info_thresh)
                cv2.imshow("Speed Debug", np.vstack((thresh_c, thresh_l)))

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    finally:
        controller.release_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()