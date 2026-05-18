import cv2
import numpy as np
import mss
import time
from src.core.states import StationState, AutopilotState


class GameOrchestrator:
    def __init__(self, config, ocr, ui, controller, mode, pilot=None, calibrator=None):
        self.config = config
        self.ocr = ocr
        self.ui = ui
        self.controller = controller
        self.mode = mode
        self.pilot = pilot
        self.calibrator = calibrator

        # Internal State tracking
        self.station_state = StationState.DRIVING
        self.door_timer = 0
        self.last_valid_speed = 0
        self.terminus_timer = 0

    def run(self):
        print("\nStarting in 3 seconds. Focus the game window!")
        time.sleep(3)

        try:
            with mss.MSS() as sct:
                while True:
                    self._loop_iteration(sct)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
        except KeyboardInterrupt:
            print("\nScript stopped by user.")
        finally:
            self.controller.release_all()
            cv2.destroyAllWindows()

    def _loop_iteration(self, sct):
        start_time = time.time()

        # 1. Capture & Extract (Abstracted mapping)
        rois = self.config.ROIS
        img_info = np.array(sct.grab(rois["info_panel"]))
        img_signal = np.array(sct.grab(rois["signal"]))
        img_speed = np.array(sct.grab(rois["digital_speed"]))
        img_dial = np.array(sct.grab(rois["dial"]))
        img_door_banner = np.array(sct.grab(rois["door_banner"]))
        img_popup = np.array(sct.grab(rois["center_popup"]))

        panel_data, info_thresh = self.ocr.extract_panel_info(img_info)
        curr_speed, limit_speed, thresh_c, thresh_l = self.ocr.extract_speeds(img_speed)
        dial_target_speed = self.ui.extract_dial_speed(img_dial)
        signal_state = self.ui.extract_signal_state(img_signal)
        signal_distance, sig_thresh = self.ocr.extract_signal_distance(img_signal)
        is_loading = self.ui.is_loading_active(img_door_banner)
        next_leg_pos = self.ui.find_next_leg_button(img_popup)
        aws_active = self.ui.is_aws_active(img_dial)
        spad_active = self.ui.is_spad_active(img_dial)

        # Smart OCR Speed Fallback
        if curr_speed is not None:
            self.last_valid_speed = curr_speed
        else:
            curr_speed = 0 if self.last_valid_speed <= 3 else self.last_valid_speed

        if aws_active:
            print("AWS Alarm detected! Acknowledging...")
            self.controller.acknowledge_aws()

        # Route to Mode Handler
        if self.mode == '2':
            self._handle_calibration(curr_speed, panel_data, start_time)
        else:
            self._handle_autopilot(
                curr_speed, limit_speed, signal_state, signal_distance,
                panel_data, dial_target_speed, spad_active, is_loading,
                next_leg_pos, start_time
            )

        # UI Rendering
        cv2.imshow("Signal Distance OCR", sig_thresh)
        cv2.imshow("Info Panel Debug", info_thresh)
        # Add other windows as needed...

    def _handle_calibration(self, curr_speed, panel_data, start_time):
        self.calibrator.update(curr_speed, panel_data)
        fps = 1.0 / (time.time() - start_time)
        print(f"FPS: {fps:.1f} | Calibrating... | Speed: {curr_speed} | Station: {panel_data.get('next_stop')}")

    def _handle_autopilot(self, curr_speed, limit_speed, signal_state, signal_distance, panel_data, dial_target_speed,
                          spad_active, is_loading, next_leg_pos, start_time):
        if spad_active:
            self.controller.release_all()
            print(f"State: SPAD_RECOVERY | Brute-forcing Q release...")
            self.controller.release_spad()
            time.sleep(0.5)
            return

        effective_limit, pilot_state = self.pilot.update(
            curr_speed, limit_speed, signal_state, signal_distance, panel_data
        )

        ui_dist = panel_data.get("distance")

        # Re-implemented Station State Machine using Enum
        if self.station_state == StationState.DRIVING:
            if pilot_state == AutopilotState.STOPPED and curr_speed == 0 and ui_dist == 0.0:
                print("\n[Station] Train stopped at platform. Opening doors...")
                self.controller.release_all()
                self.controller.toggle_doors()
                self.station_state = StationState.WAITING_LOADING_START
                self.door_timer = time.time()
            else:
                # NEW: Ask autopilot for the math, tell controller to execute
                action, duration = self.pilot.calculate_throttle_action(dial_target_speed, effective_limit)

                if action == "throttle":
                    self.controller.apply_throttle(duration)
                elif action == "brake":
                    self.controller.apply_brake(duration)
                else:
                    self.controller.release_all()

        elif self.station_state == StationState.WAITING_LOADING_START:
            if is_loading:
                self.station_state = StationState.LOADING
            elif time.time() - self.door_timer > 3.0:
                self.controller.toggle_doors()
                self.door_timer = time.time()

        elif self.station_state == StationState.LOADING:
            if not is_loading:
                time.sleep(0.5)
                self.station_state = StationState.CHECKING_TERMINUS
                self.terminus_timer = time.time()

        elif self.station_state == StationState.CHECKING_TERMINUS:
            if next_leg_pos is not None:
                global_x = next_leg_pos[0] + self.config.ROIS["center_popup"]["left"]
                global_y = next_leg_pos[1] + self.config.ROIS["center_popup"]["top"]
                self.controller.click_screen(global_x, global_y)
                self.station_state = StationState.WAITING_LOADING_START
                self.door_timer = time.time()
            elif time.time() - self.terminus_timer > 2.0:
                self.controller.toggle_doors()
                self.station_state = StationState.WAITING_DEPARTURE

        elif self.station_state == StationState.WAITING_DEPARTURE:
            if ui_dist is not None and ui_dist > 0.0:
                self.station_state = StationState.DRIVING

        fps = 1.0 / (time.time() - start_time)
        print(
            f"FPS: {fps:.1f} | State: {pilot_state.name} ({self.station_state.name}) | Tgt: {dial_target_speed} | Eff: {effective_limit}")