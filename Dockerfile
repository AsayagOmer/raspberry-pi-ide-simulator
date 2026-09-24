# Dockerfile for the Professional Raspberry Pi IDE Simulator

# ---- Base image ----
FROM python:3.12-slim

# ---- Install system dependencies ----
# pygame needs SDL2 libraries; install minimal set for audio & GUI
RUN apt-get update && apt-get install -y \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
    libasound2-dev libportaudio2 && \
    rm -rf /var/lib/apt/lists/*

# ---- Create a non‑root user (optional but recommended) ----
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN addgroup --gid $GROUP_ID appgroup && \
    adduser --uid $USER_ID --gid $GROUP_ID --disabled-password --gecos "" appuser && \
    mkdir /app && chown appuser:appgroup /app
USER appuser
WORKDIR /app

# ---- Copy the simulator source code ----
COPY . /app

# ---- Set up a virtual environment (isolated Python env) ----
RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install pygame uv && \
    # Pre‑install any third‑party deps into .sim_env (optional, can be left empty)
    /venv/bin/uv pip install --target .sim_env

# ---- Environment variables ----
# X11 forwarding for GUI (Docker on Windows needs an X server like VcXsrv)
ENV DISPLAY=${DISPLAY}

# ---- Entry point ----
# Activate the virtual environment and launch the IDE
CMD ["/bin/bash", "-c", "source /venv/bin/activate && python src/ide_app.py"]
