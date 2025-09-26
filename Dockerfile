FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Extract data from PDF on build (so it's ready to use)
RUN python pdf_table_extractor.py

# Default command runs interactive mode
CMD ["python", "fedex_price_search.py"]