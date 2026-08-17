# Dwell

Head-tracked dwell-click for Windows. You move a webcam with your face, hold still, and it clicks.

This is **not** a medical device, not mind-reading, and not a Neuralink implant. It is the first slice of a closed-loop computer-control layer: a noisy body signal in, a cursor and a click out, numbers on screen.

## Run

1. Plug in / open the laptop webcam.
2. Double-click `run.bat`.
3. The first run installs libraries (a few minutes). Allow the camera if Windows asks.
4. Sit in good light. You should see a green dot on your nose. The Dwell window is **only the camera** — watch the Windows mouse on your desktop.
5. Look at the **middle of the monitor**, sit still, press **Space**. Head tilts now move the cursor. It starts in **move-only** (no clicking).
6. If the cursor is still wild, mash **[** a few times (slower). **Space** pauses. **Esc** quits.
7. **P** or **F2** opens target practice and turns clicking on. Hold still on a circle to click it.

On many laptops F8 is brightness — use **Space** instead.

| Key | What it does |
|-----|----------------|
| Space / F8 | Start / pause. Also recenters so your current head pose is screen-center. |
| `[` `]` | Slower / faster |
| P / F2 | Target practice + clicking |
| F9 | Toggle clicking on the desktop |
| Esc | Quit |

Clicks and “did you mean it” scores append to `metrics.csv`. That file is your evidence. Keep it.

## What you are looking at in the code

| File | Job |
|------|-----|
| `dwell/track.py` | Webcam → nose position |
| `dwell/filters.py` | Smooth jitter without lag |
| `dwell/pointer.py` | Nose → cursor, hold still → click, dwell time adapts |
| `dwell/practice.py` | Circles to aim at |
| `dwell/app.py` | The loop that ties it together |

Python 3.11 is required (3.14 is too new for MediaPipe). This PC already has 3.11.
