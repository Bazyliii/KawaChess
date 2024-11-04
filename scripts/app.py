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


import time
from dataclasses import dataclass
from enum import Enum
from socket import socket
from telnetlib import DO, ECHO, IAC, SB, SE, TTYPE, WILL, Telnet  # noqa: S401
from typing import Final


def negotiation(socket: socket, cmd: bytes, opt: bytes) -> None:
    if cmd == WILL and opt == ECHO:
        socket.sendall(IAC + DO + opt)
    elif cmd == DO and opt == TTYPE:
        socket.sendall(IAC + WILL + TTYPE)
    elif cmd == SB:
        socket.sendall(IAC + SB + TTYPE + b"\00" + b"VT100" + b"\00" + IAC + SE)


SIMULATION: Final[bool] = False
TELNET: Final[Telnet] = Telnet()  # noqa: S312
TELNET.set_option_negotiation_callback(negotiation)
if SIMULATION:
    IP: Final[str] = "127.0.0.1"
    PORT: Final[int] = 9105
else:
    IP: Final[str] = "192.168.1.155"
    PORT: Final[int] = 23
USER: Final[str] = "as"
TIMEOUT: Final[int] = 5
SPEED: Final[int] = 100
ENTER: Final[bytes] = b"\n\r\n"
ENDLINE: Final[bytes] = b"\r\n"
ENCODING: Final[str] = "ascii"


@dataclass
class KawasakiCommand:
    RESET: tuple[str, int] = ("ERESET", 0)
    MOTOR_ON: tuple[str, int] = ("ZPOW ON", 0)
    MOTOR_OFF: tuple[str, int] = ("ZPOW OFF", 0)
    HOME: tuple[str, int] = ("DO HOME", 1)
    MOVE_TO_POINT: tuple[str, int] = ("DO HMOVE", 1)
    PICKUP: tuple[str, int] = ("DO LDEPART 80", 1)
    PUTDOWN: tuple[str, int] = ("DO LDEPART -80", 1)
    EXECUTE_PROG: tuple[str, int] = ("EXE", 2)

class KawasakiStatus(Enum):
    ERROR = 0
    MOTOR_POWERED = 1
    REPEAT_MODE = 2
    TEACH_MODE = 3
    BUSY = 4


class KawasakiStatusError(Exception):
    pass


class JointState:
    def __init__(self, jt1: float, jt2: float, jt3: float, jt4: float, jt5: float, jt6: float, name: str) -> None:  # noqa: PLR0917 PLR0913
        self.jt1: float = jt1
        self.jt2: float = jt2
        self.jt3: float = jt3
        self.jt4: float = jt4
        self.jt5: float = jt5
        self.jt6: float = jt6
        self.name: str = name
        self.create_joint_point()
        self.X, self.Y, self.Z, self.O, self.A, self.T = map(float, self.translate_joint_to_cartesian()[:6])

    def __bytes__(self) -> bytes:
        return f"{self.jt1},{self.jt2},{self.jt3},{self.jt4},{self.jt5},{self.jt6}".encode(ENCODING)

    def create_joint_point(self) -> None:
        TELNET.write(f"POINT #{self.name}".encode(ENCODING) + ENDLINE)
        TELNET.write(bytes(self))
        TELNET.write(ENTER)

    def translate_joint_to_cartesian(self) -> list[float]:
        TELNET.write(f"POINT {self.name}=#{self.name}".encode(ENCODING) + ENDLINE)
        time.sleep(0.1)
        x: list[float] = [float(i) for i in filter(None, TELNET.read_very_eager().decode(ENCODING).split(f"{self.name}=#{self.name}")[1].splitlines()[2].split(" "))]
        TELNET.write(ENTER)
        return x

    def shift_point(self, x: float, y: float, z: float, name: str) -> "JointState":
        TELNET.write(f"POINT {name} = SHIFT({self.name} by {x},{y},{z})".encode(ENCODING) + ENDLINE)
        TELNET.write(ENTER)
        TELNET.write(f"POINT #{name}={name}".encode(ENCODING) + ENDLINE)
        time.sleep(0.1)
        jt: list[float] = [float(i) for i in filter(None, TELNET.read_very_eager().decode(ENCODING).split(f"#{name}={name}")[1].splitlines()[2].split(" "))]
        TELNET.write(ENTER)
        return JointState(jt[0], jt[1], jt[2], jt[3], jt[4], jt[5], name)


def connect_to_robot() -> None:
    TELNET.open(IP, PORT, TIMEOUT)
    _ = TELNET.read_until(b"login: ")
    TELNET.write(USER.encode(ENCODING) + ENDLINE)
    _ = TELNET.read_until(b">")


