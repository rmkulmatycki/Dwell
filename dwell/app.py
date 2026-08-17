"""Main loop: camera + HUD + hotkeys.

Space / F8  start or pause (also recenters)
[ ]         slower / faster
G           gaze (eyes) or nose
P / F2      target practice
Esc         quit

Look to aim. Double-blink or hold eyes shut ~0.4s to click.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
from pynput import keyboard

from dwell.blink import BlinkClicker
from dwell.pointer import HeadPointer
from dwell.practice import PracticeBoard
from dwell.track import FaceTracker

HUD = "Dwell"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    tracker = FaceTracker()
    pointer = HeadPointer(metrics_path=root / "metrics.csv")
    practice = PracticeBoard()
    blinker = BlinkClicker()
    running = True
    flash_until = 0.0

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        nonlocal running
        try:
            if key == keyboard.Key.esc:
                running = False
                return
            if key == keyboard.Key.f8 or key == keyboard.Key.space:
                pointer.toggle_pause()
                blinker.reset()
                return
            if key == keyboard.Key.f2:
                practice.request_toggle()
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
        elif ch == "g":
            tracker.prefer_gaze = not tracker.prefer_gaze
            pointer.request_recenter()
        elif ch == "p":
            practice.request_toggle()
        elif ch == "[":
            pointer.nudge_gain(-2.0)
        elif ch == "]":
            pointer.nudge_gain(2.0)

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

            try:
                practice.sync()
            except Exception as exc:
                print(f"Practice window failed: {exc}")

            now = time.perf_counter()
            fired = blinker.update(face.ear, now, allow=face.seen and not pointer.paused)
            freeze = blinker.closed or face.eyes_closed
            before_clicks = pointer.clicks
            state = pointer.update(face.x, face.y, face.seen, now, freeze=freeze)
            if fired:
                pointer.blink_click(now)
                flash_until = now + 0.45
            if pointer.clicks > before_clicks:
                practice.on_click(state.x, state.y)

            _draw_hud(frame, state, face, blinker, now < flash_until)
            cv2.imshow(HUD, frame)
            try:
                practice.draw()
            except Exception as exc:
                print(f"Practice draw failed: {exc}")

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                running = False
        return 0
    finally:
        listener.stop()
        tracker.close()
        cv2.destroyAllWindows()


def _draw_hud(frame, state, face, blinker: BlinkClicker, flash: bool) -> None:
    h, w = frame.shape[:2]
    panel_h = 222 if state.paused else 140
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    src = "GAZE" if face.source == "gaze" else "NOSE"
    if not face.seen:
        mode = "NO FACE — sit in the light until you see dots on your eyes"
        color = (0, 80, 255)
        steps = ["This window is the camera. Watch the Windows mouse on your desktop."]
    elif state.paused:
        mode = f"PAUSED — {src} tracking. Mouse is NOT taken over yet."
        color = (0, 200, 255)
        steps = [
            "Yellow dots on the eyes = gaze. Look at the MIDDLE of the monitor.",
            "2. Press SPACE — looking around moves the desktop cursor",
            "3. Double-blink OR hold eyes shut to click   (P = practice)",
            "G switches to nose if gaze is jumpy.  [ ] speed.  Esc quits.",
        ]
    else:
        mode = f"LIVE — {src}    look to move, blink to click"
        color = (0, 220, 120)
        hit_txt = f"{state.hits}/{state.clicks}" if state.clicks else "0/0"
        steps = [
            f"Gain {state.gain:.1f}   meant-it {hit_txt}    [ ] speed   G {('nose' if face.source == 'gaze' else 'gaze')}   SPACE pause",
            "Click: double-blink, or close eyes until the bar fills",
        ]
        if flash:
            mode = "CLICK"
            color = (0, 255, 255)

    cv2.putText(frame, mode, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2, cv2.LINE_AA)
    y = 58
    for line in steps:
        cv2.putText(
            frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 230, 230), 1, cv2.LINE_AA
        )
        y += 28

    # Blink charge bar (fills on a long blink).
    bar_w = int((w - 24) * blinker.progress)
    fill = (0, 80, 255) if blinker.closed else (0, 220, 120)
    cv2.rectangle(frame, (12, h - 22), (12 + max(bar_w, 0), h - 8), fill, -1)
    cv2.rectangle(frame, (12, h - 22), (w - 12, h - 8), (180, 180, 180), 1)
