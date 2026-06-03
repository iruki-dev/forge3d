FROM python:3.12-slim

# Keep Python output unbuffered for container logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Default backend (override with -e ENGINE_BACKEND=jax)
    ENGINE_BACKEND=numpy \
    # JAX multi-core on CPU
    XLA_FLAGS="--xla_force_host_platform_device_count=4" \
    OMP_NUM_THREADS=4

WORKDIR /workspace

# Build deps only (no extra bloat)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*
    
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-dejavu \
    libgl1-mesa-dri \
    libgl1-mesa-dev \
    libegl1-mesa-dev \
    libxext6 \
    libx11-6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer-cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source (volume-mounted in dev, baked in prod)
COPY . .

CMD ["pytest", "-q"]
