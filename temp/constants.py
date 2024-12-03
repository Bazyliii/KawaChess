from typing import Final

ERROR = 0
MOTOR_POWERED = 1
REPEAT_MODE = 2
TEACH_MODE = 3
TEACH_LOCK = 4
BUSY = 5
HOLD = 6
CONTINUOUS_PATH = 7
REPEAT_ONCE = 8
STEP_ONCE = 9


RESET: Final[tuple[str, int]] = ("ERESET", 0)
MOTOR_ON: Final[tuple[str, int]] = ("ZPOW ON", 0)
MOTOR_OFF: Final[tuple[str, int]] = ("ZPOW OFF", 0)
HOME: Final[tuple[str, int]] = ("DO HOME", 1)
MOVE_TO_POINT: Final[tuple[str, int]] = ("DO HMOVE", 1)
PICKUP: Final[tuple[str, int]] = ("DO LDEPART 80", 1)
PUTDOWN: Final[tuple[str, int]] = ("DO LDEPART -80", 1)
EXECUTE_PROG: Final[tuple[str, int]] = ("EXE", 2)
CONTINUOUS_PATH_ON: Final[tuple[str, int]] = ("CP ON", 0)
CONTINUOUS_PATH_OFF: Final[tuple[str, int]] = ("CP OFF", 0)
REPEAT_ONCE_OFF: Final[tuple[str, int]] = ("REP_ONCE OFF", 0)
REPEAT_ONCE_ON: Final[tuple[str, int]] = ("REP_ONCE ON", 0)
STEP_ONCE_OFF: Final[tuple[str, int]] = ("STP_ONCE OFF", 0)
STEP_ONCE_ON: Final[tuple[str, int]] = ("STP_ONCE ON", 0)
