# GradePilot AI backend: API, background worker and database migrations share one image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# OpenCV (headless) needs GLib at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch for Sentence Transformers; the default wheel bundles CUDA (several GB).
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as an unprivileged user. Uploaded files and the similarity model cache live in volumes.
RUN useradd --create-home --uid 10001 gradepilot \
    && mkdir -p /data/storage /data/hf-cache \
    && chown -R gradepilot:gradepilot /data

COPY --chown=gradepilot:gradepilot . .
RUN chmod +x docker-entrypoint.sh

USER gradepilot
ENV STORAGE_DIR=/data/storage \
    HF_HOME=/data/hf-cache

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["api"]
