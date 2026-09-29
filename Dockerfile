# syntax=docker/dockerfile:1
ARG RUST_VERSION=1.98.1
FROM rust:${RUST_VERSION}-trixie AS rust

FROM python:3.14.7-slim-trixie
ARG CMAKE_VERSION=4.4.3
ARG VCPKG_COMMIT_ID=9e593bb18ea69cc5095e012465dcd675a822ed0d
ARG DEBIAN_FRONTEND=noninteractive
ENV VCPKG_FORCE_SYSTEM_BINARIES=1 \
    VCPKG_ROOT=/opt/vcpkg \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/home/builder/.cargo \
    CARGO_NET_GIT_FETCH_WITH_CLI=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang curl git libclang-dev llvm-dev \
    libasound2-dev libgtk-3-dev libpulse-dev libssl-dev libunwind-dev \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    libva-dev libvdpau-dev libxcb-randr0-dev libxcb-shape0-dev \
    libxcb-xfixes0-dev libxdo-dev libxfixes-dev nasm ninja-build \
    pkg-config unzip zip && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir "cmake==${CMAKE_VERSION}"
COPY --from=rust /usr/local/cargo/bin/ /usr/local/bin/
COPY --from=rust /usr/local/rustup/ /opt/rustup/

RUN git init /opt/vcpkg && \
    git -C /opt/vcpkg remote add origin https://github.com/microsoft/vcpkg.git && \
    git -C /opt/vcpkg fetch --depth 1 origin "${VCPKG_COMMIT_ID}" && \
    git -C /opt/vcpkg checkout --detach FETCH_HEAD && \
    test "$(git -C /opt/vcpkg rev-parse HEAD)" = "${VCPKG_COMMIT_ID}" && \
    /opt/vcpkg/bootstrap-vcpkg.sh -disableMetrics
RUN groupadd --gid 10001 builder && \
    useradd --uid 10001 --gid builder --create-home builder && \
    mkdir -p /workspace /home/builder/.cargo && \
    chown -R builder:builder /workspace /home/builder /opt/vcpkg /opt/rustup
COPY --chmod=755 entrypoint.sh /usr/local/bin/viper-build
USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/viper-build"]
