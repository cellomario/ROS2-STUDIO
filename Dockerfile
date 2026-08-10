FROM ros:jazzy

# Update apt package index
RUN apt-get update

# Copy the repository into the workspace
WORKDIR /ros2_ws
COPY . src/ros2_studio/ 

# Update rosdep and install dependencies
RUN rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y

# Build the package
RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --packages-select ros2_studio


# Source workspace on entry
ENTRYPOINT ["/bin/bash", "-c", ". /ros2_ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["ros2", "studio"]
