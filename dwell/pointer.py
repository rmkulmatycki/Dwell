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

from pynput.mouse import Controller

from dwell.filters import OneEuro


def _send_left_click() -> None:
    # pynput click is ignored by some apps; this is the real Windows click.
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


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
    dwell_ms: int = 1100
    gain: float = 12.0
    last_click_ms: int | None = None
    hits: int = 0
    clicks: int = 0
    click_enabled: bool = False
    screen_w: int = 1920
    screen_h: int = 1080


class HeadPointer:
    def __init__(self, metrics_path: Path):
        self.screen_w, self.screen_h = _screen_size()
        self.mouse = Controller()
        self.fx = OneEuro(min_cutoff=0.45, beta=0.006)
        self.fy = OneEuro(min_cutoff=0.45, beta=0.006)
        self.rest_x = 0.5
        self.rest_y = 0.45
        self.gain = 12.0
        self.paused = True
        self.click_enabled = False
        self.deadzone = 10.0
        self.max_step = 90.0
        self._ever_centered = False
        self._out: tuple[float, float] | None = None
        self._still_since: float | None = None
        self.dwell_s = 1.10
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
        self._out = (self.screen_w * 0.5, self.screen_h * 0.5)
        self._prev_pos = None
        if not self.paused:
            self.mouse.position = (int(self._out[0]), int(self._out[1]))

    def set_input(self, source: str) -> None:
        if source == "gaze":
            self.fx.min_cutoff = 0.16
            self.fy.min_cutoff = 0.16
            self.fx.beta = 0.001
            self.fy.beta = 0.001
            self.deadzone = 26.0
            self.max_step = 38.0
        else:
            self.fx.min_cutoff = 0.45
            self.fy.min_cutoff = 0.45
            self.fx.beta = 0.006
            self.fy.beta = 0.006
            self.deadzone = 10.0
            self.max_step = 90.0

    def nudge_gain(self, delta: float) -> None:
        self.gain = max(2.0, min(50.0, self.gain + delta))

    def toggle_clicks(self) -> None:
        self.click_enabled = not self.click_enabled
        self._still_since = None

    def set_clicks(self, on: bool) -> None:
        self.click_enabled = on
        self._still_since = None

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._still_since = None
        if self.paused:
            self._pending_judge = None
            return
        # Unpausing: treat current head pose as "center of screen"
        # so the cursor does not jump to a random corner.
        self.recenter_next = True
        self.fx.reset()
        self.fy.reset()
        self._out = None
        self._prev_pos = None

    def blink_click(self, now: float, ignore_pause: bool = False) -> None:
        if self.paused and not ignore_pause:
            return
        pos = self.mouse.position
        self._click(now, float(pos[0]), float(pos[1]), kind="blink")

    def update(
        self,
        nx: float,
        ny: float,
        seen: bool,
        now: float,
        freeze: bool = False,
    ) -> PointerState:
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
        if seen and not self._ever_centered:
            self.recenter(nx, ny)
            self._ever_centered = True

        if not seen or self.paused:
            self._still_since = None
            return self._state(seen, progress)

        if freeze:
            return self._state(seen, progress)

        raw_x = self.screen_w * 0.5 + (nx - self.rest_x) * self.screen_w * (self.gain / 10.0)
        raw_y = self.screen_h * 0.5 + (ny - self.rest_y) * self.screen_h * (self.gain / 10.0)
        raw_x = min(self.screen_w - 2, max(1, raw_x))
        raw_y = min(self.screen_h - 2, max(1, raw_y))
        sx = self.fx(raw_x, now)
        sy = self.fy(raw_y, now)

        # Deadzone: ignore tiny wobble so the cursor can actually sit still.
        if self._out is None:
            self._out = (sx, sy)
        dx = sx - self._out[0]
        dy = sy - self._out[1]
        if (dx * dx + dy * dy) ** 0.5 < self.deadzone:
            sx, sy = self._out
        else:
            max_step = self.max_step
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > max_step:
                sx = self._out[0] + dx / dist * max_step
                sy = self._out[1] + dy / dist * max_step
            self._out = (sx, sy)

        self.mouse.position = (int(sx), int(sy))

        speed = 0.0
        if self._prev_pos is not None:
            speed = ((sx - self._prev_pos[0]) ** 2 + (sy - self._prev_pos[1]) ** 2) ** 0.5
        self._prev_pos = (sx, sy)

        if now - self._last_click_t < self.cooldown_s:
            self._still_since = None
            return self._state(seen, 0.0)

        if not self.click_enabled:
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

    def _click(self, now: float, sx: float, sy: float, kind: str = "dwell") -> None:
        self.mouse.position = (int(sx), int(sy))
        _send_left_click()
        self.clicks += 1
        self.last_click_ms = int(self.dwell_s * 1000)
        self._last_click_t = now
        self._last_click_pos = (sx, sy)
        self._pending_judge = (now, sx, sy)
        self._still_since = None
        self._log(kind, hit=None)

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
            click_enabled=self.click_enabled,
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