def send_command(command: tuple[str, int], arg: JointState | str | None = None) -> None:
    command_encoded: bytes = command[0].encode(ENCODING)
    match command[1]:
        case 0:
            TELNET.write(command_encoded + ENDLINE)
            _ = TELNET.read_until(b">")
        case 1:
            if type(arg) is JointState:
                TELNET.write(command_encoded + f" #{arg.name}".encode(ENCODING) + ENDLINE)
            else:
                TELNET.write(command_encoded + ENDLINE)
            _ = TELNET.read_until(b"DO motion completed.")
        case 2:
            TELNET.write(command_encoded + f" {arg}".encode(ENCODING) + ENDLINE)
            _ = TELNET.read_until(b"Program completed.")
    time.sleep(0.5)

def get_robot_status() -> dict[KawasakiStatus, bool]:
    TELNET.write(b"STATUS\r\n")
    raw_status: str = TELNET.read_until(b">").decode(ENCODING).split("STATUS\r")[1]
    return {
        KawasakiStatus.ERROR: "error" in raw_status,
        KawasakiStatus.MOTOR_POWERED: "Motor power OFF" not in raw_status,
        KawasakiStatus.REPEAT_MODE: "REPEAT mode" in raw_status,
        KawasakiStatus.TEACH_MODE: "TEACH mode" in raw_status,
        KawasakiStatus.BUSY: "CYCLE START ON" in raw_status,
    }


def write_program_to_robot(program: str, name: str) -> None:
    TELNET.write(b"KILL" + ENDLINE)
    TELNET.write(b"1" + ENDLINE)
    TELNET.write(ENTER)
    TELNET.write(f"DELETE {name}".encode(ENCODING) + ENDLINE)
    TELNET.write(b"1" + ENDLINE)
    TELNET.write(ENTER)
    TELNET.write(f"EDIT {name}, 1".encode(ENCODING) + ENDLINE)
    for line in program.splitlines():
        TELNET.write(line.encode(ENCODING) + ENDLINE)
        # TELNET.write(ENTER)
    TELNET.write(b"E")
    TELNET.write(ENTER)
    time.sleep(0.1)

connect_to_robot()
status: dict[KawasakiStatus, bool] = get_robot_status()

if status[KawasakiStatus.TEACH_MODE]:
    raise KawasakiStatusError(KawasakiStatus.TEACH_MODE.name)
if status[KawasakiStatus.ERROR]:
    send_command(KawasakiCommand.RESET)
if not status[KawasakiStatus.MOTOR_POWERED]:
    send_command(KawasakiCommand.MOTOR_ON)

prog: str = """
HOME\n
HMOVE left_top_corner\n
HMOVE h8\n
HMOVE a8\n
HMOVE b4\n
HMOVE d3\n
HMOVE d1\n
HMOVE d6\n
HMOVE f4\n
HMOVE g5\n
HMOVE a1\n
"""

write_program_to_robot(prog, "temp_program")

left_top_corner: JointState = JointState(19.175, 34.457, -137.455, 2.404, -8.782, -69.342, "left_top_corner")
right_top_corner: JointState = left_top_corner.shift_point(-280, 0, 0, "right_top_corner")
right_bot_corner: JointState = right_top_corner.shift_point(0, 280, 0, "right_bot_corner")
left_bot_corner: JointState = right_bot_corner.shift_point(280, 0, 0, "left_bot_corner")


def calculate_chessboard_point_to_move(chessboard_uci: str) -> JointState:
    x: int = ord(chessboard_uci[0]) - ord("a")
    y: int = int(chessboard_uci[1]) - 1
    return left_top_corner.shift_point(x * -40, y * 40, 0, chessboard_uci)

moves: list[str] = [
    "h8",
    "a8",
    "b4",
    "d3",
    "d1",
    "d6",
    "f4",
    "g5",
    "a1", 
]

for move in moves:
    calculate_chessboard_point_to_move(move)

send_command(KawasakiCommand.EXECUTE_PROG, "temp_program")
# send_command(KawasakiCommand.HOME)
# send_command(KawasakiCommand.MOVE_TO_POINT, left_top_corner)
# send_command(KawasakiCommand.PICKUP)
# send_command(KawasakiCommand.PUTDOWN)
# for move in moves:
#     send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move(move))
# send_command(KawasakiCommand.MOTOR_OFF)
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("h8"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("a8"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("b4"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("d3"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("d1"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("d6"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("f4"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("g5"))
# send_command(KawasakiCommand.MOVE_TO_POINT, calculate_chessboard_point_to_move("a1"))

# send_command(KawasakiCommand.HOME)
# for _ in range(3):
#     send_command(KawasakiCommand.MOVE_TO_POINT, left_top_corner)
#     send_command(KawasakiCommand.MOVE_TO_POINT, right_top_corner)
#     send_command(KawasakiCommand.MOVE_TO_POINT, right_bot_corner)
#     send_command(KawasakiCommand.MOVE_TO_POINT, left_bot_corner)



