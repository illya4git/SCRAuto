# controller.py
import pydirectinput
import time

class TrainController:
    def __init__(self):
        self.current_key = None
        # Failsafe: moving the mouse to a corner of the screen aborts pydirectinput
        pydirectinput.FAILSAFE = True

    def apply_throttle(self, duration):
        """Holds 'W' to accelerate for a specific fraction of a second."""
        self._burst_key('w', 's', duration)

    def apply_brake(self, duration):
        """Holds 'S' to brake for a specific fraction of a second."""
        self._burst_key('s', 'w', duration)

    def _burst_key(self, key_to_press, key_to_release, duration):
        """Handles the low-level key events."""
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
        time.sleep(0.02)

    def release_all(self):
        """Ensure keys don't get stuck."""
        if self.current_key is not None:
            pydirectinput.keyUp('w')
            pydirectinput.keyUp('s')
            self.current_key = None

    def acknowledge_aws(self):
        pydirectinput.press('q')
        time.sleep(0.05)

    def release_spad(self):
        pydirectinput.press('q')
        time.sleep(0.1)

    def toggle_doors(self):
        pydirectinput.press('t')
        time.sleep(0.1)

    def click_screen(self, x, y):
        pydirectinput.moveTo(x, y)
        time.sleep(0.05)
        pydirectinput.click()
        time.sleep(0.1)