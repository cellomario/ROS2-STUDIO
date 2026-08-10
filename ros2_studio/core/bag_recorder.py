"""Backend for ROS2 bag recording functionality."""
import subprocess
import os
import re
from datetime import datetime
import signal

# Default values for every supported `ros2 bag record` option. A record
# config YAML file (see record_config.py) pre-populates this dict on top of
# these defaults, and the GUI reads/writes directly into it afterwards - so
# at record time `options` always holds the seamless merge of file defaults
# and whatever the user changed.
DEFAULT_OPTIONS = {
    'topics': [],
    'storage': 'mcap',
    'max_bag_duration': 0,   # GUI "Split Every" (seconds), -d/--max-bag-duration
}

# Options that live in `options` for convenience (so a single record config
# file/dict can set them) but are not `ros2 bag record` CLI flags themselves,
# so `_options_to_args()` must never dump them.
_NON_CLI_OPTIONS = {'output_dir'}


def _options_to_args(options):
    """
    Translate the options dict into `ros2 bag record` CLI arguments.

    Translation is driven purely by each value's Python type, since every
    supported option maps 1:1 to a `--option-name` argument:
      bool  True  -> ['--option-name'];      False/None -> omitted
      list/tuple  -> ['--option-name', item1, item2, ...]
      dict        -> ['--option-name', 'KEY1=VALUE1', ...]
      scalar      -> ['--option-name', str(value)];  skipped if falsy/empty

    Args:
        options: Flat dict of option_name (underscores) -> value

    Returns:
        List of CLI argument tokens
    """
    args = []
    for option_name, value in options.items():
        if option_name in _NON_CLI_OPTIONS:
            continue
        flag = f"--{option_name.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(flag)
        elif isinstance(value, (list, tuple)):
            if value:
                args.append(flag)
                args.extend(str(item) for item in value)
        elif isinstance(value, dict):
            if value:
                args.append(flag)
                args.extend(f'{key}={val}' for key, val in value.items())
        elif value:
            args.extend([flag, str(value)])
    return args


