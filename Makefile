.PHONY: run docker-build docker-run setup extract demo test

# One-step Docker run (recommended)
run: docker-build docker-run

# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t fedex-price-search .

# Run Docker container with demo
docker-run:
	@echo "Running FedEx Price Search in Docker..."
	docker run --rm fedex-price-search

# Interactive Docker mode
docker-interactive:
	docker run --rm -it fedex-price-search python fedex_price_search.py

# Single query with Docker
docker-test:
	docker run --rm fedex-price-search python fedex_price_search.py --line "Ground Zone 2 1 lb"

# Local development setup (without Docker)
setup:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Extract data from PDF (if not already done)
extract:
	@echo "Extracting FedEx rates from PDF..."
	@if [ ! -f fedex_pdf_extracted.csv ]; then \
		python pdf_table_extractor.py; \
	else \
		echo "Data already extracted (fedex_pdf_extracted.csv exists)"; \
	fi

# Run demo locally
demo: setup extract
	@echo "Running FedEx Price Search Demo..."
	python fedex_price_search.py --demo

# Test single query locally
test: setup extract
	python fedex_price_search.py --line "Ground Zone 2 1 lb"

# Interactive mode locally
interactive: setup extract
	python fedex_price_search.py

# Clean up
clean:
	rm -f fedex_pdf_extracted.csv
	docker rmi -f fedex-price-search 2>/dev/null || true