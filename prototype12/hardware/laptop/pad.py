"""Control pad -- drive the rover by hand from the laptop. Keyboard or a gamepad.

    python pad.py --rover 10.119.42.34
    python pad.py --rover 127.0.0.1            against server.py --fake

Keyboard: hold W A S D or the arrow keys. SPACE stops. 1-9 sets the power (9 = full
band), Q or closing the window quits.
Gamepad (Xbox, PlayStation, most USB/Bluetooth pads): left stick drives -- up/down
is forward/back, left/right turns, and how far you push is how fast. A / cross stops.

Releasing everything stops the rover. So does closing this window or losing wifi:
the rover stops itself 0.4 s after the last command it heard.

Driving by hand moves the rover without the grid knowing, so put it back on its start
cell facing north before Level 2 or 3 -- they reset the pose when they connect.
"""

import argparse
import os
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link import RoverLink  # noqa: E402

DEAD = 0.15          # stick deadzone
HZ = 20


def mix(throttle, turn):
    """Arcade mix: one stick to two sides. +turn is right."""
    left, right = throttle + turn, throttle - turn
    big = max(1.0, abs(left), abs(right))
    return left / big, right / big


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True)
    args = ap.parse_args()

    rover = RoverLink(args.rover, timeout=5)
    try:
        hi = rover.hello()
    except OSError as e:
        sys.exit(f"cannot reach the rover at {args.rover}:5005 ({e}). Is server.py running?")

    pygame.init()
    screen = pygame.display.set_mode((520, 300))
    pygame.display.set_caption(f"Rover pad -- {args.rover}" + ("  (fake)" if hi["fake"] else ""))
    font = pygame.font.SysFont("consolas", 18)
    big = pygame.font.SysFont("consolas", 28, bold=True)
    clock = pygame.time.Clock()
    pads = {}
    power = 0.6
    sent = (0.0, 0.0)
    status = "connected"

    try:
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.JOYDEVICEADDED:
                    j = pygame.joystick.Joystick(e.device_index)
                    pads[j.get_instance_id()] = j
                elif e.type == pygame.JOYDEVICEREMOVED:
                    pads.pop(e.instance_id, None)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_q:
                        running = False
                    elif e.key == pygame.K_SPACE:
                        rover.stop()          # a real stop: zero power alone does not end a drive
                    elif pygame.K_1 <= e.key <= pygame.K_9:
                        power = (e.key - pygame.K_0) / 9
                elif e.type == pygame.JOYBUTTONDOWN and e.button == 0:
                    rover.stop()

            k = pygame.key.get_pressed()
            throttle = (k[pygame.K_w] or k[pygame.K_UP]) - (k[pygame.K_s] or k[pygame.K_DOWN])
            turn = (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT])
            left, right = mix(throttle, turn)
            src = "keys"
            for j in pads.values():
                x, y = j.get_axis(0), -j.get_axis(1)
                if abs(x) > DEAD or abs(y) > DEAD:
                    left, right = mix(y if abs(y) > DEAD else 0, x if abs(x) > DEAD else 0)
                    src = j.get_name()[:28]
            if k[pygame.K_SPACE]:
                left = right = 0.0
            cmd = (left * power, right * power)

            try:
                if cmd != (0.0, 0.0) or sent != (0.0, 0.0):
                    rover.manual(*cmd)        # repeats while held; one zero when let go
                sent = cmd
                status = "connected"
            except OSError as e:
                status = f"link lost: {e}"[:48]
                try:
                    rover.connect()
                except OSError:
                    pass

            screen.fill((16, 22, 26))
            moving = cmd != (0.0, 0.0)
            screen.blit(big.render("DRIVING" if moving else "stopped", True,
                                   (120, 230, 140) if moving else (200, 200, 200)), (20, 16))
            lines = [f"left {cmd[0]:+.2f}   right {cmd[1]:+.2f}   ({src})",
                     f"power {power:.2f}   (keys 1-9)",
                     f"gamepads: {len(pads)}",
                     "",
                     "W A S D / arrows hold to drive    SPACE stop",
                     "gamepad: left stick, A = stop     Q quit",
                     "", status]
            for n, t in enumerate(lines):
                screen.blit(font.render(t, True, (220, 230, 235)), (20, 70 + n * 24))
            pygame.display.flip()
            clock.tick(HZ)
    finally:
        try:
            rover.manual(0, 0)
            rover.stop()
        except OSError:
            pass
        rover.close()
        pygame.quit()


if __name__ == "__main__":
    main()
