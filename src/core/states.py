from enum import Enum, auto

class AutopilotState(Enum):
    CRUISING = auto()
    BRAKING_SIGNAL = auto()
    BRAKING_STATION = auto()
    STOPPED = auto()

class StationState(Enum):
    DRIVING = auto()
    WAITING_LOADING_START = auto()
    LOADING = auto()
    CHECKING_TERMINUS = auto()
    WAITING_DEPARTURE = auto()