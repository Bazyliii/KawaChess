from dataclasses import dataclass
from enum import Enum, auto
from re import Pattern, compile, findall, split, sub
from selectors import EVENT_READ, SelectSelector
from socket import create_connection, socket
from time import sleep


class RobotStatus(Enum):
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
class RobotCommand:
    RESET: tuple[str, int] = ("ERESET", 0)
    MOTOR_ON: tuple[str, int] = ("ZPOW ON", 0)
    MOTOR_OFF: tuple[str, int] = ("ZPOW OFF", 0)
    HOME: tuple[str, int] = ("DO HOME", 1)
    MOVE_TO_POINT: tuple[str, int] = ("DO HMOVE", 1)
    PICKUP: tuple[str, int] = ("DO LDEPART 80", 1)
    PUTDOWN: tuple[str, int] = ("DO LDEPART -80", 1)
    EXECUTE_PROG: tuple[str, int] = ("EXE", 2)
    CONTINUOUS_PATH_ON: tuple[str, int] = ("CP ON", 0)
    CONTINUOUS_PATH_OFF: tuple[str, int] = ("CP OFF", 0)
    REPEAT_ONCE_OFF: tuple[str, int] = ("REP_ONCE OFF", 0)
    REPEAT_ONCE_ON: tuple[str, int] = ("REP_ONCE ON", 0)
    STEP_ONCE_OFF: tuple[str, int] = ("STP_ONCE OFF", 0)
    STEP_ONCE_ON: tuple[str, int] = ("STP_ONCE ON", 0)


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


