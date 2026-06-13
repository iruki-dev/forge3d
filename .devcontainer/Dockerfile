FROM python:3.12-slim

# Keep Python output unbuffered for container logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENGINE_BACKEND=numpy \
    XLA_FLAGS="--xla_force_host_platform_device_count=4" \
    OMP_NUM_THREADS=4

WORKDIR /workspace

# System packages — merged into a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        g++ \
        fontconfig \
        fonts-dejavu \
        # OpenGL / EGL (렌더러 + 테스트용 헤드리스 GL)
        libgl1-mesa-dri \
        libgl1-mesa-dev \
        libgl-dev \
        libegl1-mesa-dev \
        libgles2 \
        libgles-dev \
        # X11 / glfw 런타임 의존
        libx11-6 \
        libxext6 \
        libxrandr2 \
        libxrender1 \
        libxxf86vm1 \
        # 헤드리스 가상 디스플레이 (CI / 서버 환경)
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Rust toolchain — maturin이 forge3d_core Rust 확장을 빌드하는 데 필요
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain stable --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

# Python deps: maturin 빌드에 필요한 파일을 먼저 복사해 레이어 캐시 활용
COPY pyproject.toml Cargo.lock* ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[dev,rl]"

# 나머지 소스 (dev 모드에서는 볼륨 마운트로 대체됨)
COPY . .

CMD ["pytest", "-q"]
