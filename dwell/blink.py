"""Blink → click, tuned for webcam MediaPipe (eyes never look fully shut).

A blink is a *short* dip. Looking down at a keyboard is a long dip — that
must not click.
"""

from __future__ import annotations

from collections import deque


class BlinkClicker:
    BLINK_MIN_S = 0.04
    BLINK_MAX_S = 0.32
    DOUBLE_S = 1.10

    def __init__(self) -> None:
        self.closed = False
        self.progress = 0.0
        self.ear = 0.0
        self.open_level = 0.0
        self._hist: deque[float] = deque(maxlen=45)
        self._closed_since: float | None = None
        self._blinks: list[float] = []

    def reset(self) -> None:
        self.closed = False
        self.progress = 0.0
        self._closed_since = None
        self._blinks.clear()

    def update(self, ear: float, now: float, allow: bool) -> bool:
        self.ear = ear
        if not allow:
            self.reset()
            return False

        if ear > 0.04:
            self._hist.append(ear)
        if len(self._hist) < 8:
            self.open_level = ear
            self.closed = False
            return False

        ordered = sorted(self._hist)
        self.open_level = ordered[int(len(ordered) * 0.80)]
        thresh = min(self.open_level * 0.86, self.open_level - 0.025)
        closed = ear < thresh
        self.closed = closed

        if closed:
            if self._closed_since is None:
                self._closed_since = now
            held = now - self._closed_since
            self.progress = min(1.0, held / self.BLINK_MAX_S)
            return False

        self.progress = 0.0
        fired = False
        if self._closed_since is not None:
            held = now - self._closed_since
            # Looking at the keyboard stays "closed" too long. Only a quick blink counts.
            if self.BLINK_MIN_S <= held <= self.BLINK_MAX_S:
                self._blinks = [t for t in self._blinks if now - t <= self.DOUBLE_S]
                self._blinks.append(now)
                if len(self._blinks) >= 2:
                    self._blinks.clear()
                    fired = True
        self._closed_since = None
        return fired
