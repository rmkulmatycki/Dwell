"""Nose position → screen cursor → click if you hold still.

Closed loop v0: if a click looks accidental, dwell time gets longer. If you
meant it, dwell time gets shorter. You and the software train each other.
"""

from __future__ import annotations

import csv
import ctypes
import time
from dataclasses import dataclass
from pathlib import Path

from pynput.mouse import Button, Controller

from dwell.filters import OneEuro


def _screen_size() -> tuple[int, int]:
    # Without this, Windows scaling (125%/150%) maps the cursor to the wrong place.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


@dataclass
class PointerState:
    x: float = 0.0
    y: float = 0.0
    paused: bool = True
    seen: bool = False
    dwell_progress: float = 0.0  # 0–1 while holding still
    dwell_ms: int = 850
    gain: float = 14.0
    last_click_ms: int | None = None
    hits: int = 0
    clicks: int = 0
    screen_w: int = 1920
    screen_h: int = 1080


class HeadPointer:
    def __init__(self, metrics_path: Path):
        self.screen_w, self.screen_h = _screen_size()
        self.mouse = Controller()
        self.fx = OneEuro(min_cutoff=1.0, beta=0.008)
        self.fy = OneEuro(min_cutoff=1.0, beta=0.008)
        self.rest_x = 0.5
        self.rest_y = 0.45
        self.gain = 14.0
        self.paused = True
        self._still_since: float | None = None
        self.dwell_s = 0.85
        self.min_dwell = 0.45
        self.max_dwell = 1.45
        self.still_px = 22.0
        self.cooldown_s = 0.55
        self._last_click_t = 0.0
        self._last_click_pos: tuple[float, float] | None = None
        self._pending_judge: tuple[float, float, float] | None = None
        self.last_click_ms: int | None = None
        self.hits = 0
        self.clicks = 0
        self._prev_pos: tuple[float, float] | None = None
        self.metrics_path = metrics_path
        self.recenter_next = False
        self._ensure_metrics_header()

    def request_recenter(self) -> None:
        self.recenter_next = True

    def recenter(self, nx: float, ny: float) -> None:
        self.rest_x = nx
        self.rest_y = ny
        self.fx.reset()
        self.fy.reset()
        self._still_since = None
        self.recenter_next = False

    def nudge_gain(self, delta: float) -> None:
        self.gain = max(4.0, min(40.0, self.gain + delta))

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._still_since = None
        if self.paused:
            self._pending_judge = None

    def update(self, nx: float, ny: float, seen: bool, now: float) -> PointerState:
        if self._pending_judge is not None:
            click_t, cx, cy = self._pending_judge
            if now - click_t >= 0.4:
                dist = ((self.mouse.position[0] - cx) ** 2 + (self.mouse.position[1] - cy) ** 2) ** 0.5
                hit = dist < 48
                if hit:
                    self.hits += 1
                    self.dwell_s = max(self.min_dwell, self.dwell_s - 0.025)
                else:
                    self.dwell_s = min(self.max_dwell, self.dwell_s + 0.05)
                self._log("judge", hit=hit)
                self._pending_judge = None

        progress = 0.0
        if not seen or self.paused:
            self._still_since = None
            return self._state(seen, progress)

        sx = self.screen_w * 0.5 + (nx - self.rest_x) * self.screen_w * (self.gain / 10.0)
        sy = self.screen_h * 0.5 + (ny - self.rest_y) * self.screen_h * (self.gain / 10.0)
        sx = min(self.screen_w - 2, max(1, sx))
        sy = min(self.screen_h - 2, max(1, sy))
        sx = self.fx(sx, now)
        sy = self.fy(sy, now)

        self.mouse.position = (int(sx), int(sy))

        speed = 0.0
        if self._prev_pos is not None:
            speed = ((sx - self._prev_pos[0]) ** 2 + (sy - self._prev_pos[1]) ** 2) ** 0.5
        self._prev_pos = (sx, sy)

        if now - self._last_click_t < self.cooldown_s:
            self._still_since = None
            return self._state(seen, 0.0)

        if speed < self.still_px:
            if self._still_since is None:
                self._still_since = now
            held = now - self._still_since
            progress = min(1.0, held / self.dwell_s)
            if held >= self.dwell_s:
                self._click(now, sx, sy)
                progress = 0.0
        else:
            self._still_since = None

        return self._state(seen, progress)

    def _click(self, now: float, sx: float, sy: float) -> None:
        self.mouse.click(Button.left, 1)
        self.clicks += 1
        self.last_click_ms = int(self.dwell_s * 1000)
        self._last_click_t = now
        self._last_click_pos = (sx, sy)
        self._pending_judge = (now, sx, sy)
        self._still_since = None
        self._log("click", hit=None)

    def _state(self, seen: bool, progress: float) -> PointerState:
        pos = self.mouse.position
        return PointerState(
            x=float(pos[0]),
            y=float(pos[1]),
            paused=self.paused,
            seen=seen,
            dwell_progress=progress,
            dwell_ms=int(self.dwell_s * 1000),
            gain=self.gain,
            last_click_ms=self.last_click_ms,
            hits=self.hits,
            clicks=self.clicks,
            screen_w=self.screen_w,
            screen_h=self.screen_h,
        )

    def _ensure_metrics_header(self) -> None:
        if self.metrics_path.exists():
            return
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self.metrics_path.open("w", newline="") as f:
            csv.writer(f).writerow(
                ["unix_time", "event", "dwell_ms", "gain", "clicks", "hits", "hit"]
            )

    def _log(self, event: str, hit: bool | None) -> None:
        with self.metrics_path.open("a", newline="") as f:
            csv.writer(f).writerow(
                [
                    f"{time.time():.3f}",
                    event,
                    int(self.dwell_s * 1000),
                    f"{self.gain:.2f}",
                    self.clicks,
                    self.hits,
                    "" if hit is None else int(hit),
                ]
            )
