"""Main loop: nose moves the cursor, blink clicks, hands stay on the keys.

F8 pause   F7 recenter   F6 practice
F3 slower  F4 faster     F10 quit
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
from pynput import keyboard

from dwell.blink import BlinkClicker
from dwell.overlay import pin_overlay
from dwell.pointer import HeadPointer
from dwell.practice import PracticeBoard
from dwell.track import FaceTracker

HUD = "Dwell"

_CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
_ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r}
_VK_LETTER = {
    80: "p",
    82: "r",
    84: "t",
    71: "g",
    81: "q",
    67: "c",
}


def _letter(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
    if not isinstance(key, keyboard.KeyCode):
        return None
    if key.char and key.char.isalpha():
        return key.char.lower()
    if key.vk in _VK_LETTER:
        return _VK_LETTER[key.vk]
    return None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    tracker = FaceTracker()
    pointer = HeadPointer(metrics_path=root / "metrics.csv")
    practice = PracticeBoard()
    blinker = BlinkClicker()
    running = True
    flash_until = 0.0
    mods: set[str] = set()

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        nonlocal running, flash_until
        if key in _CTRL:
            mods.add("ctrl")
            return
        if key in _ALT:
            mods.add("alt")
            return
        chord = "ctrl" in mods and "alt" in mods
        letter = _letter(key)

        try:
            if key == keyboard.Key.f10 or (chord and letter == "q"):
                running = False
                return
            if key == keyboard.Key.f8 or (chord and letter == "p"):
                pointer.toggle_pause()
                blinker.reset()
                return
            if key == keyboard.Key.f7 or (chord and letter == "r"):
                pointer.request_recenter()
                return
            if key == keyboard.Key.f6 or (chord and letter == "t"):
                practice.request_toggle()
                return
            if key == keyboard.Key.f5 or (chord and letter == "g"):
                tracker.toggle_gaze()
                pointer.request_recenter()
                return
            if key == keyboard.Key.f3 or (chord and getattr(key, "vk", None) in (189, 109, 173)):
                pointer.nudge_gain(-2.0)
                return
            if key == keyboard.Key.f4 or (chord and getattr(key, "vk", None) in (187, 107)):
                pointer.nudge_gain(2.0)
                return
            if key == keyboard.Key.f1 or (chord and letter == "c"):
                pointer.blink_click(time.perf_counter(), ignore_pause=True)
                flash_until = time.perf_counter() + 0.45
                return
            if key == keyboard.Key.f9:
                pointer.toggle_clicks()
                return
        except Exception:
            return

    def on_release(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key in _CTRL:
            mods.discard("ctrl")
        if key in _ALT:
            mods.discard("alt")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    hud_w, hud_h = 380, 300
    hud_x = max(0, pointer.screen_w - hud_w - 16)
    hud_y = 16
    cv2.namedWindow(HUD, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(HUD, hud_w, hud_h)
    cv2.moveWindow(HUD, hud_x, hud_y)
    last_pin = 0.0
    last_lost = 0.0

    try:
        while running:
            frame, face = tracker.read()
            if frame is None:
                time.sleep(0.02)
                continue

            if pointer.recenter_next and face.seen:
                pointer.recenter(face.x, face.y)
            pointer.set_input(face.source)

            try:
                practice.sync()
            except Exception as exc:
                print(f"Practice window failed: {exc}")

            now = time.perf_counter()
            if not face.seen:
                last_lost = now
            looking_down = face.seen and (face.y - pointer.rest_y) > 0.045
            face_recent = (now - last_lost) > 0.55
            allow_blink = (
                face.seen
                and not pointer.paused
                and face_recent
                and not looking_down
            )
            fired = blinker.update(face.ear, now, allow=allow_blink)
            freeze = blinker.closed or looking_down or not face.seen or not face_recent
            before_clicks = pointer.clicks
            state = pointer.update(face.x, face.y, face.seen, now, freeze=freeze)
            if fired:
                pointer.blink_click(now)
                flash_until = now + 0.45
            # F1 click also increments; keep the flash if clicks just happened.
            if pointer.clicks > before_clicks:
                flash_until = now + 0.45
                practice.on_click(state.x, state.y)

            _draw_hud(
                frame,
                state,
                face,
                blinker,
                now < flash_until,
                looking_down=looking_down,
                face_lost=not face.seen,
            )
            cv2.imshow(HUD, frame)
            if now - last_pin > 1.0:
                pin_overlay(HUD, hud_x, hud_y, hud_w, hud_h)
                last_pin = now
            try:
                practice.draw()
            except Exception as exc:
                print(f"Practice draw failed: {exc}")

            cv2.waitKey(1)
        return 0
    finally:
        listener.stop()
        tracker.close()
        cv2.destroyAllWindows()


def _draw_hud(
    frame,
    state,
    face,
    blinker: BlinkClicker,
    flash: bool,
    looking_down: bool = False,
    face_lost: bool = False,
) -> None:
    h, w = frame.shape[:2]
    panel_h = 222 if state.paused else 148
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    if face_lost or not face.seen:
        mode = "LOOK AT THE SCREEN — clicks off (face not in camera)"
        color = (0, 80, 255)
        steps = ["Glance at the keys is fine. Cursor and blink-click freeze until you're back."]
    elif looking_down:
        mode = "LOOKING DOWN — clicks off so the keyboard is safe"
        color = (0, 200, 255)
        steps = ["Look back at the monitor to move and blink-click again. F1 still clicks."]
    elif state.paused:
        mode = "PAUSED — nose tracking. Keyboard is yours."
        color = (0, 200, 255)
        steps = [
            "Look at screen center. F8 (or Ctrl+Alt+P) starts.",
            "Tilt your head to move. Double-blink or F1 to click.",
            "F7 recenter  F3/F4 speed  F10 quit",
        ]
    else:
        mode = "LIVE — nose moves cursor, double-blink clicks"
        color = (0, 220, 120)
        hit_txt = f"{state.hits}/{state.clicks}" if state.clicks else "0/0"
        steps = [
            f"Gain {state.gain:.1f}  clicks {hit_txt}  ear {blinker.ear:.2f}/{blinker.open_level:.2f}  F1 click",
            "Two quick blinks = click. Looking at the keys will not click.",
        ]
        if flash:
            mode = "CLICK"
            color = (0, 255, 255)

    cv2.putText(frame, mode, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2, cv2.LINE_AA)
    y = 58
    for line in steps:
        cv2.putText(
            frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (230, 230, 230), 1, cv2.LINE_AA
        )
        y += 28

    bar_w = int((w - 24) * blinker.progress)
    fill = (0, 80, 255) if blinker.closed else (0, 220, 120)
    cv2.rectangle(frame, (12, h - 22), (12 + max(bar_w, 0), h - 8), fill, -1)
    cv2.rectangle(frame, (12, h - 22), (w - 12, h - 8), (180, 180, 180), 1)
