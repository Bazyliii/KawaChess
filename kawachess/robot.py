from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from re import Pattern, findall, split, sub
from re import compile as regex_compile
from selectors import EVENT_READ, SelectSelector
from socket import create_connection, socket
from time import sleep


class Program:
    def __init__(self, program: str) -> None:
        program_data: bytes = program.encode("ascii")
        self.split: list[bytes] = [program_data[i : i + 492] for i in range(0, len(program_data), 492)]
        self.name: str = findall(r"\.PROGRAM\s+([^\s]+)", program)[0]


@dataclass(frozen=True, repr=False, eq=False)
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


class Switch(Enum):
    MOTOR = "ZPOW"
    CONTINOUS_PATH = "CP"
    REPEAT_ONCE = "REP_ONCE"
    STEP_ONCE = "STP_ONCE"


class Move(Enum):
    LINEAR = "DO LMOVE"
    HYBRID = "DO HMOVE"
    JOINT = "DO JMOVE"


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


@dataclass(kw_only=True)
class Cartesian:
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
        self.__o: float = round(point.o, 3)  # Rotation around the Z axis
        self.__a: float = round(point.a, 3)  # Rotation around the Y axis
        self.__t: float = round(point.t, 3)  # Rotation around the rotated Z axis
        self.in_memory: bool = False

    def __str__(self) -> str:
        return f"{self.__x},{self.__y},{self.__z},{self.__o},{self.__a},{self.__t}"

    def shift(self, name: str, shift: Cartesian) -> "Point":
        return Point(
            name, Cartesian(x=self.__x + shift.x, y=self.__y + shift.y, z=self.__z + shift.z, o=self.__o + shift.o, a=self.__a + shift.a, t=self.__t + shift.t)
        )


