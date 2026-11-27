"""Helpers of the robot-side tests. These tests need the dependency group `robot` (uv sync --group robot) and run
the tools in the simulator only: no arm, no phone. Run: uv run --group robot pytest tests/robot"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(*args, env=None, timeout=300):
    """Run `python <args>` from the repository root, without a GL context, and return the finished process."""
    e = dict(os.environ, MUJOCO_GL='disable', PYTHONUNBUFFERED='1')
    for name in ('ASFINGER_TEST_ABORT', 'IPUSH_TEST_ABORT'):
        e.pop(name, None)
    e.update(env or {})
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=e, capture_output=True, text=True, timeout=timeout)


@pytest.fixture
def tool():
    return run
