"""Check forward / backward / left / right in the ideal MuJoCo model.

This validates the same direction/turn math that is used by the firmware.
    python sim/test_modes.py
"""

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).parent))
from runner import GaitRunner  # noqa: E402

XML = Path(__file__).with_name("quadruped.xml")
SECONDS = 13.5  # 1.5 s transition + 3 cycles at 1x


def main() -> None:
    if not XML.exists():
        from build_model import build_xml

        XML.write_text(build_xml(), encoding="utf-8")
    cases = [
        ("forward", 1.0, 0.0),
        ("back", -1.0, 0.0),
        ("left", 1.0, 1.0),
        ("right", 1.0, -1.0),
    ]
    results = {}
    for name, direction, turn in cases:
        model = mujoco.MjModel.from_xml_path(str(XML))
        data = mujoco.MjData(model)
        runner = GaitRunner(
            model,
            data,
            direction=direction,
            turn=turn,
            turn_gain=0.5,
        )
        m = runner.run(SECONDS)
        assert runner.frame == 675 and m.time_s == SECONDS, (runner.frame, m.time_s)
        results[name] = m
        print(
            f"{name:8s} dx={m.dx_gait_mm:7.1f} mm  "
            f"|y|max={m.max_abs_y_mm:5.1f} mm  yaw={m.final_yaw_deg:+7.1f} deg  "
            f"min_z={m.min_z_mm:5.1f} mm  fell={m.fell}"
        )

    assert not results["forward"].fell
    assert not results["back"].fell
    assert not results["left"].fell
    assert not results["right"].fell
    assert results["forward"].dx_gait_mm > 100.0
    assert results["back"].dx_gait_mm < -100.0
    assert results["left"].final_yaw_deg > 20.0
    assert results["right"].final_yaw_deg < -20.0
    print("PASS: forward/back/left/right signs and no-fall in the ideal model")


if __name__ == "__main__":
    main()
