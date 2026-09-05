# Rover Drive Logic — pulled from Nithin's Pi (rover_ros2 project)

Source: `nithin@10.7.20.227`, container `rover_ros2`, `/root/` — the tested,
calibrated motor driver from Nithin's lidar/SLAM/Nav2 stack. Copied here
(drive logic only — none of the lidar/SLAM/Nav2 pieces) on 2026-09-04.

## What this actually drives

**Not** a plain L298N in the usual dual-direction-pin sense, despite the
filename (kept only so Nithin's `stack.sh` needs no changes). This is a
**SmartElex 15D** driver board in PWM independent mode:

- `PWM1`/`DIR1` (BCM 12 / 23) → Motor 1
- `PWM2`/`DIR2` (BCM 13 / 24) → Motor 2
- DIR high = clockwise/forward, low = counterclockwise/reverse
- Duty cycle: **8% = 0% motor speed, 94% = 100% motor speed**, linear in between; 0% duty = stopped
- Uses `gpiozero` (+ `lgpio` on Pi 5), not `RPi.GPIO`

## Files

- `l298n_node.py` — the ROS2 node (`rclpy`). Subscribes to `/cmd_vel`
  (`geometry_msgs/Twist`: `linear.x` = forward m/s, `angular.z` = turn rad/s),
  mixes to per-wheel duty via differential-drive kinematics, writes GPIO.
  Has a deadman watchdog (default 2.0s, disabled via `deadman:=0`) and a
  measured proportional duty model — **not** guesswork.
- `stop_cmd.py` — publishes zero Twist for ~0.7s to force-latch STOP (needed
  because the stack normally runs with `deadman=0` for latched teleop).
- `pub_cmd.py` — CLI: `pub_cmd.py <seconds> <linear_x> <angular_z>`, drives
  for a duration then stops. Useful reference for how to publish `/cmd_vel`
  correctly (waits for subscriber discovery, sends a stop burst in `finally`
  so it can't leave the rover latched-driving on exit).
- `motor_min_duty.txt` = `0.082`, `motor_max_duty.txt` = `0.154`,
  `motor_speed.txt` = `2` — **measured calibration** for this specific
  chassis (tyres/load/battery at time of measurement). Re-measure if any of
  those change. Fed into `l298n_node.py` as the `min_duty`/`max_duty`
  parameters (see the long comment block in that file — includes the actual
  duty→speed sweep data and why quantized levels broke Nav2's approach).

## Important: this is a ROS2 node, not a standalone script

`l298n_node.py` needs `rclpy` + a running ROS2 graph (it was launched inside
Nithin's `rover_ros2` Docker container via `stack.sh`). It will **not** run
as-is outside ROS2. Options going forward, TBD per next instructions:
1. Run it for real inside a ROS2 environment and drive it by publishing
   `/cmd_vel` (what `pub_cmd.py` does) — closest to "reuse exactly as tested".
2. Strip just the GPIO/PWM math (the `_chan`/`_apply`/`_level_to_duty`
   methods + the calibrated duty constants) into a non-ROS2 script for the
   Flask bridge (`rover_bridge/motor_control.py`) — reuses the *calibration*
   without the ROS2 dependency.

Not yet touched here: the lidar/rf2o/SLAM/Nav2 side of Nithin's stack
(`stack.sh`, `nav2_params.yaml`, `slam*.yaml`, etc.) — out of scope for "just
the drive logic".
