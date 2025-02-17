import asyncio
from asyncio import StreamReader, StreamWriter, open_connection, sleep
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from re import Pattern, findall, split, sub
from re import compile as regex_compile
from typing import TYPE_CHECKING, Final, Self
from warnings import warn

warn("The AsyncRobot class is not tested and needs to be used with caution!", DeprecationWarning, 1)


if TYPE_CHECKING:
    from re import Pattern


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


class AsyncRobot:
    def __init__(self, ip: str, port: int, dialog: Callable[[str], None] = print) -> None:
        self.__ip: str = ip
        self.__port: int = port
        self.__reader: StreamReader
        self.__writer: StreamWriter
        self.__split_pattern: Final[Pattern[str]] = regex_compile(r" ON| OFF")
        self.__replace_pattern: Final[Pattern[str]] = regex_compile(r"[ \n*\r]")
        self.__dialog: Callable[[str], None] = dialog
        self.__aborted: bool = False
        self.logged_in: bool = False

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    def write(self, buffer: str | bytes) -> None:
        if isinstance(buffer, str):
            buffer = buffer.encode("ascii")
        self.__writer.write(buffer)

    async def read_until(self, *match: bytes) -> bytes:
        return await self.__reader.readuntil(match)

    async def initialize(self) -> None:
        current_status: dict[Status, bool] = await self.status()
        if any([current_status[Status.TEACH_LOCK], current_status[Status.TEACH_MODE], current_status[Status.HOLD]]):
            self.__dialog("Robot is not ready for operation!")
            return
        if current_status[Status.ERROR]:
            await self.reset_errors()
        if current_status[Status.CONTINUOUS_PATH]:
            await self.toggle((Switch.CONTINOUS_PATH, False))
        if current_status[Status.REPEAT_ONCE]:
            await self.toggle((Switch.REPEAT_ONCE, True))
        if current_status[Status.STEP_ONCE]:
            await self.toggle((Switch.STEP_ONCE, False))
        if not current_status[Status.MOTOR_POWERED]:
            await self.toggle((Switch.MOTOR, True))
            if not (await self.status())[Status.MOTOR_POWERED]:
                self.__dialog("Motor cannot be powered on!")

    async def connect(self) -> None:
        if self.logged_in:
            return
        try:
            self.__reader, self.__writer = await open_connection(self.__ip, self.__port)
            await self.__negotiate()
            self.write(b"as\r\n")
            await self.read_until(b"as\r\n>")
        except ConnectionError:
            self.__dialog("Connection refused!\nCheck IP and port!")
            return

        await self.initialize()
        self.logged_in = True
        self.__dialog("Connected and logged in!")

    async def disconnect(self) -> None:
        if not self.logged_in:
            return
        await self.abort_motion()
        await self.toggle((Switch.MOTOR, False))
        self.write(b"signal -2011\r\n")
        self.__writer.close()
        await self.__writer.wait_closed()
        self.logged_in = False
        self.__dialog("Logged out and disconnected!")

    async def status(self) -> dict[Status, bool]:
        self.write(b"SWITCH\r\n")
        raw_message: bytes = await self.read_until(b"Press SPACE key to continue")
        message: str = raw_message.decode("ascii").split("SWITCH\r")[1]
        raw_data: list[str] = [sub(self.__replace_pattern, "", s) for s in split(pattern=self.__split_pattern, string=message)][:-1]
        status_data: dict[str, bool] = {key: value == " ON" for key, value in zip(raw_data, findall(self.__split_pattern, string=message), strict=True)}
        self.write(b"\n")
        await self.read_until(b"\r\n>")
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

    async def add_point(self, *points: Point) -> None:
        for point in points:
            self.write(f"POINT {point.name} = TRANS({point!s})\n\r\n")
            await self.read_until(b"(If not, Press RETURN only.)\r\n\r\n>")
            point.in_memory = True

    async def remove_point(self, *points: Point) -> None:
        self.write("KILL\n1\n")
        await self.read_until(b"1\r\n>")
        for point in points:
            if not point.in_memory:
                continue
            self.write(f"DELETE/L {point.name}\n1\n")
            await self.read_until(b"1\r\n>", b"does not exist.\r\n>")
            point.in_memory = False

    async def move(self, move_type: Move, point: Point) -> None:
        print(point)
        if not point.in_memory:
            await self.add_point(point)
        self.write(f"{move_type.value} {point.name}\r\n")
        await self.wait_until_done()

    async def toggle(self, *switch: tuple[Switch, bool]) -> None:
        for sw in switch:
            self.write(f"{sw[0].value} {'ON' if sw[1] else 'OFF'}\r\n")
            await self.read_until(b"\r\n>")

    async def reset_errors(self) -> None:
        self.write("ERESET\r\n")
        await self.read_until(b"\r\n>", b"Cleared error state.")

    async def abort_motion(self) -> None:
        self.__aborted = True
        self.write(b"ABORT\r\n")
        print("ABORTED")
        # await self.read_until(b"DO motion held.", b"Program aborted.")

    async def home(self) -> None:
        self.write(b"DO HOME\r\n")
        await self.wait_until_done()

    async def load_program(self, program: Program) -> None:
        self.write(b"KILL\n1\n")
        self.write(f"LOAD {program.name}\r\n")
        await self.read_until(b".as")
        self.write(Flag.STX + b"A    0" + Flag.ETB)
        for chunk in program.split:
            self.write(Flag.STX + b"C    0" + chunk + Flag.ETB)
            await self.read_until(Flag.ETB)
        self.write(Flag.STX + b"C    0" + Flag.SUB + Flag.ETB + b"\n")
        await self.read_until(b"E" + Flag.ETB)
        self.write(Flag.STX + b"E    0" + Flag.ETB)
        await self.read_until(b">")

    async def exec_program(self, program: Program) -> None:
        self.write(f"EXE {program.name}\r\n")
        await self.wait_until_done()

    async def __negotiate(self) -> None:
        for _ in range(4):
            data: bytes = await self.__reader.readexactly(3)
            if data == Flag.IAC + Flag.DO + Flag.TTYPE:
                self.write(Flag.IAC + Flag.WILL + Flag.TTYPE)
            elif data == Flag.IAC + Flag.WILL + Flag.ECHO:
                self.write(Flag.IAC + Flag.DO + Flag.ECHO)
            elif data == Flag.IAC + Flag.SB + Flag.TTYPE:
                self.write(Flag.IAC + Flag.SB + Flag.TTYPE + b"VT100" + Flag.IAC + Flag.SE)

    async def wait_until_done(self) -> None:
        while not self.__aborted:
            if (status := await self.status())[Status.BUSY]:
                await asyncio.sleep(0.01)
            if not status[Status.BUSY]:
                break
        self.__aborted = False


async def main() -> None:
    async with AsyncRobot(ip="127.0.0.1", port=9105) as robot:
        await robot.connect()
        A1 = Point("a1", Cartesian(x=93.395, y=547.541, z=-210.056, o=164.851, a=179.143, t=-108.635))
        await robot.add_point(A1)
        await robot.move(Move.HYBRID, A1)
        await robot.home()
    # await robot.home()


if __name__ == "__main__":
    asyncio.run(main())
