# Dwell

Gaze-tracked pointer + blink-click for Windows. Look to move. Double-blink or hold your eyes shut to click.

This is **not** a medical device, not mind-reading, and not a Neuralink implant.

Controls are **F-keys** (and Ctrl+Alt backups) so you can still type. Letters, Space, and Esc do nothing.

## Run

1. Double-click `run.bat`. Allow the camera if Windows asks.
2. Yellow dots on the eyes = gaze tracking. This window is only the camera — watch the Windows mouse.
3. Look at the **middle of the monitor**, press **F8** (or **Ctrl+Alt+P** if F8 is brightness).
4. Look around to move. A single blink does nothing.
5. **Two blinks** in about a second clicks. Or hold your eyes shut until the bottom bar fills.
6. **F6** is target practice. **F10** quits.

If F-keys control volume/brightness, hold **Fn**, or use the Ctrl+Alt shortcuts.

| Key | Backup | What it does |
|-----|--------|----------------|
| F8 | Ctrl+Alt+P | Start / pause (recenters) |
| F7 | Ctrl+Alt+R | Recenter |
| F6 | Ctrl+Alt+T | Target practice |
| F5 | Ctrl+Alt+G | Gaze or nose |
| F3 / F4 | Ctrl+Alt+- / Ctrl+Alt+= | Slower / faster |
| F9 | | Old dwell-click (hold still) |
| F10 | Ctrl+Alt+Q | Quit |

Clicks append to `metrics.csv`.

Python 3.11 is required (3.14 is too new for MediaPipe).
