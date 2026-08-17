"""Main loop: camera + HUD + hotkeys.

Space / F8  start or pause (also recenters)
[ ]         slower / faster
P / F2      target practice (turns clicking on)
F9          toggle desktop clicking
Esc         quit
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
            if key == keyboard.Key.f8 or key == keyboard.Key.space:
                pointer.toggle_pause()
                return
            if key == keyboard.Key.f2:
                practice.toggle()
                pointer.set_clicks(practice.on)
                return
            if key == keyboard.Key.f9:
                pointer.toggle_clicks()
                return
        except Exception:
            return
        if not isinstance(key, keyboard.KeyCode) or key.char is None:
            return
        ch = key.char.lower()
        if ch == "c":
            pointer.request_recenter()
        elif ch == "p":
            practice.toggle()
            pointer.set_clicks(practice.on)
        elif ch == "[":
            pointer.nudge_gain(-1.5)
        elif ch == "]":
            pointer.nudge_gain(1.5)

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    cv2.namedWindow(HUD, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(HUD, 720, 640)

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
    panel_h = 210 if state.paused else 128
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    if not seen:
        mode = "NO FACE — sit in the light until the green dot is on your nose"
        color = (0, 80, 255)
        steps = ["This window is the camera. Watch the Windows mouse on your desktop."]
    elif state.paused:
        mode = "PAUSED — tracking works. Mouse is NOT taken over yet."
        color = (0, 200, 255)
        steps = [
            "1. Look at the MIDDLE of your monitor, sit still",
            "2. Press SPACE (or F8) — the desktop cursor starts following your head",
            "3. Tilt slowly. If it flies, press [   (SPACE again pauses)",
            "4. Press P or F2 for target practice (that turns on clicking)",
            "Esc always quits.",
        ]
    elif not state.click_enabled:
        mode = "LIVE — move only. No clicking yet."
        color = (0, 220, 120)
        steps = [
            "Tilt your HEAD, not the camera window. Watch the desktop cursor.",
            f"Gain {state.gain:.1f}   [ slower   ] faster    SPACE pause    P practice",
        ]
    else:
        mode = "LIVE — hold still to click"
        color = (0, 220, 120)
        hit_txt = f"{state.hits}/{state.clicks}" if state.clicks else "0/0"
        steps = [
            f"Dwell {state.dwell_ms} ms   gain {state.gain:.1f}   meant-it {hit_txt}",
            "SPACE pause   F9 clicks off   [ ] gain   Esc quit",
        ]

    cv2.putText(frame, mode, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2, cv2.LINE_AA)
    y = 58
    for line in steps:
        cv2.putText(
            frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (230, 230, 230), 1, cv2.LINE_AA
        )
        y += 28

    if seen and not state.paused and state.click_enabled and state.dwell_progress > 0:
        bar_w = int((w - 24) * state.dwell_progress)
        cv2.rectangle(frame, (12, h - 22), (12 + bar_w, h - 8), (0, 220, 120), -1)
        cv2.rectangle(frame, (12, h - 22), (w - 12, h - 8), (180, 180, 180), 1)
