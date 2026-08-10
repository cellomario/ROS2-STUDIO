"""Main entry point for ROS2 Studio GUI application."""
import sys
import matplotlib
try:
    matplotlib.use('Qt5Agg')
except Exception:
    matplotlib.use('Agg')
import rclpy
from PyQt5.QtWidgets import QApplication
from ros2_studio.gui.main_window import MainWindow
from ros2_studio.core.record_config import load_record_config


def main(record_config_path=None):
    """Initialize and run the ROS2 Studio GUI application.

    Args:
        record_config_path: Optional path to a YAML file with default bag
            record settings, applied as the initial Bag Recorder tab state.
    """
    record_config = None
    if record_config_path:
        try:
            record_config = load_record_config(record_config_path)
        except ValueError as e:
            print(f"Error loading --record-config: {e}", file=sys.stderr)
            return 1

    # Try to initialize ROS2 — app still opens if ROS2 is not sourced,
    # but monitor/dashboard features will be unavailable.
    ros2_initialized = False
    try:
        rclpy.init()
        ros2_initialized = True
    except Exception as e:
        print(f"Warning: ROS2 initialization failed: {e}")
        print("Bag record/play/convert features will still work.")

    app = QApplication(sys.argv)
    app.setApplicationName('ROS2 Studio')
    app.setOrganizationName('ROS2')

    window = MainWindow(record_config=record_config, record_config_path=record_config_path)
    window.show()

    try:
        exit_code = app.exec_()
    finally:
        if ros2_initialized:
            try:
                rclpy.shutdown()
            except Exception:
                pass

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
