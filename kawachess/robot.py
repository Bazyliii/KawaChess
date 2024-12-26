from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address
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


class CommandType(Enum):
    CONFIG = auto()
    MOVEMENT = auto()


class Command(Enum):
    RESET = ("ERESET", CommandType.CONFIG)
    ABORT = ("ABORT", CommandType.CONFIG)
    MOTOR_ON = ("ZPOW ON", CommandType.CONFIG)
    MOTOR_OFF = ("ZPOW OFF", CommandType.CONFIG)
    CONTINUOUS_PATH_ON = ("CP ON", CommandType.CONFIG)
    CONTINUOUS_PATH_OFF = ("CP OFF", CommandType.CONFIG)
    REPEAT_ONCE_OFF = ("REP_ONCE OFF", CommandType.CONFIG)
    REPEAT_ONCE_ON = ("REP_ONCE ON", CommandType.CONFIG)
    STEP_ONCE_OFF = ("STP_ONCE OFF", CommandType.CONFIG)
    STEP_ONCE_ON = ("STP_ONCE ON", CommandType.CONFIG)
    HOME = ("DO HOME", CommandType.MOVEMENT)
    LINEAR_MOVE = ("DO LMOVE", CommandType.MOVEMENT)
    JOINT_MOVE = ("DO JMOVE", CommandType.MOVEMENT)
    HYBRID_MOVE = ("DO HMOVE", CommandType.MOVEMENT)
    PICKUP = ("DO LDEPART 80", CommandType.MOVEMENT)
    PUTDOWN = ("DO LDEPART -80", CommandType.MOVEMENT)

    @property
    def val(self) -> str:
        return self.value[0]

    @property
    def type(self) -> CommandType:
        return CommandType(self.value[1])


@dataclass(frozen=True)
class Flag:
    IAC: bytes = bytes([255])  # Interpret As Command
    DONT: bytes = bytes([254])  # Don't
    DO: bytes = bytes([253])  # Do
    WONT: bytes = bytes([252])  # Won't
    WILL: bytes = bytes([251])  # Will
    SB: bytes = bytes([250])  # Subnegotiation
    GA: bytes = bytes([249])  # Go Ahead
    EL: bytes = bytes([248])  # Erase Line
    EC: bytes = bytes([247])  # Erase Character
    AYT: bytes = bytes([246])  # Are You There
    AO: bytes = bytes([245])  # Abort Output
    IP: bytes = bytes([244])  # Interrupt Process
    BRK: bytes = bytes([243])  # Break
    DM: bytes = bytes([242])  # Data Mark
    NOP: bytes = bytes([241])  # No Operation
    SE: bytes = bytes([240])  # End of Subnegotiation
    SUB: bytes = bytes([26])  # Substitute
    TTYPE: bytes = bytes([24])  # Terminal Type
    ETB: bytes = bytes([23])  # End of Transmission Block
    STX: bytes = bytes([2])  # Start of Transmission Block
    ECHO: bytes = bytes([1])  # Echo
    NULL: bytes = bytes([0])  # Null


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
        self.__x: float = round(point.x, 3)
        self.__y: float = round(point.y, 3)
        self.__z: float = round(point.z, 3)
        self.__o: float = round(point.o, 3)
        self.__a: float = round(point.a, 3)
        self.__t: float = round(point.t, 3)
        self.in_memory: bool = False

    def __str__(self) -> str:
        return f"{self.__x},{self.__y},{self.__z},{self.__o},{self.__a},{self.__t}"

    def shift(self, name: str, shift: Cartesian) -> "Point":
        return Point(name, Cartesian(self.__x + shift.x, self.__y + shift.y, self.__z + shift.z, self.__o + shift.o, self.__a + shift.a, self.__t + shift.t))


class Program:
    def __init__(self, program: str) -> None:
        program_data: bytes = program.encode("ascii")
        self.split: list[bytes] = [program_data[i : i + 492] for i in range(0, len(program_data), 492)]
        self.name: str = findall(r"\.PROGRAM\s+([^\s]+)", program_data.decode("ascii"))[0]


