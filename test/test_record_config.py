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
"""Tests for the record_config loader and BagRecorder options dict."""
import os

import pytest

from ros2_studio.core.bag_recorder import BagRecorder, DEFAULT_OPTIONS, _options_to_args
from ros2_studio.core.record_config import load_record_config

EXAMPLE_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'resource', 'record_config.example.yaml'
)


def test_load_record_config_flattens_groups():
    flat = load_record_config(EXAMPLE_CONFIG_PATH)
    assert flat['storage'] == 'mcap'
    assert flat['max_cache_size'] == 104857600
    assert flat['compression_mode'] == 'none'


def test_load_record_config_missing_file_raises():
    with pytest.raises(ValueError):
        load_record_config('/nonexistent/record_config.yaml')


def test_load_record_config_unknown_group_raises(tmp_path):
    bad_config = tmp_path / 'bad.yaml'
    bad_config.write_text('not_a_real_group:\n  foo: bar\n')
    with pytest.raises(ValueError):
        load_record_config(str(bad_config))


def test_load_record_config_bad_yaml_raises(tmp_path):
    bad_config = tmp_path / 'bad.yaml'
    bad_config.write_text('output:\n  storage: [unterminated\n')
    with pytest.raises(ValueError):
        load_record_config(str(bad_config))


def test_options_to_args_translates_by_type():
    options = {
        'compression_mode': 'file',
        'compression_format': 'zstd',
        'max_cache_size': 0,
        'use_sim_time': True,
        'no_discovery': False,
        'exclude_topics': ['/tf', '/rosout'],
        'custom_data': {'session': 'test'},
        'regex': '',
    }
    args = _options_to_args(options)
    assert args == [
        '--compression-mode', 'file',
        '--compression-format', 'zstd',
        '--use-sim-time',
        '--exclude-topics', '/tf', '/rosout',
        '--custom-data', 'session=test',
    ]


def test_options_to_args_empty():
    assert _options_to_args({}) == []


def test_options_to_args_excludes_output_dir():
    """output_dir drives the GUI's save-location field, not a CLI flag,
    and must never be dumped to `ros2 bag record`'s argument list."""
    args = _options_to_args({'output_dir': '/tmp/bags', 'storage': 'mcap'})
    assert args == ['--storage', 'mcap']


def test_bag_recorder_merges_initial_options_over_defaults():
    recorder = BagRecorder(initial_options={'storage': 'sqlite3', 'compression_mode': 'file'})
    assert recorder.options['storage'] == 'sqlite3'
    assert recorder.options['compression_mode'] == 'file'
    # Defaults not overridden by initial_options are preserved
    assert recorder.options['max_bag_duration'] == DEFAULT_OPTIONS['max_bag_duration']


def test_bag_recorder_defaults_without_initial_options():
    recorder = BagRecorder()
    assert recorder.options == DEFAULT_OPTIONS
