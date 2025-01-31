import serial.tools.list_ports
from error_msg import POLOLU_MINI_MAESTRO_NOT_FOUND, POSITION_OUT_OF_RANGE
from maestro import Maestro


class Gripper:
    def __init__(self, *, tty: str = "", limit: tuple[int, int] = (400, 2416), open_value: int | None = None, close_value: int | None = None) -> None:
        if not tty:
            tty = self.__get_pololu_tty_port()
        self.maestro = Maestro.connect("mini12", tty=tty)
        self.limit = limit
        self.open_value = open_value or self.limit[0]
        self.close_value = close_value or self.limit[1]

    def __exit__(self, *_: object) -> None:
        self.maestro.close()

    def open(self) -> None:
        self.__control(self.open_value)

    def close(self) -> None:
        self.__control(self.close_value)

    @staticmethod
    def __get_pololu_tty_port() -> str:
        for port in serial.tools.list_ports.comports():
            if "Pololu Mini Maestro 12-Channel USB Servo Controller Command Port" in port.description:
                return port.device
        raise ValueError(POLOLU_MINI_MAESTRO_NOT_FOUND)

    def __control(self, position: int) -> None:
        if not self.limit[0] <= position <= self.limit[1]:
            raise ValueError(POSITION_OUT_OF_RANGE)
        self.maestro.set_target(0, position)
        self.maestro.wait_until_done_moving()


if __name__ == "__main__":
    import time

    gripper = Gripper(open_value=800, close_value=1200)
    gripper.open()
    time.sleep(1)
    gripper.close()
