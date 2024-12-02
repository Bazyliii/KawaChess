import selectors
from dataclasses import dataclass
from socket import create_connection, socket


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


class SimpleTelnet:
    def __init__(self, host: str) -> None:
        self._telnet_selector: type = selectors.SelectSelector
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

    def __socket_descriptor(self) -> int:
        return self.socket.fileno()

    def close(self) -> None:
        self.end_of_file = True
        self.iac_sequence = b""
        self.subnegotiation = False
        if self.socket:
            self.socket.close()

    def write(self, buffer: str) -> None:
        buffer_encoded: bytes = buffer.encode("ascii") + b"\r\n"
        if TelnetFlag.IAC in buffer_encoded:
            buffer_encoded = buffer_encoded.replace(TelnetFlag.IAC, TelnetFlag.IAC + TelnetFlag.IAC)
        self.socket.sendall(buffer_encoded)

    def clear_queue(self) -> None:
        self.raw_queue = b""
        self.raw_queue_index = 0
        self.cooked_queue = b""
        self.iac_sequence = b""
        self.subnegotiation = False
        self.subnegotiation_data_queue = b""
        self.end_of_file = False

    def read_until_match(self, match: str) -> str:
        match_encoded: bytes = match.encode("ascii")
        self.__raw_queue_process()
        with self._telnet_selector() as selector:
            selector.register(self.__socket_descriptor(), selectors.EVENT_READ)
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


if __name__ == "__main__":
    telnet = SimpleTelnet("127.0.0.1/9105")
    a: str = telnet.read_until_match("login:")
    telnet.write("as")
    b: str = telnet.read_until_match(">")
    telnet.write("POINT #xd")
    c: str = telnet.read_until_match("Change?")
    telnet.write("9.487,68.678,-53.954,-179.435,57.988,-237.583")
    d: str = telnet.read_until_match("Change?")
    telnet.write("\n")
    e: str = telnet.read_until_match(">")
    print(a, b, c, d, e)
