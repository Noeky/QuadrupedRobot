"""Simple servo model: command deadband -> gear backlash -> first-order lag.

All angles are radians.  `deadband` and `backlash` are full widths, so a
deadband of 1 degree means +/-0.5 degree around the held command.

This is deliberately simple and identifiable from a real step test:
  * deadband: the smallest command change that produces motion;
  * backlash: the lost motion when the command reverses;
  * tau: the time constant of the first-order response;
  * max_rate: optional slew-rate limit (rad/s).
"""

from __future__ import annotations

import numpy as np


class ServoBank:
    def __init__(
        self,
        n: int = 8,
        tau: float = 0.08,
        deadband: float = 0.0,
        backlash: float = 0.0,
        max_rate: float | None = None,
    ):
        self.n = n
        self.tau = max(0.0, float(tau))
        self.deadband = max(0.0, float(deadband))
        self.backlash = max(0.0, float(backlash))
        self.max_rate = None if max_rate is None else max(0.0, float(max_rate))
        self.cmd_hold = np.zeros(n)
        self.play = np.zeros(n)
        self.y = np.zeros(n)
        self.last_y = np.zeros(n)
        self.initialized = False

    def reset(self, initial) -> None:
        initial = np.asarray(initial, dtype=float).copy()
        if initial.shape != (self.n,):
            raise ValueError(f"expected {self.n} initial values, got {initial.shape}")
        self.cmd_hold = initial.copy()
        self.play = initial.copy()
        self.y = initial.copy()
        self.last_y = initial.copy()
        self.initialized = True

    def step(self, cmd, dt: float) -> np.ndarray:
        cmd = np.asarray(cmd, dtype=float)
        if cmd.shape != (self.n,):
            raise ValueError(f"expected {self.n} commands, got {cmd.shape}")
        if not self.initialized:
            self.reset(cmd)

        # 1. Command deadband with hysteresis: small changes are ignored.
        # `deadband` is a full width, so 1 deg means +/-0.5 deg around hold.
        half_dead = self.deadband / 2.0
        moved = (cmd > self.cmd_hold + half_dead) | (
            cmd < self.cmd_hold - half_dead
        )
        self.cmd_hold = np.where(moved, cmd, self.cmd_hold)

        # 2. Gear backlash: the output side only follows after the input
        # crosses half the play in either direction.
        half = self.backlash / 2.0
        high = self.cmd_hold > self.play + half
        low = self.cmd_hold < self.play - half
        self.play = np.where(
            high,
            self.cmd_hold - half,
            np.where(low, self.cmd_hold + half, self.play),
        )

        # 3. First-order lag toward the play output.
        if self.tau <= 0.0:
            self.y = self.play.copy()
        else:
            alpha = min(1.0, dt / self.tau)
            self.y += alpha * (self.play - self.y)

        # 4. Optional slew-rate limit.
        if self.max_rate is not None:
            max_step = self.max_rate * dt
            delta = np.clip(self.y - self.last_y, -max_step, max_step)
            self.y = self.last_y + delta

        self.last_y = self.y.copy()
        return self.y.copy()
