"""Shared 50 Hz gait runner for the viewer, headless tests and servo sweeps."""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np

from gait import BASE_CYCLE_S, joint_targets
from servo import ServoBank

CONTROL_DT = 0.02  # 50 Hz, same as WALK_FRAME_MS=20
TRANSITION_S = 1.5
FALL_Z = 0.04
FALL_TILT = 0.7  # rad


def apply_model_scales(
    model,
    mass_scale: float = 1.0,
    torque_scale: float = 1.0,
    friction: float = 0.0,
    com_x: float = 0.0,
    com_y: float = 0.0,
) -> None:
    """Apply coarse mass/torque/friction/CoM changes before a runner."""
    if mass_scale != 1.0:
        model.body_mass[:] *= mass_scale
        model.body_inertia[:] *= mass_scale
    if torque_scale != 1.0:
        model.actuator_forcerange[:] *= torque_scale
    if friction > 0.0:
        model.geom_friction[:, 0] = friction
    if com_x or com_y:
        torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
        if torso < 0:
            raise ValueError("body 'torso' not found")
        model.body_ipos[torso, 0] += com_x
        model.body_ipos[torso, 1] += com_y


def attitude(qpos: np.ndarray) -> tuple[float, float]:
    mat = np.zeros(9, dtype=np.float64)
    mujoco.mju_quat2Mat(mat, qpos[3:7])
    rot = mat.reshape(3, 3)
    up = rot[:, 2]
    roll = np.arctan2(-up[1], up[2])
    pitch = np.arctan2(up[0], np.hypot(up[1], up[2]))
    return float(roll), float(pitch)


def yaw(qpos: np.ndarray) -> float:
    mat = np.zeros(9, dtype=np.float64)
    mujoco.mju_quat2Mat(mat, qpos[3:7])
    rot = mat.reshape(3, 3)
    return float(np.arctan2(rot[1, 0], rot[0, 0]))


@dataclass
class TrialMetrics:
    dx_gait_mm: float
    dx_total_mm: float
    min_z_mm: float
    max_abs_y_mm: float
    final_z_mm: float
    final_roll_deg: float
    final_pitch_deg: float
    final_yaw_deg: float
    fell: bool
    time_s: float


class GaitRunner:
    def __init__(
        self,
        model,
        data,
        speed: float = 1.0,
        servo: ServoBank | None = None,
        direction: float = 1.0,
        turn: float = 0.0,
        turn_gain: float = 0.5,
    ):
        self.model = model
        self.data = data
        self.speed = float(speed)
        self.servo = servo
        self.direction = float(direction)
        self.turn = float(turn)
        self.turn_gain = float(turn_gain)
        self.n_substeps = max(1, round(CONTROL_DT / model.opt.timestep))

        mujoco.mj_resetDataKeyframe(model, data, 0)
        mujoco.mj_forward(model, data)
        self.home = data.ctrl.copy()
        self.first = np.asarray(
            joint_targets(0.0, self.direction, self.turn, self.turn_gain)
        )
        if self.servo is not None:
            self.servo.reset(self.home)

        self.t = 0.0
        self.phase = 0.0
        self.gait_start_x: float | None = None
        self.total_start_x = float(data.qpos[0])
        self.min_z = float(data.qpos[2])
        self.max_abs_y = abs(float(data.qpos[1]))
        self.fell = False
        self.last_base = self.home.copy()
        self.last_ctrl = self.home.copy()

    def _base_ctrl(self) -> np.ndarray:
        if self.t < TRANSITION_S:
            u = min(1.0, self.t / TRANSITION_S)
            u = u * u * (3.0 - 2.0 * u)
            return self.home + u * (self.first - self.home)
        if self.gait_start_x is None:
            self.gait_start_x = float(self.data.qpos[0])
        return np.asarray(
            joint_targets(self.phase, self.direction, self.turn, self.turn_gain)
        )

    def step(self) -> None:
        base = self._base_ctrl()
        ctrl = self.servo.step(base, CONTROL_DT) if self.servo is not None else base
        self.last_base = np.asarray(base).copy()
        self.last_ctrl = np.asarray(ctrl).copy()
        self.data.ctrl[:] = np.clip(ctrl, -1.5, 2.6)
        for _ in range(self.n_substeps):
            mujoco.mj_step(self.model, self.data)

        self.t += CONTROL_DT
        if self.t >= TRANSITION_S:
            self.phase = (self.phase + CONTROL_DT * self.speed / BASE_CYCLE_S) % 1.0

        z = float(self.data.qpos[2])
        roll, pitch = attitude(self.data.qpos)
        self.min_z = min(self.min_z, z)
        self.max_abs_y = max(self.max_abs_y, abs(float(self.data.qpos[1])))
        if z < FALL_Z or abs(roll) > FALL_TILT or abs(pitch) > FALL_TILT:
            self.fell = True

    def run(self, seconds: float) -> TrialMetrics:
        while self.t < seconds and not self.fell:
            self.step()
        return self.metrics()

    def metrics(self) -> TrialMetrics:
        x = float(self.data.qpos[0])
        z = float(self.data.qpos[2])
        roll, pitch = attitude(self.data.qpos)
        dx_gait = 0.0 if self.gait_start_x is None else (x - self.gait_start_x) * 1000.0
        return TrialMetrics(
            dx_gait_mm=dx_gait,
            dx_total_mm=(x - self.total_start_x) * 1000.0,
            min_z_mm=self.min_z * 1000.0,
            max_abs_y_mm=self.max_abs_y * 1000.0,
            final_z_mm=z * 1000.0,
            final_roll_deg=np.degrees(roll),
            final_pitch_deg=np.degrees(pitch),
            final_yaw_deg=np.degrees(yaw(self.data.qpos)),
            fell=self.fell,
            time_s=self.t,
        )
