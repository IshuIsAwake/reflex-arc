"""Display telemetry must follow playback, not the already-completed world."""
import unittest
from types import SimpleNamespace

from anim import Reel


class TelemetryTests(unittest.TestCase):
    def test_route_dots_remain_as_rover_passes(self):
        self.reel._load(self.route)
        self.reel._apply('at', (2, 2))
        self.reel._apply('plan', [(2, 2), (3, 2), (3, 3)])
        self.assertEqual(self.reel.plan, [(2, 2), (3, 2), (3, 3)])
        self.reel._apply('step', ((3, 2), []))
        self.assertEqual(self.reel.plan, [(2, 2), (3, 2), (3, 3)])
        self.reel._apply('step', ((3, 3), []))
        self.assertEqual(self.reel.plan, [(2, 2), (3, 2), (3, 3)])
        self.reel._apply('probe', [(3, 3), (4, 3)])
        self.assertEqual(self.reel.probe, [(3, 3), (4, 3)])

    def setUp(self):
        self.route = [('start', (2, 2)), ('plan', [(2, 2), (3, 2), (3, 3)]),
                      ('step', ((3, 2), [])), ('step', ((3, 3), []))]
        self.world = SimpleNamespace(pos=(3, 3), reel=[self.route])
        self.reel = Reel(self.world)

    def test_arrival_follows_playback_and_survives_cleanup(self):
        self.reel.tick(0.001)
        self.assertEqual(self.reel.where(self.world.pos), (2, 2))
        self.assertEqual(self.reel.destination, (3, 3))
        self.assertEqual(self.reel.destination_status, 'APPROACHING')
        self.reel.tick(30)
        self.reel.tick(1)
        self.assertEqual(self.reel.destination_status, 'REACHED')

    def test_a_refused_cell_reads_as_blocked(self):
        self.reel._load(self.route)
        self.reel._apply('at', (3, 2))
        self.reel._apply('block', (3, 1))
        self.assertEqual(self.reel.destination_status, 'BLOCKED / REPLANNING')

    def test_skip_keeps_the_last_queued_destination(self):
        self.reel.tick(0.001)
        self.world.reel.append([('start', (3, 3)), ('plan', [(3, 3), (2, 3)]),
                                ('step', ((2, 3), []))])
        self.world.pos = (2, 3)
        self.reel.skip()
        self.assertEqual(self.reel.destination, (2, 3))
        self.assertEqual(self.reel.destination_status, 'REACHED')

    def test_price_probe_does_not_claim_a_drive_destination(self):
        self.reel._load([('start', (3, 3)), ('probe', [(3, 3), (4, 3)])])
        self.assertIsNone(self.reel.destination)



if __name__ == '__main__':
    unittest.main()
