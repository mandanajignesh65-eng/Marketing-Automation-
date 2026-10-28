# Meridian in a container, for the Mumbai server (see deploy/README.md). Render does not use this file.
FROM python:3.11-slim
# tzdata so TZ=Asia/Kolkata gives India time ("today" and dates follow it)
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# One process only: the Zoho sync, alert checks and backups run as threads inside it.
CMD ["uvicorn", "meridian.api:app", "--host", "0.0.0.0", "--port", "8321", "--proxy-headers", "--forwarded-allow-ips", "*"]
