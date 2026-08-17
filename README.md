# Dwell

Gaze-tracked pointer + blink-click for Windows. Look to move. Double-blink or hold your eyes shut to click.

This is **not** a medical device, not mind-reading, and not a Neuralink implant. It is a closed-loop computer-control layer: a noisy body signal in, a cursor and a click out, numbers on screen.

## Run

1. Plug in / open the laptop webcam.
2. Double-click `run.bat`.
3. Allow the camera if Windows asks.
4. Sit in good light. You should see **yellow dots on your eyes** and a green dot on your nose. The Dwell window is **only the camera** — watch the Windows mouse on your desktop.
5. Look at the **middle of the monitor**, sit still, press **Space**.
6. Look around. The desktop cursor should follow your gaze. A normal blink does nothing.
7. **Double-blink** or **hold your eyes shut** (~half a second, until the bar at the bottom fills) to click.
8. **P** opens target practice. **G** switches to nose-pointer if gaze is jumpy. **Esc** quits.

On many laptops F8 is brightness — use **Space** instead.

| Key | What it does |
|-----|----------------|
| Space / F8 | Start / pause. Recenters on wherever you are looking. |
| `[` `]` | Slower / faster |
| G | Gaze (eyes) or nose |
| P / F2 | Target practice |
| F9 | Old dwell-click (hold still) if you want it |
| Esc | Quit |

Clicks append to `metrics.csv`. Keep that file.

## What you are looking at in the code

| File | Job |
|------|-----|
| `dwell/track.py` | Webcam → iris gaze + blink (EAR) |
| `dwell/blink.py` | Long blink / double blink → click |
| `dwell/filters.py` | Smooth jitter without lag |
| `dwell/pointer.py` | Signal → cursor |
| `dwell/practice.py` | Circles to aim at |
| `dwell/app.py` | The loop that ties it together |

Python 3.11 is required (3.14 is too new for MediaPipe).
