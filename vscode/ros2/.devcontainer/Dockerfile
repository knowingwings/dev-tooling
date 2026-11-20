# Same ROS 2 toolchain at work and home. Change the tag for other distros (e.g. ros:humble).
FROM ros:jazzy

ARG USERNAME=ubuntu
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      sudo git gdb clangd python3-pip python3-colcon-common-extensions \
      python3-rosdep ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/* \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}

# Lint kit tools. clang-tidy from PyPI because the lint kit needs 20+ (Ubuntu 24.04 apt ships 18).
RUN pip install --break-system-packages --no-cache-dir pre-commit ruff clang-tidy

USER ${USERNAME}
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /home/${USERNAME}/.bashrc
