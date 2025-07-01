#
# -- Dockerfile for Streamlit app --
#

# Base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including ffmpeg)
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app
COPY . .

# Expose the port that Streamlit runs on
EXPOSE 8501

# Add a health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Command to run the app
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
