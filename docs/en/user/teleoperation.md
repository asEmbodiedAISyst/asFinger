# Teleoperation

Two tools let an operator move the arm and record episodes at the same time: one with a hand-held iPhone, one with a leader arm. The device in the hand of the operator is the leader. The arm is the follower.

The rules of [Arm tools and safety rules](robot-arm-tools.md) apply: on the real arm, an operator is at the power switch of the motors.

## What both tools do

The two tools share the arm side (`robot/teleop.py`):

- The arm starts from the folded pose or from home, unfolds to the home pose of the tool and waits. **It follows the operator only while engaged.**
- Without `--yes` the tool prints its plan and moves nothing.
- When the arm has a fault (stall, temperature, lost bus), it holds where it is. End that with `robot/arm release`.
- When the data of the leader is old or jumps, the tool disengages and the arm holds.

| Key | Function |
| --- | --- |
| Space | Engage or disengage. |
| `r` | Start an episode. Press again to stop and save it. |
| `f` | The episode failed: stop and save it with `success: false`. When nothing is recording, mark the last saved episode as failed. |
| `x` | Throw the last episode away (it moves to `data/discarded/`). |
| `h` | Disengage and go back to the home pose. |
| `q` | Quit: go home, fold, torque off. |

You do not press Enter after a key.

### What limits the tool

The tool can go as far as the hardware permits. Geometry stops it, not fixed angles:

- the limits of the joints;
- the box: the joint centres, the tool tip and the phone on the tool stay inside `calibration/workspace.yaml`; the tip stays below `--z-max` (default 0.35 m);
- the table: the tip stays at least `--z-min` (default 10 mm) above it, and the phone at least `--phone-clear` (default 15 mm);
- the arm itself: the phone and the rod stay at least `--arm-clear` (default 7 cm) from the centre lines of the base column, the upper arm and the forearm. The shape of the links is not in the model, so this distance is an estimate.

**Position has priority.** When the arm cannot reach the commanded orientation, the tool keeps its present orientation and the position continues to follow. The tool stops only when the position itself cannot be reached. The status line names the limit that is active, and the stream `limited` records it.

The speed limits are `--max-speed` (default 0.15 m/s), `--max-turn` (default 60 deg/s) and `--max-joint-speed` (default 60 deg/s).

How far the rod can tilt depends on the direction, because the joint limits decide it. With the tip at (0.30, 0, 0.05) m the model gives about 46° forward, 78° to each side and 32° toward the base.

## With an iPhone

```bash
uv run imuninn list                                    # find the name or address of the hand-held phone
uv run imuninn profile apply teleop <address>          # AR mode with the pose stream
uv run python robot/teleop_iphone.py --leader <name or address> --task push-cube          # print the plan
uv run python robot/teleop_iphone.py --leader <name or address> --task push-cube --yes
uv run python robot/teleop_iphone.py --sim --keys "1:space,3:r,14:r,15:q"                 # simulator, a scripted hand
```

The hand-held phone is mapped onto the phone on the tool. The idea is that the leader is a second pusher in the hand, with the phone in the same place on it. Then phone on phone also puts tip on tip.

- **Orientation is absolute.** The phone on the tool takes the attitude of the hand-held phone. Roll and pitch are absolute through gravity. The heading has no common reference, so it is aligned when you engage for the first time. Press `y` while disengaged to align it again.
- **Position is relative.** While engaged, the phone on the tool moves by what the hand-held phone moved since you engaged, times `--scale`. When your arm is at its end, disengage, move your hand back and engage again.
- **Hold the leader like the follower before you engage.** The status line shows the angle between the two attitudes. Above `--max-engage-angle` (default 10°) the tool refuses to engage. The difference that is left is taken up slowly, at `--catch-up-turn` (default 20 deg/s).
- `--point tip` makes the tool tip follow the translation of the leader instead of the phone. Then a pure rotation of the phone leaves the tip in place.

This tool was used on the real arm. The engage condition and the limits described above were changed after that, and those changes are tested in the simulator only.

## With a leader arm

```bash
uv run python robot/teleop_star.py --check       # leader and arm angles side by side; nothing moves
uv run python robot/teleop_star.py               # print the plan
uv run python robot/teleop_star.py --yes
uv run python robot/teleop_star.py --set-zero    # write the present pose of the leader into its servos as zero
uv run python robot/teleop_star.py --sim --fake --keys "1:space,3:r,12:r,13:q"    # simulator, a scripted leader
```

The leader is a Star Arm 102. The tool reads it in the same way as the official reBot support for LeRobot: Fashion Star bus servos with the ids 0 to 5 for the joints 1 to 6, on a USB serial adapter at 1 Mbit/s, through the package `motorbridge-smart-servo`. The mapping is joint to joint:

```text
follower joint angle = sign × leader angle + offset      signs (+1, +1, −1, −1, −1, +1), offsets 0
```

The port, the ids, the signs, the offsets and the ranges are in `calibration/star_leader.yaml`.

1. Connect the leader. On Linux the adapter appears as `/dev/ttyUSB0`. Your user must be in the group `dialout`.
2. Fold the leader to its zero pose, which corresponds to the folded pose of the arm, and run `--set-zero`. This writes to the servos permanently.
3. Run `--check` with the arm folded and the leader folded. All six lines must be near 0. Move each joint of the leader and see if the mapped value moves in the positive direction of the follower joint. If not, change the sign or the offset in the file.
4. Teleoperate. Put the leader in about the pose of the arm. You can engage when no joint differs by more than `--max-engage-diff` (default 15°).

> **Not checked on real hardware.** This tool is tested in the simulator with a scripted leader. The signs and the zero follow the official code and are not verified with a real leader arm on this arm. Do step 3 before step 4.
