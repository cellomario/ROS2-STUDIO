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


def main():
    """Initialize and run the ROS2 Studio GUI application."""
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

    window = MainWindow()
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
