"""Main loop: camera + HUD + hotkeys.

Keys
----
F8   start / pause the mouse
C    recenter (look at the middle of the screen, then press C)
[ ]  less / more head movement needed
F2   target practice
Esc  quit
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
from pynput import keyboard

from dwell.pointer import HeadPointer
from dwell.practice import PracticeBoard
from dwell.track import NoseTracker

HUD = "Dwell"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    tracker = NoseTracker()
    pointer = HeadPointer(metrics_path=root / "metrics.csv")
    practice = PracticeBoard()
    running = True

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        nonlocal running
        try:
            if key == keyboard.Key.esc:
                running = False
                return
            if key == keyboard.Key.f8:
                pointer.toggle_pause()
                return
            if key == keyboard.Key.f2:
                practice.toggle()
                return
        except Exception:
            return
        if not isinstance(key, keyboard.KeyCode) or key.char is None:
            return
        ch = key.char.lower()
        if ch == "c":
            pointer.request_recenter()
        elif ch == "[":
            pointer.nudge_gain(-1.5)
        elif ch == "]":
            pointer.nudge_gain(1.5)

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    cv2.namedWindow(HUD, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(HUD, 640, 520)

    try:
        while running:
            frame, face = tracker.read()
            if frame is None:
                time.sleep(0.02)
                continue

            if pointer.recenter_next and face.seen:
                pointer.recenter(face.x, face.y)

            now = time.perf_counter()
            before_clicks = pointer.clicks
            state = pointer.update(face.x, face.y, face.seen, now)
            if pointer.clicks > before_clicks:
                practice.on_click(state.x, state.y)

            _draw_hud(frame, state, face.seen)
            cv2.imshow(HUD, frame)
            practice.draw()

            # waitKey is required or OpenCV windows freeze. 1 ms keeps the loop fast.
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                running = False
        return 0
    finally:
        listener.stop()
        tracker.close()
        cv2.destroyAllWindows()


def _draw_hud(frame, state, seen: bool) -> None:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 118), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)

    if state.paused:
        mode = "PAUSED  (F8 to start)"
        color = (0, 200, 255)
    elif not seen:
        mode = "NO FACE  — mouse frozen"
        color = (0, 80, 255)
    else:
        mode = "LIVE"
        color = (0, 220, 120)

    hit_txt = f"{state.hits}/{state.clicks}" if state.clicks else "0/0"
    last = f"{state.last_click_ms} ms" if state.last_click_ms is not None else "—"
    lines = [
        f"DWELL   {mode}",
        f"dwell {state.dwell_ms} ms    gain {state.gain:.1f}    last click {last}",
        f"meant-it {hit_txt}    F8 start/pause   C recenter   [ ] gain   F2 practice   Esc quit",
    ]
    y = 28
    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55 if i else 0.72,
            color if i == 0 else (230, 230, 230),
            2,
            cv2.LINE_AA,
        )
        y += 32

    if seen and not state.paused and state.dwell_progress > 0:
        bar_w = int((w - 24) * state.dwell_progress)
        cv2.rectangle(frame, (12, h - 22), (12 + bar_w, h - 8), (0, 220, 120), -1)
        cv2.rectangle(frame, (12, h - 22), (w - 12, h - 8), (180, 180, 180), 1)
