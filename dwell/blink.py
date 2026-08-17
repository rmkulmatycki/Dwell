"""Blink → click, tuned for webcam MediaPipe (eyes never look fully shut).

A blink is a quick dip below your recent open-eye level, then back up.
Two dips in about a second = click. A held dip also clicks.
"""

from __future__ import annotations

from collections import deque


class BlinkClicker:
    LONG_S = 0.40
    BLINK_MIN_S = 0.03
    DOUBLE_S = 1.10

    def __init__(self) -> None:
        self.closed = False
        self.progress = 0.0
        self.ear = 0.0
        self.open_level = 0.0
        self._hist: deque[float] = deque(maxlen=45)
        self._closed_since: float | None = None
        self._fired_this_close = False
        self._blinks: list[float] = []

    def reset(self) -> None:
        self.closed = False
        self.progress = 0.0
        self._closed_since = None
        self._fired_this_close = False
        self._blinks.clear()

    def update(self, ear: float, now: float, allow: bool) -> bool:
        self.ear = ear
        if ear > 0.04:
            self._hist.append(ear)
        if len(self._hist) < 8:
            self.open_level = ear
            self.closed = False
            return False

        ordered = sorted(self._hist)
        self.open_level = ordered[int(len(ordered) * 0.80)]
        # Webcam blinks only dip a little. Catch a relative drop OR a small absolute drop.
        thresh = min(self.open_level * 0.86, self.open_level - 0.025)
        closed = ear < thresh
        self.closed = closed

        if not allow:
            self.progress = 0.0
            self._closed_since = None
            self._fired_this_close = False
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
