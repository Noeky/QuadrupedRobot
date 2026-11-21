"""Check the rear-leg greeting wave balance in the ideal MuJoCo model.

The firmware lifts one rear leg 25 mm and oscillates it +/-8 mm while the
other three legs hold the stand.  Front-leg waves are intentionally not used:
they pitch the body strongly with this 2-DOF layout.

    python sim/test_wave.py
"""

import math
import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gait import leg_ik  # noqa: E402
from runner import CONTROL_DT, attitude  # noqa: E402

XML = Path(__file__).with_name("quadruped.xml")
WAVE_LEG = 2  # 0=FL, 1=FR, 2=RL, 3=RR


def main() -> None:
    if not XML.exists():
        from build_model import build_xml

        XML.write_text(build_xml(), encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(XML))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)
    home = data.ctrl.copy()

    pose = np.zeros(8)
    for leg in range(4):
        x_mm, z_mm = (10.0, 40.0) if leg == WAVE_LEG else (0.0, 65.0)
        ik = leg_ik(x_mm / 1000.0, z_mm / 1000.0)
        if ik is None:
            raise AssertionError(f"unreachable wave pose for leg {leg}")
        pose[2 * leg], pose[2 * leg + 1] = ik

    # Raise over 1.2 s.
    for i in range(round(1.2 / CONTROL_DT)):
        u = min(1.0, (i + 1) * CONTROL_DT / 1.2)
        u = u * u * (3.0 - 2.0 * u)
        data.ctrl[:] = home + u * (pose - home)
        for _ in range(10):
            mujoco.mj_step(model, data)

    # Wave 2 s at 1 Hz; keep the support legs at the stand pose.
    min_clearance = 1e9
    max_roll = 0.0
    max_pitch = 0.0
    min_contacts = 99
    for i in range(round(2.0 / CONTROL_DT)):
        t = i * CONTROL_DT
        x = 10.0 + 8.0 * math.sin(2.0 * math.pi * 1.0 * t)
        ik = leg_ik(x / 1000.0, 0.040)
        data.ctrl[:] = pose
        data.ctrl[2 * WAVE_LEG], data.ctrl[2 * WAVE_LEG + 1] = ik
        for _ in range(10):
            mujoco.mj_step(model, data)
        roll, pitch = attitude(data.qpos)
        max_roll = max(max_roll, abs(math.degrees(roll)))
        max_pitch = max(max_pitch, abs(math.degrees(pitch)))
        foot = data.site(f"{['FL','FR','RL','RR'][WAVE_LEG]}_foot_site").xpos
        min_clearance = min(min_clearance, (foot[2] - 0.005) * 1000.0)
        min_contacts = min(min_contacts, data.ncon)

    print(
        f"wave RL: max |roll|={max_roll:.2f} deg, max |pitch|={max_pitch:.2f} deg, "
        f"min foot clearance={min_clearance:.1f} mm, min contacts={min_contacts}"
    )
    assert max_roll < 3.0 and max_pitch < 3.0
    assert min_clearance > 10.0
    assert min_contacts >= 3
    print("PASS: rear-leg wave keeps the body level and the raised foot clear")


if __name__ == "__main__":
    main()