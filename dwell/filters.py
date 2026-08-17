"""One Euro filter — keeps the cursor smooth without making it feel drunk.

Paper: Casiez, Roussel, Vogel. "1€ Filter". CHI 2012.
Used in real pointing devices because a plain average is either laggy or jittery.
"""

from __future__ import annotations

import math


class OneEuro:
    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.007, dcutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self._x = None
        self._dx = 0.0
        self._t = None

    def reset(self) -> None:
        self._x = None
        self._dx = 0.0
        self._t = None

    def __call__(self, x: float, t: float) -> float:
        if self._t is None or self._x is None:
            self._t = t
            self._x = x
            return x
        dt = t - self._t
        if dt <= 1e-6:
            return self._x
        dx = (x - self._x) / dt
        edx = _smooth(dx, self._dx, _alpha(dt, self.dcutoff))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        xhat = _smooth(x, self._x, _alpha(dt, cutoff))
        self._t = t
        self._x = xhat
        self._dx = edx
        return xhat


def _alpha(dt: float, cutoff: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


def _smooth(x: float, prev: float, a: float) -> float:
    return a * x + (1.0 - a) * prev