class RobotConnection:
    def __init__(self, host: str) -> None:
        self._telnet_selector: type = SelectSelector
        self.host: str = host.split("/")[0]
        self.port: int = int(host.split("/")[1])
        self.raw_queue: bytes = b""
        self.raw_queue_index: int = 0
        self.cooked_queue: bytes = b""
        self.end_of_file: bool = False
        self.iac_sequence: bytes = b""
        self.subnegotiation: bool = False
        self.subnegotiation_data_queue: bytes = b""
        self.socket: socket = create_connection((self.host, self.port))

    def __del__(self) -> None:
        self.close()

    def login(self, username: str = "as") -> None:
        self.read_until_match("login:")
        self.__write(username)
        self.read_until_match(">")

    def status(self) -> dict[RobotStatus, bool]:
        self.__write("SWITCH")
        message: str = self.read_until_match("Press SPACE key to continue").split("SWITCH\r")[1]
        split_pattern: Pattern[str] = compile(r" ON| OFF")
        replace_pattern: Pattern[str] = compile(r"[ \n*\r]")
        raw_data: list[str] = [sub(replace_pattern, "", s) for s in split(pattern=split_pattern, string=message)][:-1]
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, findall(split_pattern, string=message), strict=True)}
        self.__write("\n")
        self.__clear_queue()
        return {
            RobotStatus.BUSY: status_data["CS"],
            RobotStatus.ERROR: status_data["ERROR"],
            RobotStatus.MOTOR_POWERED: status_data["POWER"],
            RobotStatus.REPEAT_MODE: status_data["REPEAT"],
            RobotStatus.TEACH_MODE: not status_data["REPEAT"],
            RobotStatus.TEACH_LOCK: status_data["TEACH_LOCK"],
            RobotStatus.HOLD: not status_data["RUN"],
            RobotStatus.CONTINUOUS_PATH: status_data["CP"],
            RobotStatus.REPEAT_ONCE: status_data["REP_ONCE"],
            RobotStatus.STEP_ONCE: status_data["STP_ONCE"],
        }

    def send(self, command: tuple[str, int], arg: "RobotCartesianPoint | str | None" = None) -> None:
        match command[1]:
            case 0:
                self.__write(command[0])
                self.read_until_match(">")
            case 1:
                if type(arg) is RobotCartesianPoint:
                    self.__write(command[0] + f" {arg.name}")
                else:
                    self.__write(command[0])
                self.read_until_match("DO motion completed.")
                sleep(0.3)
            case 2:
                self.__write(command[0] + f" {arg}")
                self.read_until_match("Program completed.")
        sleep(0.1)

    def close(self) -> None:
        self.end_of_file = True
        self.iac_sequence = b""
        self.subnegotiation = False
        if self.socket:
            self.__write("signal -2011")
            self.socket.close()

    def read_until_match(self, match: str) -> str:
        match_encoded: bytes = match.encode("ascii")
        self.__raw_queue_process()
        with self._telnet_selector() as selector:
            selector.register(self.__socket_descriptor(), EVENT_READ)
            while not self.end_of_file and selector.select():
                self.__raw_queue_fill()
                self.__raw_queue_process()
                i: int = self.cooked_queue.find(match_encoded)
                if i >= 0:
                    i += len(match_encoded)
                    buffer: bytes = self.cooked_queue[:i]
                    self.cooked_queue = self.cooked_queue[i:]
                    return buffer.decode("ascii")
        raise EOFError

    def write_program(self, program: str, name: str) -> None:
        self.__clear_queue()
        self.__write("KILL")
        self.__write("1")
        self.__write("\n")
        self.__write(f"EDIT {name}, 1")
        for line in program.splitlines():
            self.__write(line)
        self.__write("E")
        self.__write("\n")
        sleep(0.1)

    def __write(self, buffer: str) -> None:
        buffer_encoded: bytes = buffer.encode("ascii") + b"\r\n"
        if TelnetFlag.IAC in buffer_encoded:
            buffer_encoded = buffer_encoded.replace(TelnetFlag.IAC, TelnetFlag.IAC + TelnetFlag.IAC)
        self.socket.sendall(buffer_encoded)

    def __raw_queue_process(self) -> None:
        buffer: list[bytes] = [b"", b""]
        while self.raw_queue:
            char: bytes = self.__raw_queue_get_char()
            if not self.iac_sequence:
                if char != TelnetFlag.IAC and char not in {TelnetFlag.NULL, b"\021"}:
                    buffer[self.subnegotiation] += char
                    continue
                self.iac_sequence += char
                continue
            if len(self.iac_sequence) == 1:
                if char in {TelnetFlag.DO, TelnetFlag.DONT, TelnetFlag.WILL, TelnetFlag.WONT}:
                    self.iac_sequence += char
                    continue
                self.iac_sequence = b""
                match char:
                    case TelnetFlag.IAC:
                        buffer[self.subnegotiation] += char
                    case TelnetFlag.SB:
                        self.subnegotiation = True
                        self.subnegotiation_data_queue = b""
                    case TelnetFlag.SE:
                        self.subnegotiation = False
                        self.subnegotiation_data_queue += buffer[1]
                        buffer[1] = b""
                self.__negotiate(char, TelnetFlag.NULL)
                continue
            command: bytes = self.iac_sequence[1:2]
            self.iac_sequence = b""
            if command in {TelnetFlag.DO, TelnetFlag.DONT} or command in {TelnetFlag.WILL, TelnetFlag.WONT}:
                self.__negotiate(command, char)
        self.cooked_queue += buffer[0]
        self.subnegotiation_data_queue += buffer[1]

    def __raw_queue_get_char(self) -> bytes:
        if not self.raw_queue:
            self.__raw_queue_fill()
            if self.end_of_file:
                raise EOFError
        char: bytes = self.raw_queue[self.raw_queue_index : self.raw_queue_index + 1]
        self.raw_queue_index += 1
        if self.raw_queue_index >= len(self.raw_queue):
            self.raw_queue = b""
            self.raw_queue_index = 0
        return char

    def __raw_queue_fill(self) -> None:
        if self.raw_queue_index >= len(self.raw_queue):
            self.raw_queue = b""
            self.raw_queue_index = 0
        buffer: bytes = self.socket.recv(50)
        self.end_of_file = not buffer
        self.raw_queue += buffer

    def __negotiate(self, command: bytes, option: bytes) -> None:
        match (command, option):
            case (TelnetFlag.WILL, TelnetFlag.ECHO):
                self.socket.sendall(TelnetFlag.IAC + TelnetFlag.DO + option)
            case (TelnetFlag.DO, TelnetFlag.TTYPE):
                self.socket.sendall(TelnetFlag.IAC + TelnetFlag.WILL + TelnetFlag.TTYPE)
            case (TelnetFlag.SB, _):
                self.socket.sendall(
                    TelnetFlag.IAC + TelnetFlag.SB + TelnetFlag.TTYPE + TelnetFlag.NULL + b"VT100" + TelnetFlag.NULL + TelnetFlag.IAC + TelnetFlag.SE,
                )

    def __socket_descriptor(self) -> int:
        return self.socket.fileno()

    def __clear_queue(self) -> None:
        self.__raw_queue_fill()
        self.__raw_queue_process()
        self.raw_queue = b""
        self.cooked_queue = b""
        self.raw_queue_index = 0


class RobotCartesianPoint:
    def __init__(self, telnet: RobotConnection, name: str, x: float, y: float, z: float, o: float, a: float, t: float) -> None:
        self.name: str = name
        self.telnet: RobotConnection = telnet
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.o: float = o
        self.a: float = a
        self.t: float = t
        self.__push_point_to_robot()

    def shift(self, name: str, *, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> "RobotCartesianPoint":
        return RobotCartesianPoint(self.telnet, name, self.x + x, self.y + y, self.z + z, self.o, self.a, self.t)

    def __push_point_to_robot(self) -> None:
        self.telnet.__write(f"POINT {self.name}")
        self.telnet.__write(f"{self.x},{self.y},{self.z},{self.o},{self.a},{self.t}")
        self.telnet.__write("\n")
        self.telnet.__clear_queue()
