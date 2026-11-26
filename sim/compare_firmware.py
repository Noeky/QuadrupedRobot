"""Compare the shipped C++ controller with MuJoCo. No serial connection is used.

Run python sim/compare_firmware.py from 04_控制代码, with g++ on PATH.
The saved ws snapshot is read from the accompanying calibration file.
"""
import io
import re
import subprocess
import tempfile
from pathlib import Path

import mujoco
import numpy as np

from gait import foot_path, joint_targets
from runner import GaitRunner, apply_model_scales, attitude, yaw
from servo import ServoBank

ROOT = Path(__file__).resolve().parents[1]
XML = Path(__file__).with_name("quadruped.xml")
MODES = [("forward", 1, 0), ("back", -1, 0), ("left", 1, 1), ("right", 1, -1),
         ("back-left", -1, 1), ("back-right", -1, -1)]


def read_profiles():
    calibration = (ROOT / "firmware/servo_control/calibration_backup.md").read_text(encoding="utf-8")
    snap = calibration.split("## 当前备份", 1)[1].split("```text", 1)[1].split("```", 1)[0]
    joints = re.findall(r"^\d+ stand=(\d+) dir=(-?\d+)", snap, re.M)
    legs = re.findall(r"^leg \d+ lift=([\d.]+) depth=([-\d.]+) stride=([\d.]+) lift%=([\d.]+) lower%=([\d.]+)", snap, re.M)
    assert len(joints) == 8 and len(legs) == 4
    def field(name):
        return float(re.search(r"\b" + name + r"=([-\d.]+)", snap)[1])
    common = "\n".join(" ".join(a) for a in joints)
    saved = [tuple(map(float, leg)) for leg in legs]
    def config(legs, center, bias, offset):
        rows = [common] + [f"{h} {d} {s} {up/100} {down/100}" for h,d,s,up,down in legs]
        rows.append(f"{center} {bias} {offset} {field('gain')} {field('speed')} {field('deadband')}")
        return "\n".join(rows) + "\n"
    return config([(15,0,28,25,25)]*4,0,0,0), config(saved,field("walkCenter"),field("walkBias"),field("footOffset"))


def targets(exe, config, mode, direction, turn):
    r = subprocess.run([str(exe),mode,str(direction),str(turn)], input=config, text=True,
                       capture_output=True, check=True)
    return np.loadtxt(io.StringIO(r.stdout), delimiter=",")


def servo_bank():
    return ServoBank(n=8,tau=.08,deadband=np.radians(.5),backlash=np.radians(1),max_rate=np.radians(600))


def replay(commands):
    model = mujoco.MjModel.from_xml_path(str(XML))
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model,data,0)
    mujoco.mj_forward(model,data)
    servo = servo_bank()
    servo.reset(data.ctrl.copy())
    start_x = None
    max_tilt = 0.
    for frame, row in enumerate(commands,1):
        data.ctrl[:] = np.clip(servo.step(row[1:],.02),-1.5,2.6)
        for _ in range(round(.02/model.opt.timestep)):
            mujoco.mj_step(model,data)
        if frame==75: start_x=float(data.qpos[0])
        roll,pitch=attitude(data.qpos)
        max_tilt=max(max_tilt,abs(roll),abs(pitch))
        if data.qpos[2] < .04 or max_tilt > .7: break
    return (frame*.02,(float(data.qpos[0])-start_x)*1000 if start_x is not None else float("nan"),
            np.degrees(yaw(data.qpos)),np.degrees(max_tilt),frame!=len(commands) or data.qpos[2]<.04 or max_tilt>.7)


def main():
    baseline,saved=read_profiles()
    print(f"MuJoCo {mujoco.__version__}, NumPy {np.__version__}")
    with tempfile.TemporaryDirectory() as tmp:
        exe=Path(tmp)/"walk_probe.exe"
        subprocess.run(["g++","-std=c++11","-O2","-Iscripts/test_support","scripts/walk_probe.cpp","-o",str(exe)],cwd=ROOT,check=True)
        largest_q=largest_foot=0.
        for name,d,t in MODES:
            raw=targets(exe,baseline,"geometry",d,t)
            python_q=np.array([joint_targets(ph,d,t,.5) for ph in raw[:,0]])
            largest_q=max(largest_q,float(np.degrees(abs(raw[:,1:]-python_q)).max()))
            hip,knee=raw[:,1::2],raw[:,2::2]
            x=40*np.sin(hip)+45*np.sin(hip-knee)
            z=40*np.cos(hip)+45*np.cos(hip-knee)
            truth=np.array([[foot_path(p,l,d,t,.5) for l in range(4)] for p in raw[:,0]])*1000
            largest_foot=max(largest_foot,float(np.hypot(x-truth[:,:,0],z-truth[:,:,1]).max()))
            model=mujoco.MjModel.from_xml_path(str(XML))
            runner=GaitRunner(model,mujoco.MjData(model),direction=d,turn=t,servo=servo_bank())
            m=runner.run(13.5)
            print(f"{name:10} baseline: t={m.time_s:.2f}s dx={m.dx_gait_mm:+.1f}mm yaw={m.final_yaw_deg:+.1f}deg fell={m.fell}")
            sec,dx,heading,tilt,fell=replay(targets(exe,saved,"pwm",d,t))
            assert not (m.fell or fell) and sec == m.time_s == 13.5, (name, m.time_s, sec)
            print(f"{name:10} saved PWM: t={sec:.2f}s dx={dx:+.1f}mm yaw={heading:+.1f}deg maxTilt={tilt:.1f}deg fell={fell}")
        print(f"Baseline: 6 modes x 201 phases x 4 legs, max target error {largest_foot:.6f} mm; max joint error {largest_q:.6f} deg")
        assert largest_foot<.001 and largest_q<.001
        model=mujoco.MjModel.from_xml_path(str(XML))
        apply_model_scales(model,com_x=.015)
        m=GaitRunner(model,mujoco.MjData(model),servo=servo_bank()).run(13.5)
        print(f"Baseline sensitivity, torso COM +15 mm: t={m.time_s:.2f}s pitch={m.final_pitch_deg:.1f}deg fell={m.fell}")
if __name__=="__main__":
    main()
