"""Blink → click, tuned for webcam MediaPipe (eyes never look fully shut).

A blink is a *short, deep* dip. Looking down at a keyboard is a long dip —
that must not click. One noisy blink must not flicker into a false double.
"""

from __future__ import annotations

from collections import deque


class BlinkClicker:
    # Real blinks are short; look-down / squint lasts longer.
    BLINK_MIN_S = 0.05
    BLINK_MAX_S = 0.28
    # Intentional double-blink is tight; natural pairs are often farther apart.
    DOUBLE_S = 0.72
    # Eyes must stay open this long between counted blinks.
    # Stops one noisy blink from flickering into a false double.
    MIN_OPEN_BETWEEN_S = 0.12
    # After a click, ignore blinks briefly (lids often flutter).
    CLICK_COOLDOWN_S = 0.60
    # Enter closed below this fraction of open baseline; exit above OPEN_RATIO.
    CLOSE_RATIO = 0.72
    OPEN_RATIO = 0.90
    # Absolute minimum dip depth (webcam EAR units).
    MIN_DIP = 0.035

    def __init__(self) -> None:
        self.closed = False
        self.progress = 0.0
        self.ear = 0.0
        self.open_level = 0.0
        self.pending_blinks = 0
        self._hist: deque[float] = deque(maxlen=45)
        self._closed_since: float | None = None
        self._trough = 0.0
        self._invalid_close = False
        self._blinks: list[float] = []
        self._cool_until = 0.0

    def reset(self) -> None:
        """Clear in-flight blink state; keep the open-eye baseline."""
        self.closed = False
        self.progress = 0.0
        self.pending_blinks = 0
        self._closed_since = None
        self._trough = 0.0
        self._invalid_close = False
        self._blinks.clear()
        self._cool_until = 0.0

    def hard_reset(self) -> None:
        """Wipe baseline too (face left the camera)."""
        self.reset()
        self._hist.clear()
        self.open_level = 0.0
        self.ear = 0.0

    def update(self, ear: float, now: float, allow: bool) -> bool:
        """Return True when a double-blink click should fire.

        allow=False means "do not count blinks" (paused, typing, face cool-down).
        Baseline is kept so a burst of typing does not force a re-warmup.
        """
        self.ear = ear
        if not allow:
            self.reset()
            self._feed_open(ear)
            return False

        if now < self._cool_until:
            self._feed_open(ear)
            self.closed = False
            self.progress = 0.0
            self._closed_since = None
            self._invalid_close = False
            self.pending_blinks = len(self._blinks)
            return False

        self._feed_open(ear)
        if len(self._hist) < 10:
            self.open_level = max(self.open_level, ear)
            self.closed = False
            self.progress = 0.0
            self.pending_blinks = 0
            return False

        ordered = sorted(self._hist)
        self.open_level = ordered[int(len(ordered) * 0.80)]
        close_thresh = min(self.open_level * self.CLOSE_RATIO, self.open_level - self.MIN_DIP)
        open_thresh = max(
            close_thresh + 0.01,
            min(self.open_level * self.OPEN_RATIO, self.open_level - self.MIN_DIP * 0.4),
        )

        fired = False
        if not self.closed:
            if ear < close_thresh:
                self.closed = True
                self._closed_since = now
                self._trough = ear
                self._invalid_close = False
                self.progress = 0.0
        else:
            self._trough = min(self._trough, ear)
            held = now - (self._closed_since or now)
            self.progress = min(1.0, held / self.BLINK_MAX_S)
            # Look-down / long squint: abandon any half double-blink.
            if held > self.BLINK_MAX_S:
                self._invalid_close = True
                self._blinks.clear()

            if ear > open_thresh:
                fired = self._finish_close(now, held)
                self.closed = False
                self._closed_since = None
                self.progress = 0.0

        self._blinks = [t for t in self._blinks if now - t <= self.DOUBLE_S]
        self.pending_blinks = len(self._blinks)
        return fired

    def _finish_close(self, now: float, held: float) -> bool:
        if self._invalid_close:
            self._invalid_close = False
            return False

        dip = self.open_level - self._trough
        deep_enough = dip >= max(self.MIN_DIP, self.open_level * 0.12)
        duration_ok = self.BLINK_MIN_S <= held <= self.BLINK_MAX_S
        if not (deep_enough and duration_ok):
            return False

        # Open gap between previous blink stamp and this close starting.
        if self._blinks and self._closed_since is not None:
            gap = self._closed_since - self._blinks[-1]
            if gap < self.MIN_OPEN_BETWEEN_S:
                return False

        self._blinks = [t for t in self._blinks if now - t <= self.DOUBLE_S]
        self._blinks.append(now)
        if len(self._blinks) >= 2:
            self._blinks.clear()
            self._cool_until = now + self.CLICK_COOLDOWN_S
            return True
        return False

    def _feed_open(self, ear: float) -> None:
        """Only train the open baseline on confidently-open samples."""
        if ear <= 0.04:
            return
        if self.closed:
            return
        if self.open_level > 0 and ear < self.open_level * self.OPEN_RATIO:
            return
        self._hist.append(ear)
