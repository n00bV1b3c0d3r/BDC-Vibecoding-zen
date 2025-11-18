# Smart Business Day Calculator - Docker Image
# Multi-stage build for optimal image size

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY index.html .
COPY custom_rules.json* ./

# Create custom_rules.json if it doesn't exist (will be created by app on first run)
RUN touch custom_rules.json || true

# Expose port
EXPOSE 8080

# Use gunicorn for production (better than Flask dev server)
# Workers: 2 * CPU cores + 1 (rule of thumb)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]
