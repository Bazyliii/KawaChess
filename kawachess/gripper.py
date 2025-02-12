from collections.abc import Callable

import serial.tools.list_ports
from maestro import Maestro

from kawachess.constants import POLOLU_MINI_MAESTRO_NOT_FOUND
from enum import Enum


class State(Enum):
    OPEN = 0
    CLOSE = 1


class Gripper:
    def __init__(self, *, tty: str = "", dialog: Callable[[str], None] = print) -> None:
        if not tty:
            tty = self.__get_pololu_tty_port()
        self.maestro: Maestro = Maestro.connect("mini12", tty=tty)
        self.limit: tuple = (496, 720)
        self.dialog: Callable[[str], None] = dialog

    def __exit__(self, *_: object) -> None:
        self.maestro.close()

    def control(self, state: State) -> None:
        self.__control(self.limit[state.value])

    def __get_pololu_tty_port(self) -> str:
        for port in serial.tools.list_ports.comports():
            if "Pololu Mini Maestro 12-Channel USB Servo Controller Command Port" in port.description:
                return port.device
        self.dialog("Position out of range!")
        raise ValueError(POLOLU_MINI_MAESTRO_NOT_FOUND)

    def __control(self, position: int) -> None:
        if not self.limit[0] <= position <= self.limit[1]:
            self.dialog("Position out of range!")
            return
        self.maestro.set_target(0, position)
        self.maestro.wait_until_done_moving()
