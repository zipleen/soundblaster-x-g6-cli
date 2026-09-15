from __future__ import annotations

import inspect

import pytest

from g6_cli.g6_api import G6Api
from g6_cli.g6_model import G6Model
from tests.g6_gui.fake_api import FakeG6Api


def test_records_calls_in_order():
    api = FakeG6Api()
    api.playback_enable_direct_mode(enable=True)
    api.lighting_enable_set_rgb(red=1, green=2, blue=3)
    assert api.calls == [
        ("playback_enable_direct_mode", {"enable": True}),
        ("lighting_enable_set_rgb", {"red": 1, "green": 2, "blue": 3}),
    ]
    assert api.method_names() == ["playback_enable_direct_mode", "lighting_enable_set_rgb"]


def test_exposes_a_real_model():
    assert isinstance(FakeG6Api().get_model(), G6Model)


def test_fail_next_raises_once():
    api = FakeG6Api()
    api.fail_next(IOError("device gone"))
    with pytest.raises(IOError):
        api.playback_enable_direct_mode(enable=True)
    api.playback_enable_direct_mode(enable=True)  # must not raise again
    assert api.method_names() == ["playback_enable_direct_mode"]


def test_covers_every_public_g6api_method():
    """If G6Api grows a method, the fake must grow with it or pages can silently drift."""
    real = {
        name
        for name, _ in inspect.getmembers(G6Api, inspect.isfunction)
        if not name.startswith("_")
    }
    fake = {name for name in dir(FakeG6Api) if not name.startswith("_")}
    assert real - fake == set()
