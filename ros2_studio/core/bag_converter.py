"""Backend for ROS2 bag to CSV conversion (sqlite3 and mcap)."""
import csv
import json
import os
import subprocess
import traceback
import yaml
from datetime import datetime

try:
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    ROSBAG2_AVAILABLE = True
except ImportError:
    ROSBAG2_AVAILABLE = False
    print("Warning: rosbag2_py not available. CSV conversion will be limited.")

# Expand arrays with this many elements or fewer into individual columns.
# Larger arrays are stored as a compact JSON string.
_MAX_ARRAY_EXPAND = 64


class BagConverter:
    """Convert ROS2 bags (sqlite3 or mcap) to clean, ML-ready CSV files."""

    def __init__(self):
        self.is_converting = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bag_info(self, bag_path):
        """
        Return metadata dict for a bag folder.

        Keys: path, topics, topic_types, duration, messages, size, storage_format
        """
        try:
            result = subprocess.run(
                ['ros2', 'bag', 'info', bag_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                print(f"ros2 bag info error: {result.stderr}")
                return None

            info = {
                'path': bag_path,
                'topics': [],
                'topic_types': {},
                'duration': 'Unknown',
                'messages': 'Unknown',
                'size': 'Unknown',
                'storage_format': self._detect_storage_format(bag_path),
            }

            parsing_topics = False
            for line in result.stdout.split('\n'):
                s = line.strip()
                if 'Duration:' in s:
                    info['duration'] = s.split(':', 1)[1].strip()
                elif 'Bag size:' in s:
                    info['size'] = s.split(':', 1)[1].strip()
                elif 'Messages:' in s and 'Topic' not in s:
                    info['messages'] = s.split(':', 1)[1].strip()
                elif 'Topic information:' in s:
                    parsing_topics = True
                    if 'Topic:' in s:
                        self._parse_topic_line(
                            s.split('Topic information:', 1)[1], info
                        )
                elif parsing_topics and 'Topic:' in s and '|' in s:
                    self._parse_topic_line(s, info)

            return info
        except Exception as e:
            print(f"Error getting bag info: {e}")
            return None

    def convert_bag_to_csv(self, bag_path, output_dir, selected_topics=None,
                           progress_cb=None):
        """
        Convert bag topics to clean CSV files.

        Each topic produces:
          <topic_name>_<timestamp>.csv   — ML-ready flat data table

        Args:
            bag_path: Path to bag folder
            output_dir: Directory for output files
            selected_topics: Topics to convert (None = all)
            progress_cb: Optional callable(str) for live progress messages

        Returns:
            dict(success, converted_files, errors, total, successful)
        """
        if self.is_converting:
            return {'success': False, 'error': 'Already converting'}
        if not os.path.exists(bag_path):
            return {'success': False, 'error': f'Bag folder not found: {bag_path}'}

        def emit(msg):
            print(msg)
            if progress_cb:
                progress_cb(msg)

        try:
            os.makedirs(output_dir, exist_ok=True)
            bag_info = self.get_bag_info(bag_path)
            if not bag_info:
                return {'success': False, 'error': 'Failed to read bag metadata'}

            topics_to_convert = selected_topics or bag_info['topics']
            if not topics_to_convert:
                return {'success': False, 'error': 'No topics to convert'}

            self.is_converting = True
            converted_files = []
            errors = []

            for topic in topics_to_convert:
                emit(f'  Converting {topic} ...')
                try:
                    safe_name = topic.replace('/', '_').strip('_')
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    csv_path = os.path.join(output_dir, f'{safe_name}_{ts}.csv')
                    topic_type = bag_info['topic_types'].get(topic, 'Unknown')

                    ok = self._convert_topic(
                        bag_path, topic, csv_path,
                        bag_info['storage_format'], emit
                    )
                    if ok:
                        converted_files.append(
                            {'topic': topic, 'file': csv_path, 'type': topic_type}
                        )
                    else:
                        errors.append(f'Failed to convert {topic}')
                except Exception as e:
                    errors.append(f'Error on {topic}: {e}')

            self.is_converting = False
            return {
                'success': len(converted_files) > 0,
                'converted_files': converted_files,
                'errors': errors,
                'total': len(topics_to_convert),
                'successful': len(converted_files),
            }
        except Exception as e:
            self.is_converting = False
            return {'success': False, 'error': str(e)}

    def get_conversion_status(self):
        return {'is_converting': self.is_converting}

    def cleanup(self):
        self.is_converting = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_storage_format(self, bag_path):
        """Determine storage plugin from metadata.yaml, fall back to file extension."""
        metadata_path = os.path.join(bag_path, 'metadata.yaml')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path) as f:
                    meta = yaml.safe_load(f)
                storage_id = (
                    meta.get('rosbag2_bagfile_information', {})
                        .get('storage_identifier', '')
                )
                if storage_id:
                    return storage_id
            except Exception:
                pass
        try:
            for fname in os.listdir(bag_path):
                if fname.endswith('.mcap'):
                    return 'mcap'
        except Exception:
            pass
        return 'sqlite3'

    def _parse_topic_line(self, line, info):
        """Parse a '| Topic: /foo | Type: pkg/msg/Msg |' line into info."""
        topic_name = None
        topic_type = 'Unknown'
        for part in line.split('|'):
            part = part.strip()
            if part.startswith('Topic:'):
                topic_name = part[6:].strip()
            elif part.startswith('Type:'):
                topic_type = part[5:].strip()
        if topic_name:
            info['topics'].append(topic_name)
            info['topic_types'][topic_name] = topic_type

    def _convert_topic(self, bag_path, topic, csv_path, storage_format, emit):
        """Read one topic from the bag and write a clean CSV."""
        if not ROSBAG2_AVAILABLE:
            emit('  ⚠ rosbag2_py not installed — writing placeholder CSV')
            return self._fallback_csv(csv_path, topic)

        try:
            storage_opts = rosbag2_py.StorageOptions(
                uri=bag_path, storage_id=storage_format
            )
            reader = rosbag2_py.SequentialReader()
            reader.open(storage_opts, rosbag2_py.ConverterOptions('', ''))

            type_map = {t.name: t.type for t in reader.get_all_topics_and_types()}
            if topic not in type_map:
                emit(f'  ⚠ Topic not found in bag: {topic}')
                return False

            try:
                msg_class = get_message(type_map[topic])
            except Exception as e:
                emit(f'  ⚠ Cannot load message type {type_map[topic]}: {e}')
                return self._fallback_csv(csv_path, topic)

            reader.set_filter(rosbag2_py.StorageFilter(topics=[topic]))

            rows = []
            while reader.has_next():
                tname, data, ts_ns = reader.read_next()
                if tname != topic:
                    continue
                try:
                    msg = deserialize_message(data, msg_class)
                    row = self._flatten_message(msg)
                    ts_s = ts_ns / 1e9
                    # Prepend timestamp columns (will be sorted to front in writer)
                    row['timestamp_iso'] = datetime.fromtimestamp(ts_s).strftime(
                        '%Y-%m-%dT%H:%M:%S.%f'
                    )
                    row['timestamp_s'] = round(ts_s, 9)
                    row['timestamp_ns'] = ts_ns
                    rows.append(row)
                except Exception as e:
                    emit(f'  ⚠ Deserialise error (skipping message): {e}')

            if not rows:
                emit(f'  ⚠ No messages found for {topic}')
                return False

            self._write_csv(csv_path, rows)
            return True

        except Exception as e:
            emit(f'  ✗ {e}')
            traceback.print_exc()
            return False

    def _flatten_message(self, msg, prefix=''):
        """
        Recursively flatten a ROS message into a flat dict.

        Rules applied for clean, ML-friendly output:
        - Strip leading '_' from ROS2 slot names (internal Python convention)
        - Nested sub-messages: recurse with dot-separated key path
        - Primitive arrays <= _MAX_ARRAY_EXPAND elements: expand to key_0, key_1, …
        - Larger arrays / variable-length data: compact JSON string
        - bytes/bytearray: hex string
        """
        result = {}
        if not hasattr(msg, '__slots__'):
            result[prefix or 'value'] = msg
            return result

        for slot in msg.__slots__:
            clean = slot.lstrip('_')
            key = f'{prefix}.{clean}' if prefix else clean
            value = getattr(msg, slot)

            if hasattr(value, '__slots__'):
                result.update(self._flatten_message(value, key))
            elif isinstance(value, (bytes, bytearray)):
                result[key] = value.hex()
            elif isinstance(value, (list, tuple)):
                arr = list(value)
                if not arr:
                    result[key] = ''
                elif hasattr(arr[0], '__slots__'):
                    # Array of sub-messages — JSON string
                    result[key] = json.dumps(
                        [self._flatten_message(v) for v in arr]
                    )
                elif len(arr) <= _MAX_ARRAY_EXPAND:
                    # Expand small primitive arrays to indexed columns
                    for i, v in enumerate(arr):
                        result[f'{key}_{i}'] = v
                else:
                    result[key] = json.dumps(arr)
            else:
                result[key] = value

        return result

    def _write_csv(self, csv_path, rows):
        """
        Write rows to a clean CSV.

        Column order: timestamp_iso, timestamp_s, timestamp_ns, then all
        other fields sorted alphabetically.  Columns that are entirely
        empty are dropped.
        """
        ts_cols = ['timestamp_iso', 'timestamp_s', 'timestamp_ns']
        all_keys = set()
        for row in rows:
            all_keys.update(row.keys())
        ordered = ts_cols + sorted(all_keys - set(ts_cols))

        # Drop columns that contain only None / empty string across all rows
        non_empty_cols = [
            col for col in ordered
            if any(row.get(col) not in (None, '', b'') for row in rows)
        ]

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f, fieldnames=non_empty_cols,
                extrasaction='ignore', restval=''
            )
            writer.writeheader()
            writer.writerows(rows)

    def _fallback_csv(self, csv_path, topic):
        """Minimal placeholder when rosbag2_py is not installed."""
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp_iso', 'topic', 'note'])
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    topic,
                    'Install ros-$ROS_DISTRO-rosbag2-py for full conversion',
                ])
            return True
        except Exception:
            return False
