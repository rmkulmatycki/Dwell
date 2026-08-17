"""Webcam → gaze (iris in the eye) with nose as fallback.

Not mind-reading. The camera sees where the irises sit in the eyelids.
Look left/right/up/down to aim. Blink is handled separately.
"""

from __future__ import annotations

from dataclasses import dataclass

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

    def read(self) -> tuple[np.ndarray | None, FaceSignal]:
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None, FaceSignal(0.0, 0.0, False, "nose", 0.3, False, False)

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._mesh.process(rgb)

        blank = FaceSignal(0.0, 0.0, False, "nose", 0.3, False, False)
        if not result.multi_face_landmarks:
            return frame, blank

        lm = result.multi_face_landmarks[0].landmark
        h, w = frame.shape[:2]
        nose = lm[NOSE_TIP]
        ear = 0.5 * (_ear(lm, LEFT_EYE) + _ear(lm, RIGHT_EYE))
        closed = ear < 0.19
        gaze_ok = False
        gx, gy = 0.0, 0.0

        if self.prefer_gaze and len(lm) > LEFT_IRIS:
            try:
                lx, ly = _iris_offset(lm, LEFT_IRIS, LEFT_EYE)
                rx, ry = _iris_offset(lm, RIGHT_IRIS, RIGHT_EYE)
                gx = 0.5 * (lx + rx)
                gy = 0.5 * (ly + ry)
                gaze_ok = True
                _dot(frame, lm[LEFT_IRIS], w, h, (255, 200, 0))
                _dot(frame, lm[RIGHT_IRIS], w, h, (255, 200, 0))
            except (IndexError, ZeroDivisionError):
                gaze_ok = False

        if gaze_ok:
            signal = FaceSignal(gx, gy, True, "gaze", ear, closed, True)
        else:
            signal = FaceSignal(float(nose.x), float(nose.y), True, "nose", ear, closed, False)

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


def _iris_offset(lm, iris_i: int, eye: tuple[int, int, int, int, int, int]) -> tuple[float, float]:
    top, bot, inner, outer, _t2, _b2 = eye
    mid_x = 0.5 * (lm[inner].x + lm[outer].x)
    mid_y = 0.5 * (lm[top].y + lm[bot].y)
    width = abs(lm[outer].x - lm[inner].x) + 1e-6
    height = abs(lm[bot].y - lm[top].y) + 1e-6
    iris = lm[iris_i]
    return (iris.x - mid_x) / width, (iris.y - mid_y) / height
