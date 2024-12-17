from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from re import Pattern, findall, split, sub
from re import compile as regex_compile
from selectors import EVENT_READ, SelectSelector
from socket import create_connection, socket
from time import sleep
from typing import NamedTuple


class Status(Enum):
    """
    Robot status.

    ERROR: The robot is in an error state.
    MOTOR_POWERED: The robot is powered on.
    REPEAT_MODE: The robot is in repeat mode.
    TEACH_MODE: The robot is in teach mode.
    TEACH_LOCK: The robot is locked in teach mode.
    BUSY: The robot is busy.
    HOLD: The robot is on hold.
    CONTINUOUS_PATH: The robot is in continuous path mode.
    REPEAT_ONCE: The robot is in repeat once mode.
    STEP_ONCE: The robot is in single step mode.
    """

    ERROR = auto()
    MOTOR_POWERED = auto()
    REPEAT_MODE = auto()
    TEACH_MODE = auto()
    TEACH_LOCK = auto()
    BUSY = auto()
    HOLD = auto()
    CONTINUOUS_PATH = auto()
    REPEAT_ONCE = auto()
    STEP_ONCE = auto()


@dataclass(frozen=True)
class Command:
    """
    Robot commands.

    RESET: Reset the robot.
    MOTOR_ON: Turn on the motor.
    MOTOR_OFF: Turn off the motor.
    HOME: Move the robot to the home position.
    MOVE_TO_POINT: Move the robot to a point.
    PICKUP: Move the robot to the pickup position.
    PUTDOWN: Move the robot to the putdown position.
    EXECUTE_PROG: Execute a program.
    CONTINUOUS_PATH_ON: Turn on continuous path mode.
    CONTINUOUS_PATH_OFF: Turn off continuous path mode.
    REPEAT_ONCE_OFF: Turn off repeat once mode.
    REPEAT_ONCE_ON: Turn on repeat once mode.
    STEP_ONCE_OFF: Turn off single step mode.
    STEP_ONCE_ON: Turn on single step mode.
    POINT: Add point to robot memory.

    """

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
    ADD_POINT: tuple[str, int] = ("POINT", 3)


@dataclass(frozen=True)
class TelnetFlag:
    IAC: bytes = bytes([255])
    DONT: bytes = bytes([254])
    DO: bytes = bytes([253])
    WONT: bytes = bytes([252])
    WILL: bytes = bytes([251])
    SB: bytes = bytes([250])
    GA: bytes = bytes([249])
    EL: bytes = bytes([248])
    EC: bytes = bytes([247])
    AYT: bytes = bytes([246])
    AO: bytes = bytes([245])
    IP: bytes = bytes([244])
    BRK: bytes = bytes([243])
    DM: bytes = bytes([242])
    NOP: bytes = bytes([241])
    SE: bytes = bytes([240])
    TTYPE: bytes = bytes([24])
    ECHO: bytes = bytes([1])
    NULL: bytes = bytes([0])


class Cartesian(NamedTuple):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    o: float = 0.0
    a: float = 0.0
    t: float = 0.0


class Point:
    def __init__(self, name: str, point: Cartesian) -> None:
        self.name: str = name
        self.x: float = round(point.x, 3)
        self.y: float = round(point.y, 3)
        self.z: float = round(point.z, 3)
        self.o: float = round(point.o, 3)
        self.a: float = round(point.a, 3)
        self.t: float = round(point.t, 3)

    def shift(self, name: str, shift: Cartesian) -> "Point":
        return Point(name, Cartesian(self.x + shift.x, self.y + shift.y, self.z + shift.z, self.o + shift.o, self.a + shift.a, self.t + shift.t))

    def __str__(self) -> str:
        return f"{self.x},{self.y},{self.z},{self.o},{self.a},{self.t}"


