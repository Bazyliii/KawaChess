from kawachess.astemplates import move_without_capture
from kawachess.robot import Robot, Program, Point, Cartesian
from time import sleep
robot = Robot("192.168.1.155", 23)
robot.connect()

a1 = Point("a1", Cartesian(x=300.362, y=448.329, z=-93.894, o=169.414, a=178.057, t=-100.290))
a2 = Point("a2", Cartesian(x=250.362, y=448.329, z=-93.894, o=169.414, a=178.057, t=-100.290))
robot.add_point(a1, a2)

x = move_without_capture(a1, a2, a1, 10, 40)
print(x.name)
robot.load_program(x)
robot.exec_program(x)
