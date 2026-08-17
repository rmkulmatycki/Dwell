# Dwell

Head-tracked dwell-click for Windows. You move a webcam with your face, hold still, and it clicks.

This is **not** a medical device, not mind-reading, and not a Neuralink implant. It is the first slice of a closed-loop computer-control layer: a noisy body signal in, a cursor and a click out, numbers on screen.

## Run

1. Plug in / open the laptop webcam.
2. Double-click `run.bat`.
3. The first run installs libraries (a few minutes). Allow the camera if Windows asks.
4. Sit in good light. You should see a green dot on your nose.
5. Look at the **center of the screen** and press **C**.
6. Press **F8**. The mouse is now driven by your head. **Esc** always quits.

If the cursor flies around, press F8 (pause), press C again, then F8.

| Key | What it does |
|-----|----------------|
| F8 | Start / pause mouse control (starts paused on purpose) |
| C | Recenter — wherever your nose is becomes screen center |
| `[` `]` | Need more / less head movement to cross the screen |
| F2 | Target practice (this is how we get a hit rate) |
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
