"""Level 1: drive the rover by hand from the laptop, with the keyboard or a gamepad.
Double-click to run, or:

    python level1_pad.py                       finds the Pi by hardware/rover_address.txt
    python level1_pad.py --rover 127.0.0.1     against server.py --fake

Keyboard: hold W A S D or the arrow keys. SPACE stops. 1-9 sets the power (9 = full band);
Q or closing the window quits. Gamepad: the left stick drives (up/down is forward/back,
left/right turns, and how far you push is how fast); A or cross stops.

Letting go stops the rover, and so does closing this window or losing wifi: the rover
stops itself 0.4 s after the last command it heard. Driving by hand moves the rover
without the grid knowing, so put it back on its start cell facing north before Level 3.
"""

import argparse
import sys

import pygame

import launch
from link import RoverLink

DEAD = 0.15  # stick deadzone
HZ = 20


def mix(throttle, turn):
    """Arcade mix: one stick to two sides. +turn is right."""
    left = throttle + turn
    right = throttle - turn
    big = max(1.0, abs(left), abs(right))
    return left / big, right / big


def wheel_power(pads):
    """(left, right) from the keys held, or from a gamepad's stick if it is pushed, and
    where it came from."""
    k = pygame.key.get_pressed()
    throttle = (k[pygame.K_w] or k[pygame.K_UP]) - (k[pygame.K_s] or k[pygame.K_DOWN])
    turn = (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT])
    left, right = mix(throttle, turn)
    source = "keys"
    for pad in pads.values():
        x = pad.get_axis(0)
        y = -pad.get_axis(1)
        if abs(x) > DEAD or abs(y) > DEAD:
            if abs(x) <= DEAD:
                x = 0
            if abs(y) <= DEAD:
                y = 0
            left, right = mix(y, x)
            source = pad.get_name()[:28]
    if k[pygame.K_SPACE]:
        left = 0.0
        right = 0.0
    return left, right, source


def draw(screen, font, big, cmd, source, power, pads, status):
    screen.fill((16, 22, 26))
    if cmd != (0.0, 0.0):
        screen.blit(big.render("DRIVING", True, (120, 230, 140)), (20, 16))
    else:
        screen.blit(big.render("stopped", True, (200, 200, 200)), (20, 16))
    lines = [f"left {cmd[0]:+.2f}   right {cmd[1]:+.2f}   ({source})",
             f"power {power:.2f}   (keys 1-9)",
             f"gamepads: {len(pads)}",
             "",
             "W A S D / arrows hold to drive    SPACE stop",
             "gamepad: left stick, A = stop     Q quit",
             "",
             status]
    for n, text in enumerate(lines):
        screen.blit(font.render(text, True, (220, 230, 235)), (20, 70 + n * 24))
    pygame.display.flip()


def main():
    ap = argparse.ArgumentParser(description="Level 1: drive the rover by hand")
    ap.add_argument("--rover", required=True)
    args = ap.parse_args()

    rover = RoverLink(args.rover, timeout=5)
    try:
        hi = rover.hello()
    except OSError as e:
        sys.exit(f"cannot reach the rover at {args.rover}:5005 ({e}). Is server.py running?")

    pygame.init()
    screen = pygame.display.set_mode((520, 300))
    title = f"Rover pad -- {args.rover}"
    if hi["fake"]:
        title += "  (fake)"
    pygame.display.set_caption(title)
    font = pygame.font.SysFont("consolas", 18)
    big = pygame.font.SysFont("consolas", 28, bold=True)
    clock = pygame.time.Clock()
    pads = {}  # gamepads plugged in, by instance id
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
                    pad = pygame.joystick.Joystick(e.device_index)
                    pads[pad.get_instance_id()] = pad
                elif e.type == pygame.JOYDEVICEREMOVED:
                    pads.pop(e.instance_id, None)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_q:
                        running = False
                    elif e.key == pygame.K_SPACE:
                        rover.stop()  # a real stop: zero power alone does not end a drive
                    elif pygame.K_1 <= e.key <= pygame.K_9:
                        power = (e.key - pygame.K_0) / 9
                elif e.type == pygame.JOYBUTTONDOWN and e.button == 0:
                    rover.stop()

            left, right, source = wheel_power(pads)
            cmd = (left * power, right * power)
            try:
                # Sent again every frame while held, and once more as zero when let go.
                if cmd != (0.0, 0.0) or sent != (0.0, 0.0):
                    rover.manual(*cmd)
                sent = cmd
                status = "connected"
            except OSError as e:
                status = f"link lost: {e}"[:48]
                try:
                    rover.connect()
                except OSError:
                    pass
            draw(screen, font, big, cmd, source, power, pads, status)
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
    launch.run(main)
