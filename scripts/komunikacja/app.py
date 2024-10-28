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

# Left top corner 72.319 286.221 -217.559 -155.001 177.533 -174.963


import time
from telnetlib import DO, ECHO, IAC, SB, SE, TTYPE, WILL, Telnet
from typing import Final


def negotiation(socket, cmd, opt) -> None:
    IS = b"\00"
    if cmd == WILL and opt == ECHO:
        socket.sendall(IAC + DO + opt)
    elif cmd == DO and opt == TTYPE:
        socket.sendall(IAC + WILL + TTYPE)
    elif cmd == SB:
        socket.sendall(IAC + SB + TTYPE + IS + b"VT100" + IS + IAC + SE)


IP: Final[str] = "192.168.1.155"
PORT: Final[int] = 23
USER: Final[str] = "as"
TIMEOUT: Final[int] = 5
SPEED: Final[int] = 100

telnet: Telnet = Telnet()
telnet.set_option_negotiation_callback(negotiation)

try:
    telnet.open(IP, PORT, TIMEOUT)
    _ = telnet.read_until(b"login: ", TIMEOUT)
    telnet.write(USER.encode() + b"\r\n")
    _ = telnet.read_until(b">", TIMEOUT)
except ConnectionRefusedError as e:
    print(e)
    telnet.close()


def reset_errors() -> None:
    print("Resetting errors...")
    telnet.write(b"ERESET\r\n")
    time.sleep(0.5)


def motor_on() -> None:
    print("Motor on...")
    telnet.write(b"ZPOW ON\r\n")
    time.sleep(0.5)


def motor_off() -> None:
    print("Motor off...")
    telnet.write(b"ZPOW OFF\r\n")
    time.sleep(0.5)


def send_command(command: str) -> None:
    try:
        telnet.write(command.encode() + b"\r\n")
        _ = telnet.read_until(b"DO motion completed.")
        time.sleep(0.5)
        print("Done!")
    except KeyboardInterrupt:
        telnet.close()


def create_joint_point(jt1: float, jt2: float, jt3: float, jt4: float, jt5: float, jt6: float, point_name: str) -> None:
    telnet.write(f"POINT #{point_name}".encode() + b"\r\n")
    telnet.write(f"{jt1},{jt2},{jt3},{jt4},{jt5},{jt6}".encode())
    telnet.write(b"\n\r\n")

def translate_joint_to_cartesian(from_point_name: str, to_point_name: str) -> None:
    telnet.write(f"POINT {to_point_name}=#{from_point_name}".encode() + b"\r\n")
    telnet.write(b"\n\r\n")


def shift_point(from_point_name: str, new_point_name: str, x: float, y: float, z: float) -> None:
    telnet.write(f"POINT {new_point_name} = SHIFT({from_point_name} by {x}, {y}, {z})".encode() + b"\r\n")
    telnet.write(b"\n\r\n")


def get_robot_status() -> str:
    telnet.write(b"STATUS\r\n")
    status = telnet.read_until(b"Stepper status").decode().split(">STATUS\r")[1]
    return status


create_joint_point(13.531, 44.211, -133.421, -27.616, -1.412, -118.985, "Punkt_003")
translate_joint_to_cartesian("Punkt_003", "Punkt_004")
shift_point("Punkt_004", "Punkt_005", -280, 0, 0)
shift_point("Punkt_005", "Punkt_006", 0, 280, 0)
shift_point("Punkt_006", "Punkt_007", 280, 0, 0)

cmd_list: list[str] = [
    "DO HOME",
    "DO HMOVE Punkt_003",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_005",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_006",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_007",
    "DO LDEPART 80",
    "DO LDEPART -80",
    "DO HMOVE Punkt_003",
    "DO LDEPART 80",
    "DO LDEPART -80",
]



get_robot_status()
# reset_errors()
# motor_on()
# for cmd in cmd_list:
#     send_command(cmd)
# motor_off()
