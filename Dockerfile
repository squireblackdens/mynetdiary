FROM python:3.11-slim

# Set timezone
ENV TZ=Europe/Paris

# Install Chrome & dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg unzip curl && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./google-chrome-stable_current_amd64.deb && \
    apt-get install -y chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY main.py .

# Create download directory
# RUN mkdir -p /app/downloads

# Entrypoint
CMD ["python", "main.py"]
