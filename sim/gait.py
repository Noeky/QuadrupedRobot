"""Python port of the firmware gait math, with lengths in metres.

This file mirrors firmware/servo_control/walk_math.h so that the simulated gait
and the real gait can be compared directly.  x is forward, z is down, the foot
position is relative to its hip axis.
"""

from math import acos, atan2, cos, floor, sin

THIGH = 0.040
SHIN = 0.045
STAND_HEIGHT = 0.065
FOOT_LIFT = 0.015
BASE_CYCLE_S = 4.0
STRIDE = 0.028
MAX_STRIDE = 0.050
SWING_FRACTION = 0.5
DIAGONAL_OFFSETS = (0.0, 0.5, 0.5, 0.0)  # FL, FR, RL, RR
SIDE = (1.0, -1.0, 1.0, -1.0)             # FL, FR, RL, RR: left +
TURN_SIGN = 1.0


def smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def leg_ik(x: float, z: float) -> tuple[float, float] | None:
    """Two-link sagittal IK. Returns (hip, knee) in radians or None."""
    a, b = THIGH, SHIN
    c = (x * x + z * z - a * a - b * b) / (2.0 * a * b)
    if c < -1.0 or c > 1.0 or z <= 0.0:
        return None
    k = acos(c)
    hip = atan2(x, z) + atan2(b * sin(k), a + b * cos(k))
    return hip, k


def stance_progress(t: float) -> float:
    """Ease into and out of ground travel, constant speed in the middle."""
    ramp = 0.15
    if t < ramp:
        return t * t / (2.0 * ramp * (1.0 - ramp))
    if t > 1.0 - ramp:
        remaining = 1.0 - t
        return 1.0 - remaining * remaining / (2.0 * ramp * (1.0 - ramp))
    return (t - ramp / 2.0) / (1.0 - ramp)


def foot_path(
    phase: float,
    leg: int,
    direction: float = 1.0,
    turn: float = 0.0,
    turn_gain: float = 0.5,
) -> tuple[float, float]:
    """Return foot (x, z) in metres; direction +1 forward, turn +1 left."""
    stride = STRIDE * (1.0 - turn * TURN_SIGN * direction * SIDE[leg] * turn_gain)
    stride = min(MAX_STRIDE, max(0.0, stride))
    p = (phase - DIAGONAL_OFFSETS[leg]) % 1.0
    z = STAND_HEIGHT
    if p < SWING_FRACTION:
        t = p / SWING_FRACTION
        if t < 0.25:
            x = -stride / 2.0
            z -= FOOT_LIFT * smoothstep(t / 0.25)
        elif t < 0.75:
            x = -stride / 2.0 + stride * smoothstep((t - 0.25) / 0.5)
            z -= FOOT_LIFT
        else:
            x = stride / 2.0
            z -= FOOT_LIFT * (1.0 - smoothstep((t - 0.75) / 0.25))
    else:
        x = stride / 2.0 - stride * stance_progress(
            (p - SWING_FRACTION) / (1.0 - SWING_FRACTION)
        )
    return x * direction, z


def joint_targets(
    phase: float,
    direction: float = 1.0,
    turn: float = 0.0,
    turn_gain: float = 0.5,
) -> tuple[float, float, float, float, float, float, float, float]:
    """Return eight actuator targets in FL, FR, RL, RR hip/knee order."""
    targets = []
    for leg in range(4):
        x, z = foot_path(phase, leg, direction, turn, turn_gain)
        ik = leg_ik(x, z)
        if ik is None:
            raise ValueError(f"unreachable foot target leg={leg} phase={phase:.4f}")
        targets.extend(ik)
    return tuple(targets)


if __name__ == "__main__":
    hip, knee = joint_targets(0.0)[:2]
    print(f"stand hip={hip:.4f} rad knee={knee:.4f} rad")
    for leg in range(4):
        x, z = foot_path(0.25, leg)
        print(f"leg {leg}: x={x*1000:.2f} mm z={z*1000:.2f} mm")
