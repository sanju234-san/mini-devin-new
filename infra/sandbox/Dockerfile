# Hardened base execution sandbox image for Mini-Devin Python test runs
# Pinned to python:3.12-slim (never :latest)
FROM python:3.12-slim

# Avoid interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install git (required for diff applying) and clean up apt caches
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install standard test runner
RUN pip install --no-cache-dir pytest==8.3.3

# Create the non-root sandbox user (uid 1000, gid 1000)
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g sandbox -m -s /bin/bash sandbox

# Create workspace and temporary directories with correct ownership
RUN mkdir -p /workspace /tmp && \
    chown -R sandbox:sandbox /workspace /tmp

WORKDIR /workspace

# Container strictly executes as unprivileged non-root user
USER sandbox
