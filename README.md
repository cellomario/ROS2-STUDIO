# ROS2 Studio 🤖

A comprehensive ROS2 monitoring and management tool with GUI for performance monitoring, bag operations, and system diagnostics.

## Features

- 📊 **Performance Monitor** - Real-time CPU/memory/frequency monitoring for topics and nodes with graphical plots
- 🔴 **Bag Recorder** - Multi-topic recording with sqlite3/mcap format selection, auto-stop duration, and bag splitting
- ▶️ **Bag Player** - Playback of sqlite3/mcap bags with adjustable rate (0.1x-10x) and loop controls
- 🔄 **Bag to CSV Converter** - Convert sqlite3/mcap bags to clean ML-ready CSV files
- 🎛️ **System Dashboard** - System resources, ROS2 entities, network stats, and process monitoring

## Installation

```bash
# Build
git clone https://github.com/Sourav0607/ROS2-STUDIO
cd ~/ROS2-STUDIO
rosdep update && rosdep install --from-paths . -r -y
colcon build
source install/setup.bash

# Launch
ros2 studio
```

## Usage

```
ros2 studio
```

Launch the GUI and select features from the dropdown menu:
1. **Performance Monitor** - Select Topics/Nodes and view real-time metrics
2. **Bag Recorder** - Select topics, choose format (sqlite3/mcap), set duration/split, start/stop recording
3. **Bag Player** - Load bag folder, set rate/loop options, control playback
4. **CSV Converter** - Load bag folder, select topics, convert to CSV
5. **System Dashboard** - View system resources, ROS2 entities, network, and processes

## Project Structure

```
ros2_studio/
├── ros2_studio/
│   ├── core/          # Backend (monitoring, recording, playback, conversion, dashboard)
│   ├── gui/           # UI widgets for each feature
│   ├── command/       # ROS2 CLI extension
│   └── main.py
├── package.xml        # Dependencies
└── setup.py           # Entry points
```

## Requirements

- ROS2 (Foxy/Galactic/Humble/Iron/Jazzy/Lyrical or later)
- Python 3.8+
- PyQt5, matplotlib, psutil, rosbag2_py

## Screenshots

### Performance Monitor
![Performance Monitor](resource/screenshots/performanc%20metrics.png)
*Real-time CPU, memory, and frequency monitoring with graphical plots*

### Bag Recorder
![Bag Recorder](resource/screenshots/bag%20recorder.png)
*Multi-topic selection with format, duration, and split controls*

### Bag Player
![Bag Player](resource/screenshots/bag%20play.png)
*Playback control with adjustable rate and loop options*

### Bag to CSV Converter
![CSV Converter](resource/screenshots/convert%20to%20csv.png)
*Convert bag topics to ML-ready CSV with full message deserialization*

### System Dashboard
![System Dashboard](resource/screenshots/systm%20dashboard.png)
*System resources, ROS2 entities, network stats, and process monitoring*

## Docker

You can build this project with docker:
```bash
docker build -t ros2-studio .
```
To run the dockerized app:
```bash
# Allow X11 connections from containers (run once per session)
xhost +local:

docker run -it --rm \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    ros2-studio
```
The container defaults to the X11 (xcb) Qt backend. If you're on a Wayland-only system without XWayland, override with:
```bash
docker run -it --rm \
    -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY \
    -e QT_QPA_PLATFORM=wayland \
    -e XDG_RUNTIME_DIR=/tmp/runtime-root \
    -v $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY:/tmp/runtime-root/$WAYLAND_DISPLAY \
    ros2-studio
```

## License

Apache License 2.0

## Authors

Sourav Hawaldar (sourav.hawaldar@gmail.com)
Marcello Cellina (cellina.marcello@gmail.com)

## Repository

GitHub: [https://github.com/Sourav0607/ROS2-STUDIO](https://github.com/Sourav0607/ROS2-STUDIO)

---

**Note**: This is an independent community tool, not officially affiliated with Open Robotics or the ROS project.
