# Use official Python image with pip; tag can be changed as needed
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install OS/build dependencies, install Python packages, then remove build deps to keep image small
# Make the step verbose and non-interactive so failures surface clearly. Include common native libs
# required by scapy and cryptography-related wheels.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies and Python packages in one step
RUN apt-get update -yqq \
    && apt-get install -yqq --no-install-recommends \
        build-essential \
        gcc \
        iproute2 \
        net-tools \
        libpcap-dev \
        libffi-dev \
        libssl-dev \
        python3-dev \
        ca-certificates \
        wget \
        tcpdump \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -yqq --auto-remove build-essential gcc python3-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip /tmp

# Copy all source and static files into image
COPY . .

# Create a non-root user and give ownership of the app directory
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Expose port 80 for the container (we'll run the Flask app on PORT=80 inside)
EXPOSE 80

# Ensure unbuffered output for logs and set runtime PORT to 80 inside container
ENV PYTHONUNBUFFERED=1 \
    PORT=80 \
    FLASK_DEBUG=0

# Start the application using python so our `server.py` entrypoint is used.
CMD ["python", "server.py"]

