"""Synthetic EAR sequences — no webcam required."""

from __future__ import annotations

import unittest

from dwell.blink import BlinkClicker


def _warmup(b: BlinkClicker, t0: float = 0.0, ear: float = 0.30, n: int = 20) -> float:
    t = t0
    for _ in range(n):
        b.update(ear, t, allow=True)
        t += 1 / 30
    return t


def _blink(b: BlinkClicker, t: float, open_ear: float = 0.30, closed_ear: float = 0.12, held: float = 0.12):
    """Simulate one clean blink starting at t; return time after reopen."""
    dt = 1 / 30
    # enter closed
    end_close = t + held
    while t < end_close:
        assert not b.update(closed_ear, t, allow=True)
        t += dt
    # reopen
    fired = b.update(open_ear, t, allow=True)
    t += dt
    # settle open a bit
    for _ in range(4):
        fired = b.update(open_ear, t, allow=True) or fired
        t += dt
    return t, fired


class BlinkClickerTests(unittest.TestCase):
    def test_single_blink_does_not_click(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        t, fired = _blink(b, t)
        self.assertFalse(fired)
        self.assertEqual(b.pending_blinks, 1)

    def test_double_blink_clicks(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        t, fired = _blink(b, t)
        self.assertFalse(fired)
        t, fired = _blink(b, t + 0.15)
        self.assertTrue(fired)
        self.assertEqual(b.pending_blinks, 0)

    def test_slow_pair_does_not_click(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        t, _ = _blink(b, t)
        # Wait past DOUBLE_S before second blink.
        t, fired = _blink(b, t + 1.0)
        self.assertFalse(fired)
        self.assertEqual(b.pending_blinks, 1)

    def test_look_down_does_not_click(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        # Long close = looking at keyboard.
        for _ in range(40):
            self.assertFalse(b.update(0.10, t, allow=True))
            t += 1 / 30
        self.assertTrue(b.closed or b._invalid_close or not b._blinks)
        # Reopen — must not count as a blink, and pending must be empty.
        fired = b.update(0.30, t, allow=True)
        self.assertFalse(fired)
        self.assertEqual(b.pending_blinks, 0)

    def test_look_down_clears_pending_blink(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        t, _ = _blink(b, t)
        self.assertEqual(b.pending_blinks, 1)
        for _ in range(40):
            b.update(0.10, t, allow=True)
            t += 1 / 30
        b.update(0.30, t, allow=True)
        self.assertEqual(b.pending_blinks, 0)

    def test_flicker_does_not_double_count(self) -> None:
        """One blink that briefly flickers open must not become a click."""
        b = BlinkClicker()
        t = _warmup(b)
        open_e, closed_e = 0.30, 0.12
        # First close
        for _ in range(4):
            b.update(closed_e, t, allow=True)
            t += 1 / 30
        # Flicker open one frame, then closed again immediately.
        b.update(open_e, t, allow=True)
        t += 1 / 30
        for _ in range(4):
            fired = b.update(closed_e, t, allow=True)
            self.assertFalse(fired)
            t += 1 / 30
        fired = b.update(open_e, t, allow=True)
        # At most one blink counted — never a click from flicker alone.
        self.assertFalse(fired)
        self.assertLessEqual(b.pending_blinks, 1)

    def test_shallow_dip_ignored(self) -> None:
        b = BlinkClicker()
        t = _warmup(b, ear=0.30)
        # Tiny squint — not a real blink.
        for _ in range(4):
            b.update(0.27, t, allow=True)
            t += 1 / 30
        fired = b.update(0.30, t, allow=True)
        self.assertFalse(fired)
        self.assertEqual(b.pending_blinks, 0)

    def test_disallow_clears_pending_keeps_baseline(self) -> None:
        b = BlinkClicker()
        t = _warmup(b)
        baseline = b.open_level
        t, _ = _blink(b, t)
        self.assertEqual(b.pending_blinks, 1)
        b.update(0.30, t, allow=False)
        self.assertEqual(b.pending_blinks, 0)
        self.assertGreater(b.open_level, 0.0)
        self.assertAlmostEqual(b.open_level, baseline, delta=0.05)

    def test_hard_reset_wipes_baseline(self) -> None:
        b = BlinkClicker()
        _warmup(b)
        b.hard_reset()
        self.assertEqual(len(b._hist), 0)
        self.assertEqual(b.open_level, 0.0)


if __name__ == "__main__":
    unittest.main()
