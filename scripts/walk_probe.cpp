// Host-only probe: reuse the submitted controller, its clock and servo doubles.
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include "../firmware/servo_control/servo_control.ino"

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    const bool timed = std::string(argv[1]) == "pwm";
    const float direction = std::stof(argv[2]), turn = std::stof(argv[3]);
    setup();
    for (unsigned j = 0; j < SERVO_COUNT; ++j) {
        std::cin >> standAngles[j] >> jointDirection[j];
        writeServoAngle(j, standAngles[j], 1);
    }
    standCaptured = true;
    for (auto& leg : legTuning) {
        std::cin >> leg.lift >> leg.depth >> leg.stride >> leg.liftPart >> leg.lowerPart;
    }
    std::cin >> walkCenterX >> walkBias >> walkFootOffsetX >> walkTurnGain >> walkSpeed >> walkDeadband;
    if (!std::cin || !walkReady()) return 3;
    float h0, k0;
    if (!legIK(0, CALIBRATION_HEIGHT_MM, h0, k0)) return 4;
    if (timed && !startWalk(direction, turn)) return 5;
    std::cout << std::setprecision(10);
    const int count = timed ? 675 : 201; // 13.5 s at 50 Hz, or one cycle including its boundary.
    for (int i = 0; i < count; ++i) {
        float targets[SERVO_COUNT];
        const float phase = i / 200.f;
        if (timed) {
            fakeMillis += WALK_FRAME_MS;
            updateWalk();
            for (unsigned j = 0; j < SERVO_COUNT; ++j)
                targets[j] = (commandPulses[j] - SERVO_MIN_US) * 180.f / (SERVO_MAX_US - SERVO_MIN_US);
        } else if (!calculateWalk(phase, targets, legTuning, direction, turn, walkTurnGain)) return 6;
        std::cout << (timed ? (i+1)*0.02 : phase);
        for (unsigned j = 0; j < SERVO_COUNT; ++j) {
            const float reference = j % 2 ? k0 : h0;
            const double anatomical = reference + (targets[j] - standAngles[j]) / jointDirection[j];
            std::cout << ',' << anatomical * 3.141592653589793 / 180.;
        }
        std::cout << '\n';
    }
}
