# calibration.py
import json
import os
import time
import re


class TrainCalibrator:
    def __init__(self, train_model_name):
        self.train_model = train_model_name
        # Sanitize filename (e.g., "Class 357" -> "calibration_Class_357.json")
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', train_model_name)
        self.filename = os.path.join("data", f"calibration_{safe_name}.json")

        self.data = self._load_data()

        # State variables for Offset integration
        self.is_tracking_offset = False
        self.current_offset = 0.0
        self.last_time = time.time()
        self.tracked_station = None
        self.tracked_platform = None

        # State variables for Accel/Decel tracking
        self.last_speed = None
        self.accel_samples = []
        self.decel_samples = []

    def _load_data(self):
        """Loads existing calibration data or creates a default structure."""
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {
            "train_model": self.train_model,
            "acceleration_rate_mph_s": 0.0,
            "deceleration_rate_mph_s": 0.0,
            "station_offsets": {}
        }

    def _save_data(self):
        """Saves current data to the JSON file."""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def update(self, current_speed, panel_data):
        """Main update loop to be called every frame."""
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        # --- NEW: Smart OCR Fallback ---
        if current_speed is None:
            if self.is_tracking_offset and self.last_speed is not None:
                if self.last_speed <= 3:
                    # We were almost stopped, and now Tesseract can't read the '0'.
                    # Safely assume we have come to a complete stop.
                    current_speed = 0
                else:
                    # We dropped a frame at high speed. Reuse the last known speed
                    # so our distance integration doesn't lose miles!
                    current_speed = self.last_speed
            else:
                # Not tracking anything important, just wait for a good frame
                return

        # --- 1. Calculate Acceleration & Deceleration Rates ---
        if self.last_speed is not None and dt > 0 and current_speed > 0:
            speed_diff = current_speed - self.last_speed
            rate = speed_diff / dt  # mph per second

            # Filter out tiny micro-fluctuations or impossible physics spikes
            if 0.5 < rate < 10.0:
                self.accel_samples.append(rate)
                if len(self.accel_samples) > 50: self.accel_samples.pop(0)
                self.data["acceleration_rate_mph_s"] = round(sum(self.accel_samples) / len(self.accel_samples), 2)

            elif -10.0 < rate < -0.5:
                self.decel_samples.append(abs(rate))
                if len(self.decel_samples) > 50: self.decel_samples.pop(0)
                self.data["deceleration_rate_mph_s"] = round(sum(self.decel_samples) / len(self.decel_samples), 2)

        self.last_speed = current_speed

        # --- 2. Track Station Offsets ---
        ui_distance = panel_data.get("distance")
        station_name = panel_data.get("next_stop")
        platform = panel_data.get("platform")

        # Trigger: UI Distance drops to 0.0, but the train is still moving
        if ui_distance == 0.0 and current_speed > 0:
            if not self.is_tracking_offset and station_name and platform:
                print(f"\n[Calibrator] Entered platform! Tracking offset for {station_name} - Plt {platform}...")
                self.is_tracking_offset = True
                self.current_offset = 0.0
                self.tracked_station = station_name
                self.tracked_platform = platform

        # Integration: Accumulate distance while moving
        if self.is_tracking_offset:
            distance_this_frame = (current_speed / 3600.0) * dt
            self.current_offset += distance_this_frame

            # Completion: Train comes to a full stop
            if current_speed == 0:
                key = f"{self.tracked_station}_Plt{self.tracked_platform}"
                print(f"[Calibrator] Stopped. Recorded {key} : {self.current_offset:.5f} miles.")

                # Save to database
                self.data["station_offsets"][key] = round(self.current_offset, 5)
                self._save_data()

                # Reset for the next station
                self.is_tracking_offset = False