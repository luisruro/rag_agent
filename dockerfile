FROM python:3.11-slim

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Create working directory
WORKDIR /app

# Copy dependencies
COPY pyproject.toml .
COPY uv.lock .

# Install system dependencies and Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

RUN uv sync --no-dev

# Copy the application
COPY . .

# Streamlit port
EXPOSE 8501

# Streamlit settings
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# start command
CMD ["uv", "run", "streamlit", "run", "app/app.py"]