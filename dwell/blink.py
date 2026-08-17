"""Intentional blink → click.

Natural blinks are short. A click is either:
- hold the eyes shut ~0.4s, or
- two quick blinks (double blink)

A single ordinary blink does nothing.
"""

from __future__ import annotations


class BlinkClicker:
    LONG_S = 0.40
    SHORT_MIN_S = 0.07
    SHORT_MAX_S = 0.28
    DOUBLE_S = 0.55

    def __init__(self) -> None:
        self.open_ear = 0.28
        self.closed = False
        self.progress = 0.0
        self._closed_since: float | None = None
        self._fired_this_close = False
        self._last_short_t: float | None = None

    def reset(self) -> None:
        self.closed = False
        self.progress = 0.0
        self._closed_since = None
        self._fired_this_close = False

    def update(self, ear: float, now: float, allow: bool) -> bool:
        thresh = max(0.12, self.open_ear * 0.62)
        closed = ear < thresh
        self.closed = closed

        if not allow:
            self.reset()
            if ear > thresh:
                self._nudge_open(ear)
            return False

        if closed:
            if self._closed_since is None:
                self._closed_since = now
                self._fired_this_close = False
            held = now - self._closed_since
            self.progress = min(1.0, held / self.LONG_S)
            if held >= self.LONG_S and not self._fired_this_close:
                self._fired_this_close = True
                self._last_short_t = None
                return True
            return False

        self.progress = 0.0
        fired = False
        if self._closed_since is not None and not self._fired_this_close:
            held = now - self._closed_since
            if self.SHORT_MIN_S <= held <= self.SHORT_MAX_S:
                if self._last_short_t is not None and (now - self._last_short_t) <= self.DOUBLE_S:
                    fired = True
                    self._last_short_t = None
                else:
                    self._last_short_t = now
        self._closed_since = None
        self._fired_this_close = False
        if ear > thresh:
            self._nudge_open(ear)
        return fired

    def _nudge_open(self, ear: float) -> None:
        self.open_ear = 0.85 * self.open_ear + 0.15 * ear
