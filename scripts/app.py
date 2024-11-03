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


TELNET: Final[Telnet] = Telnet()  # noqa: S312
TELNET.set_option_negotiation_callback(negotiation)
IP: Final[str] = "127.0.0.1"
PORT: Final[int] = 9105
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
    MOVE_UP_DOWN: tuple[str, int] = ("DO LDEPART", 1)


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


def send_command(command: tuple[str, int], arg: JointState | float = 0) -> None:
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
    time.sleep(0.5)


# def shift_point(from_point_name: str, new_point_name: str, x: float, y: float, z: float) -> None:
#     TELNET.write(f"POINT {new_point_name} = SHIFT({from_point_name} by {x}, {y}, {z})".encode() + b"\r\n")
#     TELNET.write(ENTER)


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


connect_to_robot()
status: dict[KawasakiStatus, bool] = get_robot_status()

start_corner: JointState = JointState(-52.095, -6.450, -59.472, -118.577, 52.309, 61.888, "start_corner")
end_corner: JointState = JointState(52.095, -6.450, -59.472, -118.577, 52.309, 61.888, "end_corner")

test_corner: JointState = start_corner.shift_point(100, 0, 0, "test_corner")


if status[KawasakiStatus.TEACH_MODE]:
    raise KawasakiStatusError(KawasakiStatus.TEACH_MODE.name)
if status[KawasakiStatus.ERROR]:
    send_command(KawasakiCommand.RESET)
if not status[KawasakiStatus.MOTOR_POWERED]:
    send_command(KawasakiCommand.MOTOR_ON)

# send_command(KawasakiCommand.HOME)
# send_command(KawasakiCommand.MOVE_TO_POINT, start_corner)
# send_command(KawasakiCommand.MOVE_TO_POINT, end_corner)