class Robot:
    def __init__(self, ip: IPv4Address, port: int, show_dialog: Callable[[str], None] = print) -> None:
        self.__telnet_selector: type = SelectSelector
        self.__dialog: Callable[[str], None] = show_dialog
        self.__ip: str = ip.exploded
        self.__port: int = port
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
        self.__socket = create_connection((self.__ip, self.__port))
        self.read_until_match("login:")
        self.__write(username)
        self.read_until_match(">")
        self.__logged_in = True
        self.__initialize()
        self.__dialog("Connected and logged in!")
        self.__clear_queue()

    def status(self) -> dict[Status, bool]:
        self.__write("SWITCH")
        message: str = self.read_until_match(["Press SPACE key to continue"]).split("SWITCH\r")[1]
        split_pattern: Pattern[str] = regex_compile(r" ON| OFF")
        replace_pattern: Pattern[str] = regex_compile(r"[ \n*\r]")
        raw_data: list[str] = [sub(replace_pattern, "", s) for s in split(pattern=split_pattern, string=message)][:-1]
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, findall(split_pattern, string=message), strict=True)}
        self.__write("\n")
        self.__clear_queue()
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

    def send(self, command: Command, arg: Point | None = None) -> None:
        if not self.__logged_in:
            return
        match command.type:
            case CommandType.CONFIG:
                self.__write(command.val)
                self.read_until_match([">", "Program aborted."])
            case CommandType.MOVEMENT:
                if arg is None:
                    self.__write(f"{command.val}")
                elif type(arg) is Point:
                    if not arg.in_memory:
                        self.add_translation_point(arg)
                    self.__write(f"{command.val} {arg.name}")
                state: str = self.read_until_match(["DO motion completed.", "suddenly changed.", "Destination is out of motion range."])
                if "suddenly changed." in state or "Destination is out of motion range." in state:
                    raise RuntimeError(state)
                sleep(0.3)
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
            self.__write("signal -2011")
            self.__dialog("Logged out and disconnected!")
            self.__socket.close()
            self.__logged_in = False

    def read_until_match(self, matches: list[bytes | str] | bytes | str) -> str:
        matches_encoded: list[bytes] = []
        if isinstance(matches, list):
            matches_encoded = [match.encode("ascii") if isinstance(match, str) else match for match in matches]
        else:
            matches_encoded = [matches.encode("ascii") if isinstance(matches, str) else matches]
        self.__raw_queue_process()
        with self.__telnet_selector() as selector:
            selector.register(self.__socket_descriptor(), EVENT_READ)
            while not self.__end_of_file and selector.select():
                self.__raw_queue_fill()
                self.__raw_queue_process()
                for match_encoded in matches_encoded:
                    i: int = self.__cooked_queue.find(match_encoded)
                    if i >= 0:
                        i += len(match_encoded)
                        buffer: bytes = self.__cooked_queue[:i]
                        self.__cooked_queue = self.__cooked_queue[i:]
                        return buffer.decode("ascii")
        raise EOFError

    def load_as_program(self, program: Program) -> None:
        self.__write("KILL\n1\n")
        self.__write(f"LOAD {program.name}")
        self.read_until_match(".as")
        self.__write(Flag.STX + b"A    0" + Flag.ETB)
        for chunk in program.split:
            self.__write(Flag.STX + b"C    0" + chunk + Flag.ETB)
            self.read_until_match(Flag.ETB)
        self.__write(Flag.STX + b"C    0" + Flag.SUB + Flag.ETB + b"\n")
        self.read_until_match(b"E" + Flag.ETB)
        self.__write(Flag.STX + b"E    0" + Flag.ETB)
        self.read_until_match(">")

    def exec_as_program(self, program: Program) -> None:
        self.__write(f"EXE {program.name}")
        state: str = self.read_until_match(["Program completed.", "Program aborted.", "Program held."])
        if "Program held." in state or "Program aborted." in state:
            print("Program held or aborted!")

    def add_translation_point(self, *points: Point) -> None:
        for point in points:
            if point.in_memory:
                continue
            self.__write(f"POINT {point.name} = TRANS({point!s})\n")
            self.read_until_match("Change?")
            point.in_memory = True

    def remove_translation_point(self, *points: Point) -> None:
        self.__write("KILL\n1\n")
        for point in points:
            if not point.in_memory:
                continue
            self.__write(f"DELETE/L {point.name}\n1\n")
            self.read_until_match(">")
            point.in_memory = False

    def __clear_queue(self) -> None:
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
                if char != Flag.IAC and char not in {Flag.NULL, b"\021"}:
                    buffer[self.__subnegotiation] += char
                    continue
                self.__iac_sequence += char
                continue
            if len(self.__iac_sequence) == 1:
                if char in {Flag.DO, Flag.DONT, Flag.WILL, Flag.WONT}:
                    self.__iac_sequence += char
                    continue
                self.__iac_sequence = b""
                match char:
                    case Flag.IAC:
                        buffer[self.__subnegotiation] += char
                    case Flag.SB:
                        self.__subnegotiation = True
                        self.__subnegotiation_data_queue = b""
                    case Flag.SE:
                        self.__subnegotiation = False
                        self.__subnegotiation_data_queue += buffer[1]
                        buffer[1] = b""
                self.__negotiate(char, Flag.NULL)
                continue
            command: bytes = self.__iac_sequence[1:2]
            self.__iac_sequence = b""
            if command in {Flag.DO, Flag.DONT} or command in {Flag.WILL, Flag.WONT}:
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
            case (Flag.WILL, Flag.ECHO):
                self.__socket.sendall(Flag.IAC + Flag.DO + option)
            case (Flag.DO, Flag.TTYPE):
                self.__socket.sendall(Flag.IAC + Flag.WILL + Flag.TTYPE)
            case (Flag.SB, _):
                self.__socket.sendall(
                    Flag.IAC + Flag.SB + Flag.TTYPE + Flag.NULL + b"VT100" + Flag.NULL + Flag.IAC + Flag.SE,
                )

    def __socket_descriptor(self) -> int:
        return self.__socket.fileno()

    def __initialize(self) -> None:
        if not self.__logged_in:
            return

        current_status: dict[Status, bool] = self.status()
        if any([
            current_status[Status.TEACH_LOCK],
            current_status[Status.TEACH_MODE],
            current_status[Status.HOLD],
        ]):
            self.__dialog("Robot is not ready for operation!")
            return

        if current_status[Status.ERROR]:
            self.send(Command.RESET)
        if current_status[Status.CONTINUOUS_PATH]:
            self.send(Command.CONTINUOUS_PATH_OFF)
        if current_status[Status.REPEAT_ONCE]:
            self.send(Command.REPEAT_ONCE_ON)
        if current_status[Status.STEP_ONCE]:
            self.send(Command.STEP_ONCE_OFF)
        if not current_status[Status.MOTOR_POWERED]:
            self.send(Command.MOTOR_ON)
            if not self.status()[Status.MOTOR_POWERED]:
                self.__dialog("Motor cannot be powered on!")

    def __write(self, buffer: str | bytes, end: bytes = b"\r\n") -> None:
        buffer_encoded: bytes = (bytes(buffer) if isinstance(buffer, bytes | bytearray | memoryview) else buffer.encode("ascii")).replace(
            Flag.IAC,
            Flag.IAC + Flag.IAC,
        )
        self.__socket.sendall(buffer_encoded + end)
