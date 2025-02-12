import asyncio

from kawachess.gripper import Gripper
from kawachess.robot import Cartesian, Move, Point, Robot


def calculate_point_to_move(algebraic_move: str, home: Point, z: float = 0.0) -> Point:
    x: int = ord(algebraic_move[0]) - ord("a")
    y: int = int(algebraic_move[1]) - 1
    return home.shift(algebraic_move, Cartesian(x=x * -40, y=y * -40, z=z))


if __name__ == "__main__":
    robot = Robot(ip="192.168.1.155", port=23)
    robot.connect()
    gripper = Gripper(open_value=800, close_value=1065)
    robot.home()
    A1 = Point("a1", Cartesian(x=93.395, y=547.541, z=-210.056, o=164.851, a=179.143, t=-108.635))
    A1_up = A1.shift("a1_up", Cartesian(z=80.0))
    H8 = calculate_point_to_move("h8", A1, z=0.0)
    H8_up = H8.shift("h8_up", Cartesian(z=80.0))
    A8 = calculate_point_to_move("a8", A1, z=0.0)
    A8_up = A8.shift("a8_up", Cartesian(z=80.0))
    H1 = calculate_point_to_move("h1", A1, z=0.0)
    H1_up = H1.shift("h1_up", Cartesian(z=80.0))

    robot.add_point(A1, H8, A1_up, H8_up, A8, A8_up)
    robot.move(Move.LINEAR, A1_up)
    gripper.open()
    robot.move(Move.LINEAR, A1)
    gripper.close()
    robot.move(Move.LINEAR, A1_up)
    robot.move(Move.LINEAR, H8_up)
    robot.move(Move.LINEAR, H8)
    gripper.open()
    robot.move(Move.LINEAR, H8_up)
    robot.move(Move.LINEAR, H8)
    gripper.close()
    robot.move(Move.LINEAR, H8_up)
    robot.move(Move.LINEAR, H1_up)
    robot.move(Move.LINEAR, H1)
    gripper.open()
    robot.move(Move.LINEAR, H1_up)
    robot.move(Move.LINEAR, H1)
    gripper.close()
    robot.move(Move.LINEAR, H1_up)
    robot.move(Move.LINEAR, A8_up)
    robot.move(Move.LINEAR, A8)
    gripper.open()
    robot.move(Move.LINEAR, A8_up)
    robot.home()
    robot.disconnect()
