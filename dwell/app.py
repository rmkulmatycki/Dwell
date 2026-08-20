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


_TYPING_KEYS = {
    keyboard.Key.space,
    keyboard.Key.enter,
    keyboard.Key.backspace,
    keyboard.Key.delete,
    keyboard.Key.tab,
}


def _is_typing_key(key: keyboard.Key | keyboard.KeyCode | None) -> bool:
    """True for keys you press while writing — not F-keys / our chords."""
    if key is None:
        return False
    if key in _TYPING_KEYS:
        return True
    if isinstance(key, keyboard.Key):
        return False
    if key.char and not key.char.isalpha() and not key.char.isdigit() and key.char.isprintable():
        return True
    if key.char and (key.char.isalnum() or key.char == "_"):
        return True
    # Windows often delivers letters as vk-only when a modifier was involved earlier.
    if key.vk is not None and 48 <= key.vk <= 90:
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    tracker = FaceTracker()
    pointer = HeadPointer(metrics_path=root / "metrics.csv")
    practice = PracticeBoard()
    blinker = BlinkClicker()
    running = True
    flash_until = 0.0
    last_typed = 0.0
    last_face_lost = 0.0
    face_was_seen = False
    mods: set[str] = set()

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        nonlocal running, flash_until, last_typed
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
            # Any real typing key: suppress blink-clicks briefly so the
            # keyboard does not click itself while you look at the keys.
            if _is_typing_key(key):
                last_typed = time.perf_counter()
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
    # After the face returns from a keyboard glance, wait before trusting blinks.
    FACE_SETTLE_S = 0.55
    # After any typing key, ignore blinks so natural lid motion does not click.
    TYPE_SUPPRESS_S = 0.80

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
                last_face_lost = now
                if face_was_seen:
                    blinker.hard_reset()
                face_was_seen = False
            else:
                face_was_seen = True

            face_settled = (now - last_face_lost) > FACE_SETTLE_S
            typing = (now - last_typed) < TYPE_SUPPRESS_S
            allow_blink = (
                face.seen and not pointer.paused and face_settled and not typing
            )
            fired = blinker.update(face.ear, now, allow=allow_blink)
            # Freeze only when the face is gone (keyboard glance), not when aiming at the bottom of the screen.
            freeze = blinker.closed or not face.seen
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
                face_lost=not face.seen,
                typing=typing and face.seen and not pointer.paused,
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
    face_lost: bool = False,
    typing: bool = False,
) -> None:
    h, w = frame.shape[:2]
    panel_h = 222 if state.paused else 148
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    if face_lost or not face.seen:
        mode = "LOOK AT THE SCREEN — clicks off (face not in camera)"
        color = (0, 80, 255)
        steps = ["Glance at the keys is fine. Cursor freezes until your face is back."]
    elif state.paused:
        mode = "PAUSED — nose tracking. Keyboard is yours."
        color = (0, 200, 255)
        steps = [
            "Look at screen center. F8 (or Ctrl+Alt+P) starts.",
            "Tilt your head to move. Double-blink or F1 to click.",
            "F7 recenter  F3/F4 speed  F10 quit",
        ]
    elif typing:
        mode = "TYPING — blink clicks paused"
        color = (0, 180, 255)
        steps = [
            "Keep writing. Blink-click returns ~1s after you stop typing.",
            "F1 still clicks if you need it.",
        ]
    else:
        mode = "LIVE — nose moves cursor, double-blink clicks"
        color = (0, 220, 120)
        hit_txt = f"{state.hits}/{state.clicks}" if state.clicks else "0/0"
        armed = f"blink {blinker.pending_blinks}/2"
        steps = [
            f"Gain {state.gain:.1f}  clicks {hit_txt}  {armed}  ear {blinker.ear:.2f}/{blinker.open_level:.2f}",
            "Two quick blinks = click. Typing or lost face pauses blink-click.",
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