class Robot:
    def __init__(self, ip: str, port: int, show_dialog: Callable[[str], None] = print) -> None:
        self.__split_pattern: Pattern[str] = regex_compile(r" ON| OFF")
        self.__replace_pattern: Pattern[str] = regex_compile(r"[ \n*\r]")
        self.__telnet_selector: type = SelectSelector
        self.__dialog: Callable[[str], None] = show_dialog
        self.__ip: str = ip
        self.__port: int = port
        self.__raw_queue: bytes = b""
        self.__raw_queue_index: int = 0
        self.__cooked_queue: bytes = b""
        self.__end_of_file: bool = False
        self.__iac_sequence: bytes = b""
        self.__subnegotiation: bool = False
        self.__subnegotiation_data_queue: bytes = b""
        self.__socket: socket = socket()
        self.logged_in: bool = False

    def connect(self, username: str = "as") -> None:
        if self.logged_in:
            return
        try:
            self.__socket = create_connection((self.__ip, self.__port))
        except ConnectionRefusedError:
            self.__dialog("Connection refused!\nCheck IP and port!")
            return
        self.read_until(b"login:")
        self.__write(username)
        self.read_until(b">")
        if not self.__initialize():
            return
        self.logged_in = True
        self.__dialog("Connected and logged in!")
        self.__clear_queue()

    def status(self) -> dict[Status, bool]:
        self.__write("SWITCH")
        message: str = self.read_until(b"Press SPACE key to continue").split("SWITCH\r")[1]
        raw_data: list[str] = [sub(self.__replace_pattern, "", s) for s in split(pattern=self.__split_pattern, string=message)][:-1]
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, findall(self.__split_pattern, string=message), strict=True)}
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

    def disconnect(self) -> None:
        self.__raw_queue: bytes = b""
        self.__raw_queue_index: int = 0
        self.__cooked_queue: bytes = b""
        self.__end_of_file: bool = False
        self.__iac_sequence: bytes = b""
        self.__subnegotiation: bool = False
        self.__subnegotiation_data_queue: bytes = b""
        if self.logged_in:
            self.__write("signal -2011")
            self.__dialog("Logged out and disconnected!")
            self.__socket.close()
            self.logged_in = False

    def read_until(self, *match: bytes) -> str:
        self.__raw_queue_process()
        with self.__telnet_selector() as selector:
            selector.register(self.__socket_descriptor(), EVENT_READ)
            while not self.__end_of_file and selector.select():
                self.__raw_queue_fill()
                self.__raw_queue_process()
                for match_encoded in match:
                    i: int = self.__cooked_queue.find(match_encoded)
                    if i >= 0:
                        i += len(match_encoded)
                        buffer: bytes = self.__cooked_queue[:i]
                        self.__cooked_queue = self.__cooked_queue[i:]
                        return buffer.decode("ascii")
        raise EOFError

    def load_program(self, program: Program) -> None:
        self.__write("KILL\n1\n")
        self.__write(f"LOAD {program.name}")
        self.read_until(b".as")
        self.__write(Flag.STX + b"A    0" + Flag.ETB)
        for chunk in program.split:
            self.__write(Flag.STX + b"C    0" + chunk + Flag.ETB)
            self.read_until(Flag.ETB)
        self.__write(Flag.STX + b"C    0" + Flag.SUB + Flag.ETB + b"\n")
        self.read_until(Flag.ETB)
        self.__write(Flag.STX + b"E    0" + Flag.ETB)
        self.read_until(b">")

    def exec_program(self, program: Program) -> None:
        self.__write(f"EXE {program.name}")
        state: str = self.read_until(b"Program completed.", b"Program aborted.", b"Program held.")
        if "Program held." in state or "Program aborted." in state:
            pass

    def add_point(self, *points: Point) -> None:
        for point in points:
            if point.in_memory:
                continue
            self.__write(f"POINT {point.name} = TRANS({point!s})\n")
            self.read_until(b"Change?")
            self.__write("\n")
            point.in_memory = True

    def remove_point(self, *points: Point) -> None:
        self.__write("KILL\n1\n")
        for point in points:
            if not point.in_memory:
                continue
            self.__write(f"DELETE/L {point.name}\n1\n")
            self.read_until(b">")
            point.in_memory = False

    def reset_errors(self) -> None:
        self.__write("ERESET\r\n")
        self.read_until(b"Cleared error state.", b">")

    def move(self, move_type: Move, point: Point) -> None:
        if not point.in_memory:
            self.add_point(point)
        self.__write(f"{move_type.value} {point.name}\r\n")
        state: str = self.read_until(
            b"DO motion completed.",
            b"suddenly changed.",
            b"Destination is out of motion range.",
            b"beyond motion range.",
            b"DO motion held.",
            b"Program aborted.",
        )
        if "beyond motion range." in state:
            raise RuntimeError(state)
        sleep(0.4)

    def toggle(self, *switch: tuple[Switch, bool]) -> None:
        for sw in switch:
            self.__write(f"{sw[0].value} {'ON' if sw[1] else 'OFF'}\r\n")
            self.read_until(b"\r\n>")

    def abort_motion(self) -> None:
        self.__write("ABORT\r\n")
        self.read_until(b"DO motion held.", b"Program aborted.")

    def home(self) -> None:
        self.__write("DO HOME\r\n")
        self.read_until(b"DO motion completed.", b"Program aborted.")
        sleep(0.4)

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

    def __initialize(self) -> bool:
        current_status: dict[Status, bool] = self.status()
        if any(
            [
                current_status[Status.TEACH_LOCK],
                current_status[Status.TEACH_MODE],
                current_status[Status.HOLD],
            ]
        ):
            self.__dialog("Robot is not ready for operation!")
            return False

        if current_status[Status.ERROR]:
            self.reset_errors()
        if current_status[Status.CONTINUOUS_PATH]:
            self.toggle((Switch.CONTINOUS_PATH, False))
        if current_status[Status.REPEAT_ONCE]:
            self.toggle((Switch.REPEAT_ONCE, True))
        if current_status[Status.STEP_ONCE]:
            self.toggle((Switch.STEP_ONCE, False))
        if not current_status[Status.MOTOR_POWERED]:
            self.toggle((Switch.MOTOR, True))
            sleep(0.1)
            if not self.status()[Status.MOTOR_POWERED]:
                self.__dialog("Motor cannot be powered on!")
                return False

        return True

    def __write(self, buffer: str | bytes, end: bytes = b"\r\n") -> None:
        buffer_encoded: bytes = (bytes(buffer) if isinstance(buffer, bytes | bytearray | memoryview) else buffer.encode("ascii")).replace(
            Flag.IAC,
            Flag.IAC + Flag.IAC,
        )
        self.__socket.sendall(buffer_encoded + end)
