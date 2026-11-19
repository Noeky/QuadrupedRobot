"""Load the MuJoCo model and hold the calibrated stand pose.

Run:
    python sim/build_model.py
    python sim/run_stand.py
"""

import time
from pathlib import Path

import mujoco
import mujoco.viewer

XML = Path(__file__).with_name("quadruped.xml")


def main() -> None:
    if not XML.exists():
        raise SystemExit("quadruped.xml missing; run: python sim/build_model.py")
    model = mujoco.MjModel.from_xml_path(str(XML))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    print(f"total mass: {model.body_subtreemass[1]:.3f} kg")
    print("holding home pose; close the viewer to stop")
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            start = time.perf_counter()
            mujoco.mj_step(model, data)
            viewer.sync()
            remaining = model.opt.timestep - (time.perf_counter() - start)
            if remaining > 0:
                time.sleep(remaining)


if __name__ == "__main__":
    main()
