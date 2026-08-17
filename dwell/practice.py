"""On-screen targets so you can measure hits instead of guessing."""

from __future__ import annotations

import random

import cv2
import numpy as np

WINDOW = "Dwell Practice"
WIN_X, WIN_Y = 80, 60
WIN_W, WIN_H = 1100, 720
RADIUS = 44


class PracticeBoard:
    def __init__(self) -> None:
        self.on = False
        self.target = (WIN_W // 2, WIN_H // 2)
        self.hits = 0
        self.tries = 0
        self._place()

    def toggle(self) -> None:
        self.on = not self.on
        if self.on:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, WIN_W, WIN_H)
            cv2.moveWindow(WINDOW, WIN_X, WIN_Y)
            self.hits = 0
            self.tries = 0
            self._place()
        else:
            try:
                cv2.destroyWindow(WINDOW)
            except cv2.error:
                pass

    def on_click(self, screen_x: float, screen_y: float) -> None:
        if not self.on:
            return
        local_x = screen_x - WIN_X
        local_y = screen_y - WIN_Y
        self.tries += 1
        dx = local_x - self.target[0]
        dy = local_y - self.target[1]
        if dx * dx + dy * dy <= RADIUS * RADIUS:
            self.hits += 1
            self._place()

    def draw(self) -> None:
        if not self.on:
            return
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
        frame[:] = (28, 28, 28)
        cv2.circle(frame, self.target, RADIUS, (0, 180, 255), 3)
        cv2.circle(frame, self.target, 6, (0, 180, 255), -1)
        acc = f"{self.hits}/{self.tries}" if self.tries else "0/0"
        cv2.putText(
            frame,
            f"Hold still on the circle.  Hits {acc}    F2 close",
            (24, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (220, 220, 220),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(WINDOW, frame)

    def _place(self) -> None:
        margin = RADIUS + 30
        self.target = (
            random.randint(margin, WIN_W - margin),
            random.randint(margin + 40, WIN_H - margin),
        )
