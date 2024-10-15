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




# import time
# from telnetlib import DO, ECHO, IAC, SB, SE, TTYPE, WILL, Telnet
# from typing import Final


# def negotiation(socket, cmd, opt) -> None:
#     IS = b"\00"
#     if cmd == WILL and opt == ECHO:
#         socket.sendall(IAC + DO + opt)
#     elif cmd == DO and opt == TTYPE:
#         socket.sendall(IAC + WILL + TTYPE)
#     elif cmd == SB:
#         socket.sendall(IAC + SB + TTYPE + IS + b"VT100" + IS + IAC + SE)
#     elif cmd == SE:
#         pass
#     else:
#         print("Invalid negotiation!")


# IP: Final[str] = "192.168.1.155"
# PORT: Final[int] = 23
# USER: Final[str] = "as"
# TIMEOUT: Final[int] = 5
# SPEED: Final[int] = 100

# telnet: Telnet = Telnet()
# telnet.set_option_negotiation_callback(negotiation)

# try:
#     telnet.open(IP, PORT, TIMEOUT)
#     _ = telnet.read_until(b"login: ", TIMEOUT)
#     telnet.write(USER.encode() + b"\r\n")
#     _ = telnet.read_until(b">", TIMEOUT)
# except ConnectionRefusedError as e:
#     print(e)
#     telnet.close()


# def send_command(command: str) -> None:
#     telnet.write(command.encode() + b"\r\n")
#     _ = telnet.read_until(b"DO motion completed.")
#     time.sleep(0.5)
#     print("Done!")


# cmd_list: list[str] = ["DO HOME", "DO TDRAW 0, 0, 0", f"DO DRIVE 1, 20, {SPEED}", f"DO DRIVE 2, 30, {SPEED}", f"DO DRIVE 3, 20, {SPEED}", f"DO DRIVE 1, -80, {SPEED}"]

# for cmd in cmd_list:
#     send_command(cmd)


import socket
import time
from typing import Final

IP: Final[str] = "192.168.1.155"
PORT: Final[int] = 23
USER: Final[str] = "as"
TIMEOUT: Final[int] = 5
SPEED: Final[int] = 100

sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((IP, PORT))

try:
    sock.settimeout(TIMEOUT)
    sock.sendall(USER.encode() + b"\r\n")
    _ = sock.recv(1024)
    sock.sendall(b"DO HOME\r\n")
    _ = sock.recv(1024)
    sock.sendall(b"DO TDRAW 0, 0, 0\r\n")
    _ = sock.recv(1024)
    sock.sendall(f"DO DRIVE 1, 20, {SPEED}\r\n".encode())
    _ = sock.recv(1024)
    sock.sendall(f"DO DRIVE 2, 30, {SPEED}\r\n".encode())
    _ = sock.recv(1024)
    sock.sendall(f"DO DRIVE 3, 20, {SPEED}\r\n".encode())
    _ = sock.recv(1024)
    sock.sendall(f"DO DRIVE 1, -80, {SPEED}\r\n".encode())
    _ = sock.recv(1024)
    time.sleep(0.5)
    print("Done!")
except socket.error as e:
    print(e)
    sock.close()