class BagRecorder:
    """Handle ROS2 bag recording operations.

    `self.options` is the single source of truth for every `ros2 bag record`
    setting (topics, storage format, compression, QoS overrides, etc.). It
    starts out as `DEFAULT_OPTIONS`, optionally pre-populated from a loaded
    record config file, and the GUI reads/writes directly into it. At
    `start_recording()` time, the full dict is dumped to CLI arguments.
    """

    def __init__(self, initial_options=None):
        """Initialize bag recorder.

        Args:
            initial_options: Optional dict merged on top of DEFAULT_OPTIONS
                (e.g. loaded from a record config file)
        """
        self.options = dict(DEFAULT_OPTIONS)
        self.options.update(initial_options or {})

        self.recording_process = None
        self.save_location = None
        self.bag_path = None
        self.is_recording = False
        self.stderr_log_path = None
        self._stderr_log_file = None
        self.cli_duration_supported = self._check_duration_flag_support()

    def _check_duration_flag_support(self):
        """Return True if ros2 bag record supports --duration for total recording time."""
        try:
            result = subprocess.run(
                ['ros2', 'bag', 'record', '--help'],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout + result.stderr
            # Match --duration as a standalone flag, not --max-bag-duration
            return bool(re.search(r'[\s\[]--duration\b', output))
        except Exception:
            return False

    def get_all_topics(self):
        """Get list of all active topics."""
        try:
            result = subprocess.run(
                ['ros2', 'topic', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                topics = [topic.strip() for topic in result.stdout.strip().split('\n') if topic.strip()]
                return sorted(topics)
            return []
        except Exception as e:
            print(f"Error getting topics: {e}")
            return []

    def start_recording(self, save_location, duration=0):
        """
        Start recording to a bag file, using the current `self.options`.

        Args:
            save_location: Directory path where bag should be saved
            duration: Total recording time in seconds (0 = no limit). Not
                part of `self.options` since it is a GUI-only concept: it
                maps to the CLI --duration flag where supported, and to a
                GUI-side auto-stop timer otherwise.
        """
        if self.is_recording:
            print("Already recording!")
            return False

        if not self.options.get('topics'):
            print("No topics specified!")
            return False

        try:
            # Create save directory if it doesn't exist
            os.makedirs(save_location, exist_ok=True)

            # Generate bag name with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            bag_name = f'ros2_studio_bag_{timestamp}'
            self.bag_path = os.path.join(save_location, bag_name)

            # Build command: base verb, all options dumped generically, then -o
            cmd = ['ros2', 'bag', 'record']
            cmd.extend(_options_to_args(self.options))
            cmd.extend(['-o', self.bag_path])

            # Use CLI --duration flag if supported, otherwise GUI timer handles it
            if duration > 0 and self.cli_duration_supported:
                cmd.extend(['--duration', str(duration)])

            # Redirect stderr to a log file instead of an unread PIPE. An unread
            # PIPE fills its OS buffer under sustained output (e.g. high-bitrate
            # topics printing warnings) and blocks the subprocess on write(),
            # which can stall bag writing. stdout is discarded entirely.
            self.stderr_log_path = f'{self.bag_path}.log'
            self._stderr_log_file = open(self.stderr_log_path, 'w')

            # Start recording process
            self.recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_log_file,
                text=True,
                preexec_fn=os.setsid  # Create new process group
            )

            self.save_location = save_location
            self.is_recording = True

            print(f"Started recording {len(self.options['topics'])} topics to {self.bag_path}")
            return True

        except Exception as e:
            print(f"Error starting recording: {e}")
            self.is_recording = False
            return False

    def stop_recording(self):
        """
        Stop the current recording.
        
        Returns:
            Path to the saved bag file, or None if not recording
        """
        if not self.is_recording or not self.recording_process:
            print("Not currently recording!")
            return None
        
        try:
            # Only send SIGINT if process is still running.
            # If duration expired it already exited on its own.
            if self.recording_process.poll() is None:
                os.killpg(os.getpgid(self.recording_process.pid), signal.SIGINT)
                # Allow up to 30s for graceful shutdown: high-bitrate recordings
                # can have a large unflushed writer buffer, and killing too soon
                # risks a corrupted/unreadable bag file.
                self.recording_process.wait(timeout=30)

            saved_path = self.bag_path
            self._close_stderr_log()

            # Reset state
            self.recording_process = None
            self.is_recording = False
            
            print(f"Stopped recording. Bag saved to: {saved_path}")
            return saved_path
            
        except subprocess.TimeoutExpired:
            # Force kill if graceful shutdown fails
            print("Timeout waiting for recording to stop, forcing...")
            try:
                os.killpg(os.getpgid(self.recording_process.pid), signal.SIGKILL)
                self.recording_process.wait(timeout=5)
            except Exception as e:
                print(f"Force kill failed: {e}")
            self._close_stderr_log()
            self.recording_process = None
            self.is_recording = False
            return self.bag_path
            
        except Exception as e:
            print(f"Error stopping recording: {e}")
            self._close_stderr_log()
            self.recording_process = None
            self.is_recording = False
            return None
    
    def get_recording_status(self):
        """
        Get current recording status.
        
        Returns:
            Dictionary with recording status information
        """
        return {
            'is_recording': self.is_recording,
            'topics': self.options.get('topics', []),
            'save_location': self.save_location,
            'bag_path': self.bag_path,
            'storage_format': self.options.get('storage'),
        }

    def _close_stderr_log(self):
        """Close the stderr log file handle if it is currently open."""
        if self._stderr_log_file is not None:
            try:
                self._stderr_log_file.close()
            except Exception as e:
                print(f"Error closing stderr log: {e}")
            self._stderr_log_file = None

    def read_stderr_tail(self, max_chars=300):
        """
        Read the tail of the captured stderr log for the last recording process.

        Args:
            max_chars: Maximum number of characters to return from the end of the log

        Returns:
            The last `max_chars` characters of the stderr log, or '' if unavailable
        """
        self._close_stderr_log()
        if not self.stderr_log_path:
            return ''
        try:
            with open(self.stderr_log_path, 'r') as log_file:
                content = log_file.read()
            return content.strip()[-max_chars:]
        except Exception:
            return ''

    def cleanup(self):
        """Clean up resources."""
        if self.is_recording:
            self.stop_recording()
        self._close_stderr_log()
