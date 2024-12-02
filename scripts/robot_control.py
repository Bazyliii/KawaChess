# SPEED [0.01 -> 100] ALWAYS
# ACCURACY [0.5 -> 5000] mm ALWAYS
# ACCEL [0.01 -> 100] ALWAYS
# DECEL [0.01 -> 100] ALWAYS
# CALL [program name]               # Calling program
# WHERE 2                           # Transformation value
# WHERE 3                           # Joint value
# FREE                              # Free memory
# HOME                              # Return to home position
# DRIVE [joint], [amount], [speed]
# DRAW [x], [y], [z]                # Move in linear interpolated motion
# TDRAW [x], [y], [z]               # Draw in tool coordinate system
# PCEXECUTE [program name]          # Execute program from PC
# EXECUTE [program name]            # Execute program from robot controller
# ERESET                            # Reset errors
# ZPOW ON                           # Motor power on
# ZPOW OFF                          # Motor power off

# Left top corner 72.319 286.221 -217.559 -155.001 177.533 -174.963

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Final

from simple_telnet import SimpleTelnet

TELNET: Final[SimpleTelnet] = SimpleTelnet("192.168.1.155/23")

USER: Final[str] = "as"
SPEED: Final[int] = 100
ENTER: Final[bytes] = "\n"


@dataclass
class KawasakiCommand:
    RESET: tuple[str, int] = ("ERESET", 0)
    MOTOR_ON: tuple[str, int] = ("ZPOW ON", 0)
    MOTOR_OFF: tuple[str, int] = ("ZPOW OFF", 0)
    HOME: tuple[str, int] = ("DO HOME", 1)
    MOVE_TO_POINT: tuple[str, int] = ("DO LMOVE", 1)
    PICKUP: tuple[str, int] = ("DO LDEPART 80", 1)
    PUTDOWN: tuple[str, int] = ("DO LDEPART -80", 1)
    EXECUTE_PROG: tuple[str, int] = ("EXE", 2)
    CONTINUOUS_PATH_ON: tuple[str, int] = ("CP ON", 0)
    CONTINUOUS_PATH_OFF: tuple[str, int] = ("CP OFF", 0)
    REPEAT_ONCE_OFF: tuple[str, int] = ("REP_ONCE OFF", 0)
    REPEAT_ONCE_ON: tuple[str, int] = ("REP_ONCE ON", 0)
    STEP_ONCE_OFF: tuple[str, int] = ("STP_ONCE OFF", 0)
    STEP_ONCE_ON: tuple[str, int] = ("STP_ONCE ON", 0)


class KawasakiStatus(Enum):
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


class KawasakiStatusError(Exception):
    pass


class CartesianState:
    def __init__(self, name: str, x: float, y: float, z: float, o: float, a: float, t: float) -> None:
        self.name: str = name
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.o: float = o
        self.a: float = a
        self.t: float = t
        self.__create_point()

    def __create_point(self) -> "CartesianState":
        TELNET.write(f"POINT {self.name}")
        TELNET.write(f"{self.x},{self.y},{self.z},{self.o},{self.a},{self.t}")
        TELNET.write(ENTER)
        TELNET.clear_queue()

    def shift_point(self, name: str, x: float, y: float, z: float) -> "CartesianState":
        TELNET.write(f"POINT {name} = SHIFT({self.name} by {x},{y},{z})")
        TELNET.write(ENTER)
        xx = list(map(float, filter(None, TELNET.read_until_match("Change?").splitlines()[-2].split(" "))))[:6]
        return CartesianState(name, xx[0], xx[1], xx[2], xx[3], xx[4], xx[5])

def connect_to_robot() -> None:
    _ = TELNET.read_until_match("login: ")
    TELNET.write(USER)
    _ = TELNET.read_until_match(">")


def send_command(command: tuple[str, int], arg: CartesianState | str | None = None) -> None:
    match command[1]:
        case 0:
            TELNET.write(command[0])
            _ = TELNET.read_until_match(">")
        case 1:
            if type(arg) is CartesianState:
                TELNET.write(command[0] + f" {arg.name}")
            else:
                TELNET.write(command[0])
            _ = TELNET.read_until_match("DO motion completed.")
        case 2:
            TELNET.write(command[0] + f" {arg}")
            _ = TELNET.read_until_match("Program completed.")
    time.sleep(0.5)

