# data

Recorded data. `episodes/` holds one folder per recording made with `robot/episode.py`, `robot/record.py` or the
teleoperation tools (format: docs/en/user/data-collection.md); `discarded/` the ones thrown away while recording.
`lerobot/<task>/` are LeRobot v2.1 datasets made from the episodes by `robot/to_lerobot.py`: they can be deleted and
made again. Large files: sync them, do not commit them.
