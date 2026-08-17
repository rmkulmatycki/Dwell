"""Intentional blink → click.

Any close→open that isn't a long hold counts as a blink.
Two blinks within a second = click. Holding shut ~0.5s also clicks.

Hysteresis so webcam EAR flicker doesn't eat the double blink.
"""

from __future__ import annotations


class BlinkClicker:
    LONG_S = 0.50
    BLINK_MIN_S = 0.04
    DOUBLE_S = 0.95

    def __init__(self) -> None:
        self.open_ear = 0.30
        self.closed = False
        self.progress = 0.0
        self.unstable = False
        self._closed_since: float | None = None
        self._fired_this_close = False
        self._blinks: list[float] = []

    def reset(self) -> None:
        self.closed = False
        self.progress = 0.0
        self.unstable = False
        self._closed_since = None
        self._fired_this_close = False
        self._blinks.clear()

    def update(self, ear: float, now: float, allow: bool) -> bool:
        close_thresh = max(0.10, self.open_ear * 0.55)
        open_thresh = max(0.13, self.open_ear * 0.74)
        squint_thresh = max(0.16, self.open_ear * 0.85)

        if ear > open_thresh:
            self._nudge_open(ear)

        if self.closed:
            closed = ear < open_thresh
        else:
            closed = ear < close_thresh
        self.closed = closed
        self.unstable = ear < squint_thresh

        if not allow:
            self.reset()
            self.unstable = ear < squint_thresh
            return False

        if closed:
            if self._closed_since is None:
                self._closed_since = now
                self._fired_this_close = False
            held = now - self._closed_since
            self.progress = min(1.0, held / self.LONG_S)
            if held >= self.LONG_S and not self._fired_this_close:
                self._fired_this_close = True
                self._blinks.clear()
                return True
            return False

        self.progress = 0.0
        fired = False
        if self._closed_since is not None and not self._fired_this_close:
            held = now - self._closed_since
            if held >= self.BLINK_MIN_S:
                self._blinks = [t for t in self._blinks if now - t <= self.DOUBLE_S]
                self._blinks.append(now)
                if len(self._blinks) >= 2:
                    self._blinks.clear()
                    fired = True
        self._closed_since = None
        self._fired_this_close = False
        return fired

    def _nudge_open(self, ear: float) -> None:
        self.open_ear = 0.92 * self.open_ear + 0.08 * ear
