# controller.py
import pydirectinput
import time

class TrainController:
    def __init__(self):
        self.current_key = None
        # Failsafe: moving the mouse to a corner of the screen aborts pydirectinput
        pydirectinput.FAILSAFE = True

    def cruise_control(self, target_speed, limit_speed):
        """Matches the train's target speed (green dial) to the track speed limit."""
        if target_speed is None or limit_speed is None:
            self.release_all()
            return

        # If the dial is set lower than the limit, press W to increase target speed
        if target_speed < limit_speed - 2:
            self._press_key('w', 's')

        # If the dial is set higher than the limit, press S to decrease target speed
        elif target_speed > limit_speed + 2:
            self._press_key('s', 'w')

        # If the dial matches the limit, release all keys
        else:
            self.release_all()

    def _press_key(self, key_to_press, key_to_release):
        """Taps the key to prevent the dial from spinning too fast and overshooting."""
        # 1. Release the opposite key just in case it was stuck
        pydirectinput.keyUp(key_to_release)

        # 2. Tap the desired key instead of holding it down
        pydirectinput.press(key_to_press)

        # 3. Add a tiny delay so the Roblox engine has time to register the tap
        # If it still overshoots, increase this to 0.1. If it's too slow, decrease to 0.02.
        time.sleep(0.05)

        # Because we are tapping and not holding, we don't need to lock the state
        self.current_key = None

    def release_all(self):
        """Ensure keys don't get stuck."""
        if self.current_key is not None:
            pydirectinput.keyUp('w')
            pydirectinput.keyUp('s')
            self.current_key = None