def write_program_to_robot(program: str, name: str) -> None:
    TELNET.write("KILL")
    TELNET.write("1")
    TELNET.write(ENTER)
    TELNET.write(f"DELETE {name}")
    TELNET.write("1")
    TELNET.write(ENTER)
    TELNET.write(f"EDIT {name}, 1")
    for line in program.splitlines():
        TELNET.write(line)
    TELNET.write("E")
    TELNET.write(ENTER)
    time.sleep(0.1)


def get_robot_status() -> dict[KawasakiStatus, bool]:
    TELNET.write("SWITCH")
    message: str = TELNET.read_until_match("Press SPACE key to continue").split("SWITCH\r")[1]
    raw_data = [s.replace(" ", "").replace("\n", "").replace("*", "").replace("\r", "") for s in re.split(" ON| OFF", message)]
    raw_data.pop()
    status_data = {key: value == " ON" for key, value in zip(raw_data, re.findall(" ON| OFF", message), strict=False)}
    time.sleep(0.1)
    TELNET.write(ENTER)
    return {
        KawasakiStatus.BUSY: status_data["CS"],
        KawasakiStatus.ERROR: status_data["ERROR"],
        KawasakiStatus.MOTOR_POWERED: status_data["POWER"],
        KawasakiStatus.REPEAT_MODE: status_data["REPEAT"],
        KawasakiStatus.TEACH_MODE: not status_data["REPEAT"],
        KawasakiStatus.TEACH_LOCK: status_data["TEACH_LOCK"],
        KawasakiStatus.HOLD: not status_data["RUN"],
        KawasakiStatus.CONTINUOUS_PATH: status_data["CP"],
        KawasakiStatus.REPEAT_ONCE: status_data["REP_ONCE"],
        KawasakiStatus.STEP_ONCE: status_data["STP_ONCE"],
    }


connect_to_robot()
status: dict[KawasakiStatus, bool] = get_robot_status()

if status[KawasakiStatus.TEACH_MODE]:
    raise KawasakiStatusError(KawasakiStatus.TEACH_MODE.name)
if status[KawasakiStatus.TEACH_LOCK]:
    raise KawasakiStatusError(KawasakiStatus.TEACH_LOCK.name)
if status[KawasakiStatus.REPEAT_ONCE]:
    send_command(KawasakiCommand.REPEAT_ONCE_OFF)
if status[KawasakiStatus.STEP_ONCE]:
    send_command(KawasakiCommand.STEP_ONCE_OFF)
if status[KawasakiStatus.HOLD]:
    raise KawasakiStatusError(KawasakiStatus.HOLD.name)
if status[KawasakiStatus.ERROR]:
    send_command(KawasakiCommand.RESET)
if status[KawasakiStatus.CONTINUOUS_PATH]:
    send_command(KawasakiCommand.CONTINUOUS_PATH_OFF)
if not status[KawasakiStatus.MOTOR_POWERED]:
    send_command(KawasakiCommand.MOTOR_ON)
status = get_robot_status()
if not status[KawasakiStatus.MOTOR_POWERED]:
    raise KawasakiStatusError(KawasakiStatus.MOTOR_POWERED.name)


left_top_corner: CartesianState = CartesianState("left_top_corner", 91.362, 554.329, -193.894, -137.238, 179.217, -5.03)


def calculate_chessboard_point_to_move(chessboard_uci: str, z: float = 0.0) -> CartesianState:
    x: int = ord(chessboard_uci[0]) - ord("a")
    y: int = int(chessboard_uci[1]) - 1
    return left_top_corner.shift_point(chessboard_uci, x * -40, y * -40, z)

p = False
send_command(KawasakiCommand.HOME)
while True:
    move_to: str = input("Move to: ")
    if len(move_to) == 2 and move_to[0] in "abcdefgh" and move_to[1] in "12345678":
        if p:
            send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move(move_to, 80))
        else:
            send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move(move_to))
        time.sleep(0.1)
        print("Done!")
    elif move_to == "up" and not p:
        send_command(KawasakiCommand.PICKUP)
        p = True
        time.sleep(0.1)
        print("Done!")
    elif move_to == "down" and p:
        p = False
        send_command(KawasakiCommand.PUTDOWN)
        time.sleep(0.1)
        print("Done!")
    elif move_to == "exit":
        send_command(KawasakiCommand.MOTOR_OFF)
        break
    else:
        print("Invalid move!")
