"""Gymnasium environment for learning a residual policy on top of the gait.

The observation deliberately uses only signals the real robot can measure:
body attitude, angular rate, acceleration, the downward height sensor, the gait
phase and the previous action.  It does NOT use body x/y, joint positions or
joint velocities, because the current robot has no encoders.

Action: 8 residuals around the scripted gait (or around the stand pose).
"""

from __future__ import annotations

import math
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from gait import BASE_CYCLE_S, joint_targets

XML = Path(__file__).with_name("quadruped.xml")
CONTROL_DT = 0.02
N_SUBSTEPS = 10
TRANSITION_S = 1.5
RESIDUAL_SCALE = 0.25  # rad, about 14 degrees
CTRL_LOW = -1.5
CTRL_HIGH = 2.6


def load_model():
    if not XML.exists():
        from build_model import build_xml

        XML.write_text(build_xml(), encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(XML))
    return model


def attitude(qpos: np.ndarray) -> tuple[float, float]:
    """Return roll and pitch from the free-joint quaternion."""
    quat = qpos[3:7]
    mat = np.zeros(9, dtype=np.float64)
    mujoco.mju_quat2Mat(mat, quat)
    rot = mat.reshape(3, 3)
    up = rot[:, 2]
    roll = math.atan2(-up[1], up[2])
    pitch = math.atan2(up[0], math.hypot(up[1], up[2]))
    return roll, pitch


class QuadrupedEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, mode: str = "walk", speed: float = 1.0, randomize: bool = False):
        super().__init__()
        if mode not in ("stand", "walk"):
            raise ValueError("mode must be 'stand' or 'walk'")
        self.mode = mode
        self.speed = speed if mode == "walk" else 0.0
        self.randomize = randomize

        self.model = load_model()
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)
        self.home = self.data.ctrl.copy()
        self.first = np.asarray(joint_targets(0.0))
        self.h_ref = float(self.data.sensor("us_distance").data[0])
        self.base_body_mass = self.model.body_mass.copy()
        self.base_floor_friction = float(self.model.geom_friction[0, 0])

        self.action_space = spaces.Box(-1.0, 1.0, shape=(8,), dtype=np.float32)
        self.observation_space = spaces.Box(
            -np.inf, np.inf, shape=(20,), dtype=np.float32
        )

        self.max_time = 10.0
        self.t = 0.0
        self.phase = 0.0
        self.last_action = np.zeros(8, dtype=np.float64)
        self.ctrl_filtered = self.home.copy()
        self.last_x = 0.0
        self.v_cmd = 2.0 * 0.028 * self.speed / BASE_CYCLE_S  # 2 x stride per cycle

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        if self.randomize:
            self.data.qpos[7:] += self.np_random.uniform(-0.01, 0.01, size=8)
            self.data.qpos[2] += self.np_random.uniform(-0.002, 0.002)
            self.model.body_mass[:] = self.base_body_mass
            self.model.body_mass[1] *= self.np_random.uniform(0.85, 1.15)
            self.model.geom_friction[0, 0] = self.base_floor_friction * self.np_random.uniform(0.8, 1.2)
        mujoco.mj_forward(self.model, self.data)
        self.t = 0.0
        self.phase = 0.0
        self.last_action[:] = 0.0
        self.ctrl_filtered = self.home.copy()
        self.last_x = float(self.data.qpos[0])
        return self._obs(), {}

    def _base_ctrl(self) -> np.ndarray:
        if self.mode == "stand":
            return self.home
        if self.t < TRANSITION_S:
            u = min(1.0, self.t / TRANSITION_S)
            u = u * u * (3.0 - 2.0 * u)
            return self.home + u * (self.first - self.home)
        return np.asarray(joint_targets(self.phase))

    def _obs(self) -> np.ndarray:
        roll, pitch = attitude(self.data.qpos)
        gyro = self.data.sensor("torso_gyro").data
        accel = self.data.sensor("torso_accel").data
        height = float(self.data.sensor("us_distance").data[0])
        if self.mode == "walk":
            phase_sin, phase_cos = math.sin(2 * math.pi * self.phase), math.cos(2 * math.pi * self.phase)
        else:
            phase_sin, phase_cos = 0.0, 1.0
        obs = np.concatenate(
            [
                [roll, pitch],
                np.asarray(gyro).ravel(),
                np.asarray(accel).ravel(),
                [phase_sin, phase_cos],
                self.last_action,
                [height, self.v_cmd],
            ]
        )
        return obs.astype(np.float32)

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        base = self._base_ctrl()
        ctrl = np.clip(base + RESIDUAL_SCALE * action * np.array(
            [1, 1, 1, 1, 1, 1, 1, 1]
        ), CTRL_LOW, CTRL_HIGH)
        self.ctrl_filtered = 0.7 * self.ctrl_filtered + 0.3 * ctrl
        self.data.ctrl[:] = self.ctrl_filtered
        for _ in range(N_SUBSTEPS):
            mujoco.mj_step(self.model, self.data)

        if self.mode == "walk" and self.t >= TRANSITION_S:
            self.phase = (self.phase + CONTROL_DT * self.speed / BASE_CYCLE_S) % 1.0
        self.t += CONTROL_DT

        x, y, z = (float(v) for v in self.data.qpos[:3])
        vx = (x - self.last_x) / CONTROL_DT
        self.last_x = x
        roll, pitch = attitude(self.data.qpos)
        height = float(self.data.sensor("us_distance").data[0])
        upright = math.cos(roll) * math.cos(pitch)

        r_forward = 2.0 * math.exp(-((vx - self.v_cmd) / 0.02) ** 2)
        r_upright = 1.0 * upright
        r_height = -0.5 * ((height - self.h_ref) / 0.01) ** 2
        r_action = -0.02 * float(np.sum(action**2))
        r_smooth = -0.01 * float(np.sum((action - self.last_action) ** 2))
        reward = 1.0 + r_forward + r_upright + r_height + r_action + r_smooth

        terminated = bool(z < 0.04 or abs(roll) > 0.7 or abs(pitch) > 0.7)
        if terminated:
            reward -= 10.0
        truncated = bool(self.t >= self.max_time)
        self.last_action = action
        info = {"x": x, "y": y, "z": z, "phase": self.phase, "vx": vx}
        return self._obs(), float(reward), terminated, truncated, info

    def close(self):
        pass


if __name__ == "__main__":
    env = QuadrupedEnv(mode="walk", speed=1.0)
    obs, info = env.reset()
    print("obs shape", obs.shape, "action shape", env.action_space.shape)
    total = 0.0
    for i in range(50):
        obs, reward, terminated, truncated, info = env.step(np.zeros(8))
        total += reward
        if terminated or truncated:
            print(f"episode ended at step {i}, reward {total:.2f}, info {info}")
            break
    print(f"random-zero policy: steps={i+1}, total reward={total:.2f}")