class Connection:
    def __init__(self, host: str, show_dialog: Callable[[str], None]) -> None:
        self.__telnet_selector: type = SelectSelector
        self.__dialog: Callable[[str], None] = show_dialog
        self.__host: str = host.split("/")[0]
        self.__port: int = int(host.split("/")[1])
        self.__raw_queue: bytes = b""
        self.__raw_queue_index: int = 0
        self.__cooked_queue: bytes = b""
        self.__end_of_file: bool = False
        self.__iac_sequence: bytes = b""
        self.__subnegotiation: bool = False
        self.__subnegotiation_data_queue: bytes = b""
        self.__socket: socket = socket()
        self.__logged_in: bool = False

    def login(self, username: str = "as") -> None:
        if self.__logged_in:
            return
        self.__socket = create_connection((self.__host, self.__port))
        self.read_until_match("login:")
        self.write(username)
        self.read_until_match(">")
        self.__logged_in = True
        self.initialize()
        self.__dialog("Connected and logged in!")

    def initialize(self) -> None:
        if not self.__logged_in:
            return
        status: dict[Status, bool] = self.status()
        if status[Status.ERROR]:
            self.send(Command.RESET)
        if status[Status.CONTINUOUS_PATH]:
            self.send(Command.CONTINUOUS_PATH_OFF)
        if status[Status.REPEAT_ONCE]:
            self.send(Command.REPEAT_ONCE_ON)
        if status[Status.STEP_ONCE]:
            self.send(Command.STEP_ONCE_OFF)
        if not status[Status.MOTOR_POWERED]:
            self.send(Command.MOTOR_ON)
        if status[Status.TEACH_MODE] or status[Status.TEACH_LOCK] or status[Status.HOLD] or not status[Status.REPEAT_MODE]:
            self.__dialog("Robot is in an invalid state!")

    def status(self) -> dict[Status, bool]:
        self.write("SWITCH")
        message: str = self.read_until_match("Press SPACE key to continue").split("SWITCH\r")[1]
        split_pattern: Pattern[str] = regex_compile(r" ON| OFF")
        replace_pattern: Pattern[str] = regex_compile(r"[ \n*\r]")
        raw_data: list[str] = [sub(replace_pattern, "", s) for s in split(pattern=split_pattern, string=message)][:-1]
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, findall(split_pattern, string=message), strict=True)}
        self.write("\n")
        self.clear_queue()
        return {
            Status.BUSY: status_data["CS"],
            Status.ERROR: status_data["ERROR"],
            Status.MOTOR_POWERED: status_data["POWER"],
            Status.REPEAT_MODE: status_data["REPEAT"],
            Status.TEACH_MODE: not status_data["REPEAT"],
            Status.TEACH_LOCK: status_data["TEACH_LOCK"],
            Status.HOLD: not status_data["RUN"],
            Status.CONTINUOUS_PATH: status_data["CP"],
            Status.REPEAT_ONCE: status_data["REP_ONCE"],
            Status.STEP_ONCE: status_data["STP_ONCE"],
        }

    def send(self, command: tuple[str, int], arg: Point | str | None = None) -> None:
        if not self.__logged_in:
            return
        match command[1]:
            case 0:
                self.write(command[0])
                self.read_until_match(">")
            case 1:
                if type(arg) is Point:
                    self.write(command[0] + f" {arg.name}")
                else:
                    self.write(command[0])
                self.read_until_match("DO motion completed.")
                sleep(0.3)
            case 2:
                self.write(command[0] + f" {arg}")
                self.read_until_match("Program completed.")
            case 3:
                if type(arg) is Point:
                    self.write(f"POINT {arg.name}")
                    self.write(str(arg))
                    self.write("\n")
                    self.clear_queue()
        sleep(0.1)

    def close(self) -> None:
        self.__raw_queue: bytes = b""
        self.__raw_queue_index: int = 0
        self.__cooked_queue: bytes = b""
        self.__end_of_file: bool = False
        self.__iac_sequence: bytes = b""
        self.__subnegotiation: bool = False
        self.__subnegotiation_data_queue: bytes = b""
        if self.__logged_in:
            self.write("signal -2011")
            self.__dialog("Logged out and disconnected!")
            self.__socket.close()
            self.__logged_in = False

    def read_until_match(self, match: str) -> str:
        match_encoded: bytes = match.encode("ascii")
        self.__raw_queue_process()
        with self.__telnet_selector() as selector:
            selector.register(self.__socket_descriptor(), EVENT_READ)
            while not self.__end_of_file and selector.select():
                self.__raw_queue_fill()
                self.__raw_queue_process()
                i: int = self.__cooked_queue.find(match_encoded)
                if i >= 0:
                    i += len(match_encoded)
                    buffer: bytes = self.__cooked_queue[:i]
                    self.__cooked_queue = self.__cooked_queue[i:]
                    return buffer.decode("ascii")
        raise EOFError

    def write_program(self, program: str, name: str) -> None:
        if not self.__logged_in:
            return
        self.clear_queue()
        self.write("KILL")
        self.write("1")
        self.write("\n")
        self.write(f"EDIT {name}, 1")
        for line in program.splitlines():
            self.write(line)
        self.write("E")
        self.write("\n")
        sleep(0.1)

    def write(self, buffer: str) -> None:
        buffer_encoded: bytes = buffer.encode("ascii") + b"\r\n"
        if TelnetFlag.IAC in buffer_encoded:
            buffer_encoded = buffer_encoded.replace(TelnetFlag.IAC, TelnetFlag.IAC + TelnetFlag.IAC)
        self.__socket.sendall(buffer_encoded)

    def clear_queue(self) -> None:
        self.__raw_queue_fill()
        self.__raw_queue_process()
        self.__raw_queue = b""
        self.__cooked_queue = b""
        self.__raw_queue_index = 0

    def __raw_queue_process(self) -> None:
        buffer: list[bytes] = [b"", b""]
        while self.__raw_queue:
            char: bytes = self.__raw_queue_get_char()
            if not self.__iac_sequence:
                if char != TelnetFlag.IAC and char not in {TelnetFlag.NULL, b"\021"}:
                    buffer[self.__subnegotiation] += char
                    continue
                self.__iac_sequence += char
                continue
            if len(self.__iac_sequence) == 1:
                if char in {TelnetFlag.DO, TelnetFlag.DONT, TelnetFlag.WILL, TelnetFlag.WONT}:
                    self.__iac_sequence += char
                    continue
                self.__iac_sequence = b""
                match char:
                    case TelnetFlag.IAC:
                        buffer[self.__subnegotiation] += char
                    case TelnetFlag.SB:
                        self.__subnegotiation = True
                        self.__subnegotiation_data_queue = b""
                    case TelnetFlag.SE:
                        self.__subnegotiation = False
                        self.__subnegotiation_data_queue += buffer[1]
                        buffer[1] = b""
                self.__negotiate(char, TelnetFlag.NULL)
                continue
            command: bytes = self.__iac_sequence[1:2]
            self.__iac_sequence = b""
            if command in {TelnetFlag.DO, TelnetFlag.DONT} or command in {TelnetFlag.WILL, TelnetFlag.WONT}:
                self.__negotiate(command, char)
        self.__cooked_queue += buffer[0]
        self.__subnegotiation_data_queue += buffer[1]

    def __raw_queue_get_char(self) -> bytes:
        if not self.__raw_queue:
            self.__raw_queue_fill()
            if self.__end_of_file:
                raise EOFError
        char: bytes = self.__raw_queue[self.__raw_queue_index : self.__raw_queue_index + 1]
        self.__raw_queue_index += 1
        if self.__raw_queue_index >= len(self.__raw_queue):
            self.__raw_queue = b""
            self.__raw_queue_index = 0
        return char

    def __raw_queue_fill(self) -> None:
        if self.__raw_queue_index >= len(self.__raw_queue):
            self.__raw_queue = b""
            self.__raw_queue_index = 0
        buffer: bytes = self.__socket.recv(50)
        self.__end_of_file = not buffer
        self.__raw_queue += buffer

    def __negotiate(self, command: bytes, option: bytes) -> None:
        match (command, option):
            case (TelnetFlag.WILL, TelnetFlag.ECHO):
                self.__socket.sendall(TelnetFlag.IAC + TelnetFlag.DO + option)
            case (TelnetFlag.DO, TelnetFlag.TTYPE):
                self.__socket.sendall(TelnetFlag.IAC + TelnetFlag.WILL + TelnetFlag.TTYPE)
            case (TelnetFlag.SB, _):
                self.__socket.sendall(
                    TelnetFlag.IAC + TelnetFlag.SB + TelnetFlag.TTYPE + TelnetFlag.NULL + b"VT100" + TelnetFlag.NULL + TelnetFlag.IAC + TelnetFlag.SE,
                )

    def __socket_descriptor(self) -> int:
        return self.__socket.fileno()


if __name__ == "__main__":
    from random import uniform

    def dialog(msg: str) -> None:
        print(msg)

    robot = Connection("127.0.0.1/9105", dialog)
    robot.login()

    base = Point("A", Cartesian(91.362, 554.329, -193.894, -137.238, 179.217, -5.03))
    b: Point = base.shift("B", Cartesian(x=20))
    c: Point = base.shift("C", Cartesian(x=-20, z=round(uniform(-100, 100), 0)))
    robot.send(Command.ADD_POINT, b)
    robot.send(Command.ADD_POINT, c)
    robot.close()
