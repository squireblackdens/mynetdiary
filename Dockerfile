FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y wget gnupg unzip curl chromium chromium-driver && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY main.py .

RUN mkdir /app/downloads
RUN pip install selenium schedule influxdb

CMD ["python", "main.py"]