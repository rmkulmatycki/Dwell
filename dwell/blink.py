"""Intentional blink → click.

Calibrates to your open-eye size first so a normal face is not treated as
always-blinking (that froze the cursor).
"""

from __future__ import annotations


class BlinkClicker:
    LONG_S = 0.50
    BLINK_MIN_S = 0.04
    DOUBLE_S = 0.95
    BOOT_FRAMES = 12

    def __init__(self) -> None:
        self.open_ear = 0.0
        self.closed = False
        self.progress = 0.0
        self._boot: list[float] = []
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
        if self.open_ear <= 0.0:
            if ear > 0.05:
                self._boot.append(ear)
            if len(self._boot) < self.BOOT_FRAMES:
                self.closed = False
                self.progress = 0.0
                return False
            self.open_ear = sorted(self._boot)[len(self._boot) // 2]

        close_thresh = self.open_ear * 0.48
        open_thresh = self.open_ear * 0.68

        if ear > open_thresh:
            self.open_ear = 0.97 * self.open_ear + 0.03 * ear

        if self.closed:
            closed = ear < open_thresh
        else:
            closed = ear < close_thresh
        self.closed = closed

        if not allow:
            self.progress = 0.0
            self._closed_since = None
            self._fired_this_close = False
            self.closed = False
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
