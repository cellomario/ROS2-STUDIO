"""Loader for optional ros2_studio bag record default-configuration files.

The config file is a YAML document grouped by topic for readability, but is
flattened into a single option_name -> value dict on load, using the same
names as `ros2 bag record`'s CLI flags (dashes replaced with underscores).
That flattened dict is passed as `BagRecorder(initial_options=...)`, which
pre-populates `BagRecorder.options` - the single source of truth the GUI
reads from and writes into.
"""
import yaml

# Top-level groups accepted in the YAML file. Keeping this explicit means a
# typo'd group name fails loudly at launch instead of being silently ignored.
_KNOWN_GROUPS = {'output', 'topics', 'discovery', 'recording', 'compression'}


def load_record_config(path):
    """
    Load and flatten a bag record default-configuration YAML file.

    Args:
        path: Path to the YAML config file

    Returns:
        Flat dict of flag_name -> value (dashes replaced with underscores,
        matching `ros2 bag record` CLI flag names)

    Raises:
        ValueError: If the file is missing, not valid YAML, or contains an
            unrecognized top-level group
    """
    try:
        with open(path, 'r') as config_file:
            raw = yaml.safe_load(config_file) or {}
    except OSError as e:
        raise ValueError(f"Cannot read record config '{path}': {e}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in record config '{path}': {e}") from e

    unknown_groups = set(raw) - _KNOWN_GROUPS
    if unknown_groups:
        raise ValueError(
            f"Unknown group(s) {sorted(unknown_groups)} in record config '{path}'. "
            f"Expected one of {sorted(_KNOWN_GROUPS)}."
        )

    flat_options = {}
    for group_values in raw.values():
        if group_values:
            flat_options.update(group_values)
    return flat_options
