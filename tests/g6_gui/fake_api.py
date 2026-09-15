"""A recording stand-in for G6Api, so GUI pages can be tested with no device."""

from __future__ import annotations

import inspect

from g6_cli.g6_api import G6Api
from g6_cli.g6_model import G6Model


class FakeG6Api:
    """Records every call instead of talking to USB.

    Methods are generated from ``G6Api`` at import time, so a new upstream API
    method automatically appears here rather than raising AttributeError deep
    inside a page.
    """

    def __init__(self, model: G6Model | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._model = model if model is not None else G6Model()
        self._next_error: Exception | None = None

    def get_model(self) -> G6Model:
        return self._model

    def fail_next(self, exception: Exception) -> None:
        self._next_error = exception

    def method_names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def _record(self, name: str, kwargs: dict):
        if self._next_error is not None:
            error, self._next_error = self._next_error, None
            raise error
        self.calls.append((name, kwargs))
        if name.endswith("_available") or name.startswith("is_"):
            return True
        if name == "sbx_profile_selection":
            return self._model.get_sbx_profile_selection()
        return None


def _install_methods():
    reserved = {"get_model", "sbx_profile_selection"}
    for name, _ in inspect.getmembers(G6Api, inspect.isfunction):
        if name.startswith("_") or name in reserved:
            continue

        def make(method_name):
            def method(self, **kwargs):
                return self._record(method_name, kwargs)

            method.__name__ = method_name
            return method

        setattr(FakeG6Api, name, make(name))


_install_methods()


def _sbx_profile_selection(self):
    self.calls.append(("sbx_profile_selection", {}))
    return self._model.get_sbx_profile_selection()


FakeG6Api.sbx_profile_selection = _sbx_profile_selection
