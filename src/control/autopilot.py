# autopilot.py
import time
import math
import json
import os
import re
from src.core.states import AutopilotState


class AutopilotLogic:
    def __init__(self, train_model):
        self.state = AutopilotState.CRUISING
        self.train_model = train_model

        # Formatting filename to match the calibrator
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', train_model)
        self.calib_file = os.path.join("data", f"calibration_{safe_name}.json")

        # Default physical fallbacks if not calibrated
        self.decel_rate = 1.5
        self.station_offsets = {}

        self._load_calibration()

        # Tuning parameter: Seconds to hold the key per 1 MPH difference.
        self.hold_time_per_mph = 0.015

        # Dead Reckoning State Variables
        self.last_time = time.time()
        self.is_tracking_platform = False
        self.platform_distance_traveled = 0.0
        self.last_reckoning_speed = None

    def _load_calibration(self):
        if os.path.exists(self.calib_file):
            with open(self.calib_file, 'r') as f:
                data = json.load(f)
                # Ensure we have a positive integer for the math
                raw_decel = abs(data.get("deceleration_rate_mph_s", 1.5))
                self.decel_rate = raw_decel * 0.8
                self.station_offsets = data.get("station_offsets", {})
                print(f"[Autopilot] Loaded profile for {self.train_model}. Deceleration: {self.decel_rate} mph/s")
        else:
            print(f"[Autopilot] WARNING: No calibration found for {self.train_model}. Using default physics.")

    def calculate_throttle_action(self, current_dial, target_limit):
        """
        A Proportional (P) control loop that determines how to adjust the train's speed.
        Returns a tuple: (action_type, duration_in_seconds)
        """
        if current_dial is None or target_limit is None:
            return "coast", 0.0

        diff = current_dial - target_limit

        # Deadband: If within 2 mph of the target, do nothing
        if abs(diff) <= 2:
            return "coast", 0.0

        # Calculate proportional hold time
        hold_time = abs(diff) * self.hold_time_per_mph

        # Cap the hold time so we don't block the computer vision loop (max 0.4s)
        hold_time = min(hold_time, 0.4)

        if diff > 0:
            # Dial is higher than limit -> Need to brake
            return "brake", hold_time
        else:
            # Dial is lower than limit -> Need to accelerate
            return "throttle", hold_time

    def calculate_braking_speed(self, distance_miles):
        """Calculates the maximum safe speed for a given distance to target."""
        if distance_miles <= 0:
            return 0

        # Kinematic equation: u = sqrt(2 * a * s)
        # 7200 scales the mph/s deceleration rate to match mph and miles.
        safe_speed = math.sqrt(7200 * self.decel_rate * distance_miles)
        return int(safe_speed)

    def update(self, curr_speed, limit_speed, signal_state, signal_distance, panel_data):
        """Evaluates the environment and returns the effective target speed."""
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        # --- 1. Signal Logic ---
        dist_to_signal = None
        if signal_state == "danger" and signal_distance is not None:
            # INCREASED MARGIN: Stop 0.04 miles (~210 feet) before the signal
            dist_to_signal = max(0.0, signal_distance - 0.04)

        # --- 2. Station Logic & Dead Reckoning ---
        ui_dist = panel_data.get("distance")
        station = panel_data.get("next_stop")
        platform = panel_data.get("platform")

        key = f"{station}_Plt{platform}"
        # Fallback to 0.02 miles if we haven't calibrated this specific platform yet
        offset = self.station_offsets.get(key, 0.02)

        dist_to_station = None

        if ui_dist is not None:
            if ui_dist == 0.0:
                if curr_speed is not None and curr_speed > 0:
                    # We entered the platform bounds. Begin Dead Reckoning.
                    if not self.is_tracking_platform:
                        self.is_tracking_platform = True
                        self.platform_distance_traveled = 0.0
                        self.last_reckoning_speed = curr_speed
                    else:
                        # Use average speed between this frame and last frame for better accuracy
                        avg_speed = (curr_speed + self.last_reckoning_speed) / 2.0
                        self.platform_distance_traveled += (avg_speed / 3600.0) * dt
                        self.last_reckoning_speed = curr_speed

                    dist_to_station = max(0.0, (offset - 0.004) - self.platform_distance_traveled)
                else:
                    # THE FIX: Train is fully stopped (curr_speed == 0) or OCR dropped a frame.
                    # Lock the distance to 0 so the speed limit stays firmly at 0 MPH!
                    dist_to_station = 0.0

            elif ui_dist > 0:
                # We are approaching the station. Distance = UI Distance + the platform offset.
                self.is_tracking_platform = False
                self.platform_distance_traveled = 0.0
                dist_to_station = ui_dist + offset

        # --- 3. Speed Limit Calculation ---
        signal_limit = self.calculate_braking_speed(dist_to_signal) if dist_to_signal is not None else float('inf')
        station_limit = self.calculate_braking_speed(dist_to_station) if dist_to_station is not None else float('inf')

        # NEW: Enforce a 15 MPH approach speed when within 0.15 miles of a RED signal
        if dist_to_signal is not None and dist_to_signal <= 0.15:
            signal_limit = min(signal_limit, 15)

        # NEW: Enforce a 15 MPH approach speed when within 0.15 miles of the station
        if dist_to_station is not None:
            if dist_to_station <= 0.15:
                # Approach speed constraint
                station_limit = min(station_limit, 15)

                # THE KILL SWITCH: If we are extremely close, force the target to 0 immediately
            if dist_to_station <= 0.01:
                station_limit = 0

        # Handle intermediate signal states (yellows)
        if signal_state == "caution":
            signal_limit = min(signal_limit, 45)
        elif signal_state == "preliminary_caution":
            signal_limit = min(signal_limit, 70)

        # The effective limit is the most restrictive of all three factors
        track_limit = limit_speed if limit_speed is not None else float('inf')
        effective_limit = min(track_limit, signal_limit, station_limit)

        # --- 4. State Machine Updates ---
        if effective_limit == float('inf'):
            effective_limit = None  # Failsafe if nothing is detected
            self.state = AutopilotState.CRUISING
        elif curr_speed == 0 and effective_limit == 0:
            self.state = AutopilotState.STOPPED
        elif effective_limit == station_limit and effective_limit < track_limit:
            self.state = AutopilotState.BRAKING_STATION
        elif effective_limit == signal_limit and effective_limit < track_limit:
            self.state = AutopilotState.BRAKING_SIGNAL
        else:
            self.state = AutopilotState.CRUISING

        # Clean up the output to never return infinity
        if effective_limit == float('inf'):
            effective_limit = limit_speed

        return effective_limit, self.state