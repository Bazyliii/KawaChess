from kawachess import RobotCartesianPoint, RobotCommand, RobotConnection, RobotStatus

robot = RobotConnection("127.0.0.1/9105")
robot.login("as")

status: dict[RobotStatus, bool] = robot.status()
# STATUS HANDLING
if status[RobotStatus.ERROR]:
    robot.send(RobotCommand.RESET)
if not status[RobotStatus.MOTOR_POWERED]:
    robot.send(RobotCommand.MOTOR_ON)
if status[RobotStatus.REPEAT_MODE]:
    robot.send(RobotCommand.REPEAT_ONCE_ON)
if status[RobotStatus.STEP_ONCE]:
    robot.send(RobotCommand.STEP_ONCE_OFF)
if status[RobotStatus.CONTINUOUS_PATH]:
    robot.send(RobotCommand.CONTINUOUS_PATH_OFF)


home_point: RobotCartesianPoint = RobotCartesianPoint(robot, "home_point", 91.362, 554.329, -193.894, -137.238, 179.217, -5.03)
a1_point: RobotCartesianPoint = home_point.shift("a1_point", x=-10.0)
h4_point: RobotCartesianPoint = home_point.shift("h4_point", x=100.0, z=80)


# robot.send(RobotCommand.HOME)
# robot.send(RobotCommand.MOVE_TO_POINT, a1_point)
# robot.send(RobotCommand.MOVE_TO_POINT, h4_point)


program = """
SPEED 5 ALWAYS
HOME
HMOVE home_point
HMOVE a1_point
LDEPART 80
HMOVE h4_point
"""

robot.write_program(program, "test_program")


robot.send(RobotCommand.EXECUTE_PROG, "test_program")
