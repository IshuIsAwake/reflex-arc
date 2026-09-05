#!/usr/bin/env python3
"""stop_cmd.py -- publish zero Twist on /cmd_vel for ~0.7 s so the SmartElex motor
node LATCHES a STOP. Needed because deadman=0 (kept off so teleop is latched): when
Nav2 is killed (nav stop / stop) nothing else is publishing /cmd_vel, so without this
the motor would hold its last command and keep driving. Run AFTER the nav nodes are
killed (so the velocity_smoother isn't still publishing nonzero)."""
import time
import rclpy
from geometry_msgs.msg import Twist

rclpy.init()
n = rclpy.create_node('stop_cmd')
p = n.create_publisher(Twist, '/cmd_vel', 10)
t0 = time.time()
while time.time() - t0 < 0.7:
    p.publish(Twist())                       # all-zero = STOP
    rclpy.spin_once(n, timeout_sec=0.05)
    time.sleep(0.05)
n.destroy_node()
rclpy.shutdown()

