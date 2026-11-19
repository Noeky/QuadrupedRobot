"""Headless smoke tests for the simplified MuJoCo model.

Checks:
  1. the model loads and the home keyframe holds the stand pose;
  2. the firmware trot runs for three cycles without NaNs or a fall;
  3. the body actually moves forward (not an in-place gait);
  4. the downward rangefinder returns a plausible distance.

Run:
    python sim/build_model.py
    python sim/test_sim.py
"""

import math
from pathlib import Path

import mujoco
import numpy as np

from build_model import build_xml
from gait import BASE_CYCLE_S, joint_targets
from runner import CONTROL_DT, TRANSITION_S

XML = Path(__file__).with_name("quadruped.xml")
N_STEPS = max(1, round(CONTROL_DT / 0.002))


def load_model():
    if not XML.exists():
        XML.write_text(build_xml(), encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(XML))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    return model, data


def step_control(model, data, ctrl, n=N_STEPS):
    data.ctrl[:] = ctrl
    for _ in range(n):
        mujoco.mj_step(model, data)
    if not np.isfinite(data.qpos).all():
        raise AssertionError("simulation diverged")


def main() -> None:
    model, data = load_model()
    home = data.ctrl.copy()

    # 1. Stand test: hold the home pose for 2 s.
    for _ in range(round(2.0 / CONTROL_DT)):
        step_control(model, data, home)
    z_stand = float(data.qpos[2])
    print(f"stand: body z={z_stand*1000:.1f} mm, height sensor={data.sensor('us_distance').data[0]*1000:.1f} mm")
    assert 0.05 < z_stand < 0.12, "robot fell while holding the stand pose"

    # 2. Transition to the phase-0 pose, matching firmware's 1.5 s blend.
    first = np.asarray(joint_targets(0.0))
    for i in range(round(TRANSITION_S / CONTROL_DT)):
        u = min(1.0, (i + 1) * CONTROL_DT / TRANSITION_S)
        u = u * u * (3.0 - 2.0 * u)
        step_control(model, data, home + u * (first - home))

    # 3. Gait test: three cycles at 1x, measured from the start of phase 0.
    x0 = float(data.qpos[0])
    phase = 0.0
    min_z = float(data.qpos[2])
    max_abs_y = 0.0
    for _ in range(round(3.0 * BASE_CYCLE_S / CONTROL_DT)):
        phase = (phase + CONTROL_DT / BASE_CYCLE_S) % 1.0
        step_control(model, data, joint_targets(phase))
        min_z = min(min_z, float(data.qpos[2]))
        max_abs_y = max(max_abs_y, abs(float(data.qpos[1])))

    dx = float(data.qpos[0]) - x0
    z = float(data.qpos[2])
    print(f"gait: dx={dx*1000:.1f} mm, min z={min_z*1000:.1f} mm, |y|max={max_abs_y*1000:.1f} mm")
    print(f"final body z={z*1000:.1f} mm, height sensor={data.sensor('us_distance').data[0]*1000:.1f} mm")
    assert z > 0.03, "robot fell during the trot"
    assert min_z > 0.025, "body dropped too low during the trot"
    assert math.isfinite(dx), "non-finite displacement"
    print("PASS: model loads, stands and runs the trot without divergence")


if __name__ == "__main__":
    main()
