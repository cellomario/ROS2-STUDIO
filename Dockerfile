FROM ros:jazzy

# Update apt package index and install emoji font for GUI icons
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-color-emoji

# Copy the repository into the workspace
WORKDIR /ros2_ws
COPY . src/ros2_studio/

# Update rosdep and install dependencies
RUN rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy && \
    rm -rf /var/lib/apt/lists/*

# Build the package
RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --packages-select ros2_studio

# Avoid XDG_RUNTIME_DIR warning
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
RUN mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root

# Source workspace on entry
ENTRYPOINT ["/bin/bash", "-c", ". /ros2_ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["ros2", "studio"]
