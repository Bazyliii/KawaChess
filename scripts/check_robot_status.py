import asyncio
from enum import Enum
from telnetlib import Telnet


class KawasakiStatus(Enum):
    ERROR = 0
    MOTOR_POWERED = 1
    REPEAT_MODE = 2
    TEACH_MODE = 3
    BUSY = 4


class KawasakiStatusError(Exception):
    pass


async def get_robot_status(telnet: Telnet) -> dict[KawasakiStatus, bool]:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    await loop.run_in_executor(None, telnet.write, b"STATUS\r\n")
    raw_status: bytes = await loop.run_in_executor(None, telnet.read_until, b">")
    decoded_status: str = raw_status.decode().split("STATUS\r")[1]

    status: dict[KawasakiStatus, bool] = {
        KawasakiStatus.ERROR: "error" in decoded_status,
        KawasakiStatus.MOTOR_POWERED: "Motor power OFF" not in decoded_status,
        KawasakiStatus.REPEAT_MODE: "REPEAT mode" in decoded_status,
        KawasakiStatus.TEACH_MODE: "TEACH mode" in decoded_status,
        KawasakiStatus.BUSY: "CYCLE START ON" in decoded_status,
    }
    return status
