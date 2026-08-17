"""Webcam → nose tip in the camera frame.

This is not mind-reading. The camera sees your face. We pick one point (the
nose) and treat it like a joystick. Same idea as Camera Mouse, a real
assistive tool used in clinics.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

# MediaPipe Face Mesh index for the tip of the nose.
NOSE_TIP = 4


@dataclass
class FacePoint:
    # 0–1 in the camera image. x is already mirrored (left on screen = left in real life).
    x: float
    y: float
    seen: bool


class NoseTracker:
    def __init__(self, camera_index: int = 0):
        # CAP_DSHOW is the Windows backend that actually opens laptop webcams.
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
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def read(self) -> tuple[np.ndarray | None, FacePoint]:
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None, FacePoint(0.5, 0.5, False)

        # Webcams are mirrored vs a mirror. Flip so moving left moves left.
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._mesh.process(rgb)

        point = FacePoint(0.5, 0.5, False)
        if result.multi_face_landmarks:
            nose = result.multi_face_landmarks[0].landmark[NOSE_TIP]
            point = FacePoint(float(nose.x), float(nose.y), True)
            h, w = frame.shape[:2]
            cv2.circle(frame, (int(nose.x * w), int(nose.y * h)), 6, (0, 220, 120), -1)

        return frame, point

    def close(self) -> None:
        self._mesh.close()
        self.cap.release()
