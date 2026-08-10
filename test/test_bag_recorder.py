# Copyright 2024 ROS2 Studio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Regression test for the stdout/stderr PIPE deadlock in BagRecorder."""
import os
import signal
import subprocess

from ros2_studio.core.bag_recorder import BagRecorder


def test_high_volume_stderr_does_not_hang(tmp_path):
    """A subprocess writing far more than the OS pipe buffer to stderr
    must not block, since stderr is redirected to a log file rather
    than an unread PIPE.
    """
    recorder = BagRecorder()

    save_location = str(tmp_path)
    recorder.bag_path = os.path.join(save_location, 'test_bag')
    recorder.stderr_log_path = f'{recorder.bag_path}.log'
    recorder._stderr_log_file = open(recorder.stderr_log_path, 'w')

    # Write well beyond the typical 64KB pipe buffer, continuously, so a
    # PIPE-based implementation would block on write() and hang.
    cmd = [
        'python3', '-c',
        "import sys\n"
        "for _ in range(20):\n"
        "    sys.stderr.write('x' * 65536)\n"
        "    sys.stderr.flush()\n"
    ]

    recorder.recording_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=recorder._stderr_log_file,
        text=True,
        preexec_fn=os.setsid
    )
    recorder.is_recording = True

    try:
        recorder.recording_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(recorder.recording_process.pid), signal.SIGKILL)
        raise AssertionError('Process did not complete within timeout - possible PIPE deadlock')

    assert recorder.recording_process.returncode == 0

    tail = recorder.read_stderr_tail(300)
    assert tail != ''
    assert len(tail) <= 300
    assert set(tail) == {'x'}


def test_read_stderr_tail_missing_file_returns_empty(tmp_path):
    """read_stderr_tail() must not raise when the log file/path is unset."""
    recorder = BagRecorder()
    assert recorder.read_stderr_tail() == ''

    recorder.stderr_log_path = str(tmp_path / 'does_not_exist.log')
    assert recorder.read_stderr_tail() == ''
