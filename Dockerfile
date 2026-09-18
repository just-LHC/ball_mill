# 1. Use an official lightweight Python runtime
FROM python:3.10-slim

# 2. Prevent Python from buffering stdout/stderr (ensures instant Cloud Run logging)
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-install-recommends -r requirements.txt

# 6. Copy application code into the container
COPY . .

# 7. Expose the port used by Streamlit (Cloud Run uses 8080 by default)
EXPOSE 8080

# 8. Launch Streamlit binding to 0.0.0.0 and port 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]