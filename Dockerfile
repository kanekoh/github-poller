# Red Hat Universal Base Image 9 with Python 3.12
FROM registry.access.redhat.com/ubi9/python-312:latest

# Switch to root for package installation
USER 0

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set ownership to default user (UID 1001 in UBI images)
RUN chown -R 1001:0 /app && \
    chmod -R g+rwX /app

# Switch to non-root user
USER 1001

# Set entrypoint
ENTRYPOINT ["python", "/app/src/poller.py"]

