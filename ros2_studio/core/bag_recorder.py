"""Backend for ROS2 bag recording functionality."""
import subprocess
import os
import re
from datetime import datetime
import signal


class BagRecorder:
    """Handle ROS2 bag recording operations."""
    
    def __init__(self):
        """Initialize bag recorder."""
        self.recording_process = None
        self.recording_topics = []
        self.save_location = None
        self.bag_path = None
        self.storage_format = 'mcap'
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
    
    def start_recording(self, topics, save_location, storage_format='mcap', duration=0, split_duration=0):
        """
        Start recording selected topics to a bag file.

        Args:
            topics: List of topic names to record
            save_location: Directory path where bag should be saved
            storage_format: Storage plugin to use ('sqlite3' or 'mcap')
            duration: Total recording time in seconds (0 = no limit)
            split_duration: Split bag into new file every N seconds (0 = no split)
        """
        if self.is_recording:
            print("Already recording!")
            return False

        if not topics:
            print("No topics specified!")
            return False

        try:
            # Create save directory if it doesn't exist
            os.makedirs(save_location, exist_ok=True)

            # Generate bag name with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            bag_name = f'ros2_studio_bag_{timestamp}'
            self.bag_path = os.path.join(save_location, bag_name)
            self.storage_format = storage_format

            # Build command
            cmd = ['ros2', 'bag', 'record']
            cmd.extend(topics)
            cmd.extend(['-o', self.bag_path])
            cmd.extend(['--storage', storage_format])
            
            # Use CLI --duration flag if supported, otherwise GUI timer handles it
            if duration > 0 and self.cli_duration_supported:
                cmd.extend(['--duration', str(duration)])

            # Split bag into multiple files every N seconds (-d is available on all distros)
            if split_duration > 0:
                cmd.extend(['-d', str(split_duration)])

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
            
            self.recording_topics = topics
            self.save_location = save_location
            self.is_recording = True
            
            print(f"Started recording {len(topics)} topics to {self.bag_path}")
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
                self.recording_process.wait(timeout=10)

            saved_path = self.bag_path
            self._close_stderr_log()

            # Reset state
            self.recording_process = None
            self.is_recording = False
            self.recording_topics = []
            
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
            'topics': self.recording_topics,
            'save_location': self.save_location,
            'bag_path': self.bag_path,
            'storage_format': self.storage_format
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
