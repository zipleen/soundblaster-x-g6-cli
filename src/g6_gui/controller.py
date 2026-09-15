"""Marshals blocking G6Api calls off the UI thread and debounces slider traffic."""

from __future__ import annotations

import asyncio
import sys
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from g6_cli.g6_model import G6Model

DEFAULT_DEBOUNCE_SECONDS = 0.15


class G6Controller:
    """The single choke point between the GUI and the device.

    All device I/O runs on one worker thread, which both keeps the UI
    responsive and serialises writes so two of them cannot interleave on the
    wire.
    """

    def __init__(
        self,
        api,
        *,
        on_error: Callable[[str], None] | None = None,
        on_device_lost: Callable[[Exception], None] | None = None,
    ):
        self._api = api
        self._on_error = on_error
        self._on_device_lost = on_device_lost
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="g6-io")
        self._pending: dict[str, asyncio.Task] = {}
        self._in_flight: set[asyncio.Task] = set()

    @property
    def api(self):
        return self._api

    @property
    def model(self) -> G6Model:
        return self._api.get_model()

    async def call(self, method: str, **kwargs) -> Any:
        """Await a single device call on the worker thread."""
        loop = asyncio.get_running_loop()
        target = getattr(self._api, method)
        return await loop.run_in_executor(self._executor, lambda: target(**kwargs))

    def submit(
        self,
        method: str,
        *,
        revert: Callable[[], None] | None = None,
        on_success: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        """Fire a device call from a synchronous Toga handler. Returns immediately.

        `on_success` runs only if the call succeeded, as part of the same tracked
        unit of work that `flush()` awaits — so a caller doing
        `submit(...); await flush()` is guaranteed to observe its effect.
        """
        self._spawn(self._guarded(method, revert, kwargs, on_success))

    def debounced(
        self,
        key: str,
        method: str,
        *,
        delay: float = DEFAULT_DEBOUNCE_SECONDS,
        revert: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        """Fire a device call after `delay`, cancelling any earlier call with the same key.

        One slider drag becomes one USB write instead of a hundred.
        """
        existing = self._pending.pop(key, None)
        if existing is not None and not existing.done():
            existing.cancel()

        async def later():
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return
            self._pending.pop(key, None)
            await self._guarded(method, revert, kwargs)

        task = self._spawn(later())
        if isinstance(task, asyncio.Task):
            self._pending[key] = task

    async def flush(self) -> None:
        """Await every pending debounce and in-flight call. Used by tests."""
        while self._pending or self._in_flight:
            waiting = list(self._pending.values()) + list(self._in_flight)
            await asyncio.gather(*waiting, return_exceptions=True)

    def shutdown(self) -> None:
        for task in list(self._pending.values()):
            task.cancel()
        self._pending.clear()
        self._executor.shutdown(wait=False)

    # ── internals ──

    def _spawn(self, coro):
        """Schedule `coro` on the running loop.

        Toga event handlers normally run with the app's asyncio loop active, so
        this is just `ensure_future`. Outside a running loop — a synchronous
        test, or a handler invoked directly — `ensure_future` would raise and
        Toga would swallow the traceback, silently dropping the device call. In
        that case run the coroutine to completion instead, so the call still
        happens and the failure mode is visible rather than silent.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        task = asyncio.ensure_future(coro)
        self._in_flight.add(task)
        task.add_done_callback(self._in_flight.discard)
        return task

    async def _guarded(self, method: str, revert, kwargs: dict, on_success=None) -> None:
        try:
            await self.call(method, **kwargs)
        except asyncio.CancelledError:
            raise
        except IOError as exc:
            # The device vanished. The app returns to its "connect your G6" gate.
            if self._on_device_lost is not None:
                self._on_device_lost(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            traceback.print_exc(file=sys.stderr)
            if revert is not None:
                revert()
            if self._on_error is not None:
                self._on_error(f"{method} failed: {exc}")
        else:
            if on_success is not None:
                on_success()
