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


class Command(Enum):
    RESET_ERRORS = ("ERESET", 0)
    MOTOR_ON = ("ZPOW ON", 0)
    MOTOR_OFF = ("ZPOW OFF", 0)
    HOME = ("DO HOME", 1)
    MOVE_TO_POINT = ("DO HMOVE", 1)
    MOVE_UP_DOWN = ("DO LDEPART", 1)


class JointState:
    def __init__(self, jt1: float, jt2: float, jt3: float, jt4: float, jt5: float, jt6: float, point_name: str) -> None:
        self.jt1: float = jt1
        self.jt2: float = jt2
        self.jt3: float = jt3
        self.jt4: float = jt4
        self.jt5: float = jt5
        self.jt6: float = jt6
        self.point_name: str = point_name
        self.x: float
        self.y: float
        self.z: float
        self.create_joint_point()
        self.translate_joint_to_cartesian()

    def __bytes__(self) -> bytes:
        return f"{self.jt1}, {self.jt2}, {self.jt3}, {self.jt4}, {self.jt5}, {self.jt6}".encode()

    def create_joint_point(self) -> None:
        TELNET.write(f"POINT #{self.point_name}".encode() + b"\r\n")
        TELNET.write(bytes(self))
        TELNET.write(ENTER)

    def translate_joint_to_cartesian(self) -> None:
        TELNET.write(f"POINT {self.point_name}=#{self.point_name}".encode() + b"\r\n")
        TELNET.write(ENTER)

    def translate_cartesian_to_joint(self) -> None:
        TELNET.write(f"POINT #{self.point_name}={self.point_name}".encode() + b"\r\n")
        TELNET.write(ENTER)

    def shift_point(self, x: float, y: float, z: float, new_point_name: str) -> None:
        TELNET.write(f"POINT {new_point_name} = SHIFT({self.point_name} by {x}, {y}, {z})".encode() + b"\r\n")
        TELNET.write(ENTER)



def connect_to_robot() -> None:
    try:
        TELNET.open(IP, PORT, TIMEOUT)
        _ = TELNET.read_until(b"login: ", TIMEOUT)
        TELNET.write(USER.encode() + ENDLINE)
        _ = TELNET.read_until(b">", TIMEOUT)
    except ConnectionRefusedError as _:
        TELNET.close()


# def reset_errors() -> None:
#     TELNET.write(b"ERESET\r\n")
#     time.sleep(0.5)


# def motor_on() -> None:
#     TELNET.write(b"ZPOW ON\r\n")
#     time.sleep(0.5)


# def motor_off() -> None:
#     TELNET.write(b"ZPOW OFF\r\n")
#     time.sleep(0.5)

def send_command(command: Command, arg: JointState | float | None = None) -> None:
    command_encoded: bytes = command.value[0].encode()
    match command.value[1]:
        case 0:
            TELNET.write(command_encoded + ENDLINE)
        case 1:
            if type(arg) is JointState:
                TELNET.write(command_encoded + bytes(arg) + ENDLINE)
            elif type(arg) is float or int:
                TELNET.write(command_encoded + str(arg).encode() + ENDLINE)
            else:
                TELNET.write(command_encoded + ENDLINE)
            _ = TELNET.read_until(b"DO motion completed.")  # Możliwe że musi być przypisane!
        case _:
            pass
    time.sleep(0.5)


# def send_motion_command(command: str) -> None:
#     TELNET.write(command.encode() + b"\r\n")
#     _ = TELNET.read_until(b"DO motion completed.")
#     time.sleep(0.5)


# def create_joint_point(joints: JointState, point_name: str) -> None:
#     TELNET.write(f"POINT #{point_name}".encode() + b"\r\n")
#     TELNET.write(f"{joints.jt1},{joints.jt2},{joints.jt3},{joints.jt4},{joints.jt5},{joints.jt6}".encode())
#     TELNET.write(ENTER)


# def translate_joint_to_cartesian(from_point: JointState, to_point_name: str) -> None:
#     TELNET.write(f"POINT {to_point_name}=#{from_point.position_name}".encode() + b"\r\n")
#     TELNET.write(ENTER)


# def shift_point(from_point_name: str, new_point_name: str, x: float, y: float, z: float) -> None:
#     TELNET.write(f"POINT {new_point_name} = SHIFT({from_point_name} by {x}, {y}, {z})".encode() + b"\r\n")
#     TELNET.write(ENTER)


def get_robot_status() -> str:
    TELNET.write(b"STATUS\r\n")
    status: str = TELNET.read_until(b"Stepper status").decode().split(">STATUS\r")[1]
    return status


connect_to_robot()
send_command(Command.MOTOR_ON)
send_command(Command.RESET_ERRORS)



# start_corner: JointState = JointState(13.531, 44.211, -133.421, -27.616, -1.412, -118.985, "start_corner")
# send_command(Command.MOVE_TO_POINT, start_corner)

# end_corner = JointState = start_corner.shift_point(120, 0, 0, "end_corner")

# send_command(Command.MOVE_TO_POINT, start_corner)

# send_command(Command.MOTOR_ON)
# send_command(Command.MOVE_TO_POINT, start_corner)

# create_joint_point(start_corner, "Punkt_003")
# translate_joint_to_cartesian("Punkt_003", "Punkt_004")
# shift_point("Punkt_004", "Punkt_005", -280, 0, 0)
# shift_point("Punkt_005", "Punkt_006", 0, 280, 0)
# shift_point("Punkt_006", "Punkt_007", 280, 0, 0)

cmd_list: list[str] = [
    "DO HOME",
    "DO HMOVE Punkt_003",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_005",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_006",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_007",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_003",
    "DO LDEPART 80",
    "DO LDEPART -80",
]


# print(get_robot_status())
# reset_errors()
# motor_on()
# for cmd in cmd_list:
#     send_command(cmd)
# motor_off()
