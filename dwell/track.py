"""Webcam → gaze (iris in the eye) with nose as fallback.

Not mind-reading. The camera sees where the irises sit in the eyelids.
Look left/right/up/down to aim. Blink is handled separately.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from types import SimpleNamespace
import time

import cv2
import mediapipe as mp

NOSE_TIP = 4
RIGHT_IRIS = 468
LEFT_IRIS = 473

LEFT_EYE = (159, 145, 133, 33, 158, 153)
RIGHT_EYE = (386, 374, 362, 263, 385, 380)


@dataclass
class FaceSignal:
    # Gaze is iris offset in the eye (~0 at center). Nose is 0–1 in the frame.
    x: float
    y: float
    seen: bool
    source: str
    ear: float
    eyes_closed: bool
    gaze_ok: bool
    unstable: bool


class FaceTracker:
    def __init__(self, camera_index: int = 0):
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(
                "Could not open the webcam. Close Zoom/Discord/Teams and try again."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.prefer_gaze = True
        self._gx = _SignalSmooth()
        self._gy = _SignalSmooth()
        self._held: tuple[float, float] | None = None
        self._open_ear = 0.30
        self._hold_until = 0.0

    def toggle_gaze(self) -> None:
        self.prefer_gaze = not self.prefer_gaze
        self._gx.reset()
        self._gy.reset()
        self._held = None

    def read(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None, FaceSignal(0.0, 0.0, False, "nose", 0.3, False, False, False)

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._mesh.process(rgb)

        blank = FaceSignal(0.0, 0.0, False, "nose", 0.3, False, False, False)
        if not result.multi_face_landmarks:
            self._gx.reset()
            self._gy.reset()
            self._held = None
            return frame, blank

        lm = result.multi_face_landmarks[0].landmark
        h, w = frame.shape[:2]
        nose = lm[NOSE_TIP]
        ear = 0.5 * (_ear(lm, LEFT_EYE) + _ear(lm, RIGHT_EYE))
        if ear > self._open_ear * 0.9:
            self._open_ear = 0.95 * self._open_ear + 0.05 * ear
        squint = ear < self._open_ear * 0.85
        closed = ear < max(0.12, self._open_ear * 0.55)
        if squint:
            self._hold_until = time.perf_counter() + 0.20
        freeze_gaze = squint or time.perf_counter() < self._hold_until
        gaze_ok = False
        gx, gy = 0.0, 0.0

        if self.prefer_gaze and len(lm) > LEFT_IRIS:
            try:
                left_c = _iris_center(lm, range(473, 478))
                right_c = _iris_center(lm, range(468, 473))
                if freeze_gaze:
                    if self._held is not None:
                        gx, gy = self._held
                        gaze_ok = True
                else:
                    lx, ly = _offset(left_c, lm, LEFT_EYE)
                    rx, ry = _offset(right_c, lm, RIGHT_EYE)
                    gx = max(-0.4, min(0.4, 0.5 * (lx + rx)))
                    gy = max(-0.4, min(0.4, 0.5 * (ly + ry)))
                    gx = self._gx(gx)
                    gy = self._gy(gy)
                    self._held = (gx, gy)
                    gaze_ok = True
                if gaze_ok:
                    _dot(frame, left_c, w, h, (255, 200, 0))
                    _dot(frame, right_c, w, h, (255, 200, 0))
            except (IndexError, ZeroDivisionError):
                gaze_ok = False

        if gaze_ok:
            signal = FaceSignal(gx, gy, True, "gaze", ear, closed, True, freeze_gaze)
        else:
            signal = FaceSignal(
                float(nose.x), float(nose.y), True, "nose", ear, closed, False, freeze_gaze
            )

        color = (0, 80, 255) if closed else (0, 220, 120)
        _dot(frame, nose, w, h, color, 6)
        return frame, signal

    def close(self) -> None:
        self._mesh.close()
        self.cap.release()


def _dot(frame, pt, w: int, h: int, color: tuple[int, int, int], r: int = 4) -> None:
    cv2.circle(frame, (int(pt.x * w), int(pt.y * h)), r, color, -1)


def _dist(a, b) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _ear(lm, eye: tuple[int, int, int, int, int, int]) -> float:
    top, bot, inner, outer, top2, bot2 = eye
    vertical = _dist(lm[top], lm[bot]) + _dist(lm[top2], lm[bot2])
    horizontal = _dist(lm[inner], lm[outer])
    return vertical / (2.0 * horizontal + 1e-6)


def _iris_center(lm, indices):
    xs = [lm[i].x for i in indices]
    ys = [lm[i].y for i in indices]
    return SimpleNamespace(x=sum(xs) / len(xs), y=sum(ys) / len(ys))


def _offset(iris, lm, eye: tuple[int, int, int, int, int, int]) -> tuple[float, float]:
    top, bot, inner, outer, _t2, _b2 = eye
    mid_x = 0.5 * (lm[inner].x + lm[outer].x)
    mid_y = 0.5 * (lm[top].y + lm[bot].y)
    width = abs(lm[outer].x - lm[inner].x) + 1e-6
    height = abs(lm[bot].y - lm[top].y) + 1e-6
    return (iris.x - mid_x) / width, (iris.y - mid_y) / height


class _SignalSmooth:
    """Median of the last few samples, then a slow average. Kills iris flicker."""

    def __init__(self, window: int = 7, alpha: float = 0.18) -> None:
        self._buf: deque[float] = deque(maxlen=window)
        self._ema: float | None = None
        self._alpha = alpha

    def reset(self) -> None:
        self._buf.clear()
        self._ema = None

    def __call__(self, x: float) -> float:
        self._buf.append(x)
        ordered = sorted(self._buf)
        med = ordered[len(ordered) // 2]
        if abs(x - med) > 0.10:
            x = med
        if self._ema is None:
            self._ema = med
        else:
            self._ema = self._alpha * med + (1.0 - self._alpha) * self._ema
        return self._ema
