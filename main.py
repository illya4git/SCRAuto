# main.py
import cv2
import numpy as np
import mss
import time
import config
from vision import VisionExtractor
from controller import TrainController
from calibration import TrainCalibrator
from autopilot import AutopilotLogic, AutopilotState  # <-- Import the new module


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

    station_state = "DRIVING"
    door_timer = 0
    last_valid_speed = 0
    terminus_timer = 0

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
                img_door_banner = np.array(sct.grab(config.ROIS["door_banner"]))
                img_popup = np.array(sct.grab(config.ROIS["center_popup"]))

                # 2. Extract Data
                panel_data, info_thresh = vision.extract_panel_info(img_info)
                curr_speed, limit_speed, thresh_c, thresh_l = vision.extract_speeds(img_speed)
                dial_target_speed = vision.extract_dial_speed(img_dial)
                signal_state = vision.extract_signal_state(img_signal)
                signal_distance, sig_thresh = vision.extract_signal_distance(img_signal)
                is_loading = vision.is_loading_active(img_door_banner)
                next_leg_pos = vision.find_next_leg_button(img_popup)

                aws_active = vision.is_aws_active(img_dial)
                spad_active = vision.is_spad_active(img_dial)

                # --- NEW: Smart OCR Speed Fallback ---
                if curr_speed is not None:
                    last_valid_speed = curr_speed
                else:
                    # If we lose the number, assume we stopped if we were already going very slow
                    if last_valid_speed <= 3:
                        curr_speed = 0
                    else:
                        # Dropped a frame at high speed, reuse previous frame
                        curr_speed = last_valid_speed
                # -------------------------------------

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
                    if spad_active:
                        # --- SPAD RECOVERY LOGIC ---
                        controller.release_all()  # Drop the throttle/brakes immediately
                        fps = 1.0 / (time.time() - start_time)
                        print(f"FPS: {fps:.1f} | State: SPAD_RECOVERY | Brute-forcing Q release...")

                        # Simply press Q.
                        # We use a 0.5s sleep so we aren't spamming the key 30 times a second,
                        # but we hit it often enough to catch the exact moment the timer expires.
                        controller.release_spad()
                        time.sleep(0.5)
                    else:
                        # --- NORMAL DRIVING & STATION LOGIC ---
                        effective_limit, pilot_state = pilot.update(
                            curr_speed, limit_speed, signal_state, signal_distance, panel_data
                        )

                        ui_dist = panel_data.get("distance")

                        if station_state == "DRIVING":
                            if pilot_state == AutopilotState.STOPPED and curr_speed == 0 and ui_dist == 0.0:
                                print("\n[Station] Train stopped at platform. Opening doors...")
                                controller.release_all()
                                controller.toggle_doors()
                                station_state = "WAITING_LOADING_START"
                                door_timer = time.time()
                            else:
                                controller.cruise_control(dial_target_speed, effective_limit)

                        elif station_state == "WAITING_LOADING_START":
                            if is_loading:
                                print("[Station] Loading passengers...")
                                station_state = "LOADING"
                            elif time.time() - door_timer > 3.0:
                                print("[Station] Retrying doors...")
                                controller.toggle_doors()
                                door_timer = time.time()

                        elif station_state == "LOADING":
                            if not is_loading:
                                time.sleep(0.5)
                                print("[Station] Loading finished! Checking for terminus...")
                                # --- INSTEAD OF CLOSING DOORS, ENTER TERMINUS CHECK ---
                                station_state = "CHECKING_TERMINUS"
                                terminus_timer = time.time()

                        elif station_state == "CHECKING_TERMINUS":
                            # We give the game 2 seconds to spawn the popup
                            if next_leg_pos is not None:
                                print("[Station] Terminus popup detected! Clicking 'Next Leg'...")

                                # Convert the local coordinates inside the ROI to global screen coordinates
                                global_x = next_leg_pos[0] + config.ROIS["center_popup"]["left"]
                                global_y = next_leg_pos[1] + config.ROIS["center_popup"]["top"]

                                controller.click_screen(global_x, global_y)

                                # Loop back to wait for the second loading phase to begin
                                station_state = "WAITING_LOADING_START"
                                door_timer = time.time()

                            elif time.time() - terminus_timer > 2.0:
                                # 2 seconds passed and no blue button appeared. It's safe to close doors.
                                print("[Station] Closing doors...")
                                controller.toggle_doors()
                                station_state = "WAITING_DEPARTURE"

                        elif station_state == "WAITING_DEPARTURE":
                            if ui_dist is not None and ui_dist > 0.0:
                                print("[Station] Departure cleared. Resuming journey...\n")
                                station_state = "DRIVING"

                        fps = 1.0 / (time.time() - start_time)
                        # Updated print to show station state
                        print(
                            f"FPS: {fps:.1f} | State: {pilot_state} ({station_state}) | Tgt: {dial_target_speed} | Eff: {effective_limit}")

                # Show debug windows
                cv2.imshow("Signal Distance OCR", sig_thresh)
                cv2.imshow("Signal ROI Debug", img_signal)
                cv2.imshow("Info Panel Debug", info_thresh)
                cv2.imshow("Speed Debug", np.vstack((thresh_c, thresh_l)))
                cv2.imshow("Door Banner Mask", cv2.cvtColor(img_door_banner, cv2.COLOR_BGRA2BGR))

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    finally:
        controller.release_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()