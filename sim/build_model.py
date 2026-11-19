"""Build a simplified MuJoCo model of the R3 quadruped from the project dimensions.

The model is intentionally primitive (boxes/capsules/spheres, no imported STL) so
that it is easy to read, edit and simulate.  It keeps the dimensions that matter
for the gait: hip spacing, 40/45 mm sagittal links, 18 mm outward knee offset,
65 mm stand height and the 8 position-controlled joints.

Run:
    python sim/build_model.py
Then:
    python sim/run_stand.py
    python sim/run_gait.py
    python sim/test_sim.py
"""

from math import radians
from pathlib import Path

# --- Dimensions from the CAD assembly manifest (metres) -----------------------
HIP_X = 0.043          # front/rear hip spacing from body centre
HIP_Y = 0.054          # left/right hip spacing
KNEE_Y_OFFSET = 0.018  # knee axis is 18 mm outboard of the hip
THIGH = 0.040          # sagittal thigh length
SHIN = 0.045           # sagittal shin length
FOOT_RADIUS = 0.005
STAND_HEIGHT = 0.065   # hip axis to foot centre at the calibrated stand
BODY_HALF = (0.12765 / 2, 0.09150 / 2, 0.02750 / 2)
BODY_Z = 0.0175        # body geometric centre above the hip plane

# Mass estimates from the PLA STL volumes plus servos/board/battery.  Replace
# with SolidWorks mass properties when available; the total is about 0.30 kg.
MASS_BODY = 0.210
MASS_THIGH = 0.012
MASS_SHIN = 0.009
MASS_FOOT = 0.002

# Reference stand pose from firmware/servo_control/README.md:
# hip 43.049 deg, knee 80.406 deg.  Joint positive signs in this model:
# hip + = thigh swings forward; knee + = shin bends backward.
HIP0 = radians(43.049)
KNEE0 = radians(80.406)

LEGS = [
    # name, x sign (front +), y sign (left +)
    ("FL", +1, +1),
    ("FR", +1, -1),
    ("RL", -1, +1),
    ("RR", -1, -1),
]


def _leg_xml(name: str, xs: int, ys: int) -> str:
    hip_x = xs * HIP_X
    hip_y = ys * HIP_Y
    knee_y = ys * KNEE_Y_OFFSET
    foot_y = hip_y + knee_y
    return f"""
      <body name="{name}_hip" pos="{hip_x:.5f} {hip_y:.5f} 0">
        <joint name="{name}_hip" axis="0 -1 0" range="-1.5 1.5"/>
        <geom name="{name}_thigh" type="capsule"
              fromto="0 0 0 0 {knee_y:.5f} {-THIGH:.5f}"
              size="0.006" mass="{MASS_THIGH}"/>
        <body name="{name}_knee" pos="0 {knee_y:.5f} {-THIGH:.5f}">
          <joint name="{name}_knee" axis="0 1 0" range="0 2.6"/>
          <geom name="{name}_shin" type="capsule"
                fromto="0 0 0 0 0 {-SHIN:.5f}"
                size="0.006" mass="{MASS_SHIN}"/>
          <body name="{name}_foot" pos="0 0 {-SHIN:.5f}">
            <geom name="{name}_foot_geom" type="sphere" size="{FOOT_RADIUS}"
                  mass="{MASS_FOOT}" friction="1.2 0.02 0.001"/>
            <site name="{name}_foot_site" pos="0 0 0"/>
          </body>
        </body>
      </body>"""


def _floor_markers() -> str:
    """Visual-only lines every 50 mm along +x; no collisions."""
    out = []
    for i, x in enumerate((-0.02, 0.0, 0.05, 0.10, 0.15, 0.20)):
        color = "0.85 0.20 0.15 0.55" if i == 1 else "0.55 0.55 0.55 0.45"
        out.append(
            f'    <geom name="marker_{i}" type="box" size="0.0004 0.075 0.0004" '
            f'pos="{x:.3f} 0 0.0004" rgba="{color}" contype="0" conaffinity="0"/>'
        )
    return "\n".join(out)


def build_xml() -> str:
    legs = "".join(_leg_xml(name, xs, ys) for name, xs, ys in LEGS)
    markers = _floor_markers()
    actuators = "\n".join(
        f'    <position name="{name}_hip_act" joint="{name}_hip" ctrlrange="-1.5 1.5"/>\n'
        f'    <position name="{name}_knee_act" joint="{name}_knee" ctrlrange="0 2.6"/>'
        for name, _, _ in LEGS
    )
    sensors = "\n".join(
        f'    <jointpos name="{name}_hip_pos" joint="{name}_hip"/>\n'
        f'    <jointpos name="{name}_knee_pos" joint="{name}_knee"/>'
        for name, _, _ in LEGS
    )
    qpos = " ".join(
        ["0", "0", f"{STAND_HEIGHT + FOOT_RADIUS:.5f}", "1", "0", "0", "0"]
        + [f"{HIP0:.5f}", f"{KNEE0:.5f}"] * len(LEGS)
    )
    ctrl = " ".join([f"{HIP0:.5f}", f"{KNEE0:.5f}"] * len(LEGS))
    return f"""<mujoco model="quadruped_r3">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="0.002" integrator="implicitfast" cone="elliptic" impratio="10"/>
  <visual>
    <global offwidth="1280" offheight="720"/>
    <quality shadowsize="2048"/>
  </visual>
  <default>
    <joint type="hinge" damping="0.01" armature="0.001" frictionloss="0.002"/>
    <geom density="1240" friction="0.9 0.02 0.001"/>
    <position kp="4.0" kv="0.2" forcerange="-0.20 0.20"/>
  </default>
  <worldbody>
    <light name="key" pos="0.4 -0.4 1.2" dir="-0.4 0.4 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="floor" type="plane" size="2 2 0.1"
          friction="1.0 0.02 0.001" rgba="0.82 0.82 0.82 1"/>
{markers}
    <body name="torso" pos="0 0 {STAND_HEIGHT + FOOT_RADIUS:.5f}">
      <freejoint name="root"/>
      <geom name="torso_geom" type="box" size="{BODY_HALF[0]:.5f} {BODY_HALF[1]:.5f} {BODY_HALF[2]:.5f}"
            pos="0 0 {BODY_Z:.5f}" mass="{MASS_BODY}" rgba="0.25 0.55 0.80 1"/>
      <site name="imu" pos="0 0 0.012"/>
      <site name="us" pos="0 0 -0.014" quat="0 1 0 0"/>
{legs}
    </body>
  </worldbody>
  <actuator>
{actuators}
  </actuator>
  <sensor>
    <framequat name="torso_quat" objtype="body" objname="torso"/>
    <gyro name="torso_gyro" site="imu"/>
    <accelerometer name="torso_accel" site="imu"/>
    <framepos name="torso_pos" objtype="body" objname="torso"/>
    <rangefinder name="us_distance" site="us"/>
{sensors}
  </sensor>
  <keyframe>
    <key name="home" qpos="{qpos}" ctrl="{ctrl}"/>
  </keyframe>
</mujoco>
"""


def main() -> None:
    out = Path(__file__).with_name("quadruped.xml")
    out.write_text(build_xml(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
