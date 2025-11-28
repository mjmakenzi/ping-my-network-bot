FROM python:3.11-slim

# Install system dependencies for ping/traceroute
RUN apt-get update && apt-get install -y \
    iputils-ping \
    traceroute \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Remove the non-root user setup - run as root for network access
# RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
# USER botuser

# Run the bot
CMD ["python", "main.py"]