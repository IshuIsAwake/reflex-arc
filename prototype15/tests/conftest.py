"""What every test shares: settings put back after each test, and threads that run inline."""
import types

import pytest

import chat
import config
import dashboard
import nav
import settings


@pytest.fixture(autouse=True)
def fresh_settings(tmp_path):
    # Tests change settings and the arena freely; each one starts from the same place.
    saved_settings = dict(vars(settings))
    saved_config = dict(vars(config))
    saved_threading = chat.threading
    saved_hint = dashboard.ROVER_HINT
    settings.STORM_ON = False  # clear skies unless a test turns the storm on
    settings.PLAN_FILE = str(tmp_path / "plan.txt")
    yield
    vars(settings).update(saved_settings)
    vars(config).update(saved_config)
    chat.threading = saved_threading
    dashboard.ROVER_HINT = saved_hint
    nav.wait_for_rover = None
    nav.leg_started = None
    nav.leg_finished = None
    nav.rover_driving = None


class Inline:
    """A 'thread' that runs where it stands, so one send() drives a whole exchange."""

    def __init__(self, target, args=(), daemon=False):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def inline_threads():
    chat.threading = types.SimpleNamespace(Thread=Inline)
