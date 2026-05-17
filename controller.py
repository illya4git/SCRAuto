# controller.py
import pydirectinput
import time


class TrainController:
    def __init__(self):
        self.current_key = None
        # Failsafe: moving the mouse to a corner of the screen aborts pydirectinput
        pydirectinput.FAILSAFE = True

        # Tuning parameter: How many seconds to hold the key per 1 MPH difference.
        # If moving the dial from 0 to 100 takes roughly 1.5 seconds, this should be ~0.015.
        self.hold_time_per_mph = 0.015

    def cruise_control(self, target_speed, limit_speed):
        """Matches the train's target speed (green dial) to the track speed limit."""
        if target_speed is None or limit_speed is None:
            self.release_all()
            return

        diff = target_speed - limit_speed

        # If the dial is within 2 mph of the target, do nothing
        if abs(diff) <= 2:
            self.release_all()
            return

        # Calculate proportional hold time
        hold_time = abs(diff) * self.hold_time_per_mph

        # Cap the hold time so we don't block the vision loop for too long (max 0.4 seconds)
        hold_time = min(hold_time, 0.4)

        if diff > 0:
            # Dial is higher than limit -> BRAKE (Press S)
            self._burst_key('s', 'w', hold_time)
        else:
            # Dial is lower than limit -> ACCELERATE (Press W)
            self._burst_key('w', 's', hold_time)

    def _burst_key(self, key_to_press, key_to_release, duration):
        """Holds a key for a precise fraction of a second to move the dial rapidly."""
        # 1. Release the opposite key just in case it was stuck
        if self.current_key == key_to_release:
            pydirectinput.keyUp(key_to_release)
            self.current_key = None

        # 2. Hold the target key
        pydirectinput.keyDown(key_to_press)
        self.current_key = key_to_press

        # 3. Wait for the proportional amount of time
        time.sleep(duration)

        # 4. Release the key
        pydirectinput.keyUp(key_to_press)
        self.current_key = None

        # Tiny sleep to ensure the game engine registers the release
        time.sleep(0.02)

    def release_all(self):
        """Ensure keys don't get stuck."""
        if self.current_key is not None:
            pydirectinput.keyUp('w')
            pydirectinput.keyUp('s')
            self.current_key = None

    def acknowledge_aws(self):
        """Presses Q to accept the AWS warning."""
        pydirectinput.press('q')
        time.sleep(0.05)

    def release_spad(self):
        """Presses Q to release the SPAD emergency brake."""
        pydirectinput.press('q')
        # A small sleep ensures we don't spam the key too fast in the main loop
        time.sleep(0.1)