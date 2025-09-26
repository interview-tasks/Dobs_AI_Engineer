#!/usr/bin/env python3
"""
PDF Table Extractor
Extract tables directly from the PDF using pdfplumber for better accuracy.
"""

import pdfplumber
import csv
import re
from decimal import Decimal

class PDFTableExtractor:
    def __init__(self, pdf_path="data/FedEx_Standard_List_Rates_2025.pdf"):
        self.pdf_path = pdf_path
        self.extracted_data = []
        self.row_counter = 1

    def extract_tables_from_pdf(self):
        """Extract all tables from PDF"""
        print(f"Opening PDF: {self.pdf_path}")

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                print(f"PDF has {len(pdf.pages)} pages")

                for page_num, page in enumerate(pdf.pages):
                    print(f"\n=== Processing Page {page_num + 1} ===")

                    # Extract text to identify services and zones
                    page_text = page.extract_text()
                    if page_text:
                        services, zones = self.analyze_page_content(page_text)
                        print(f"Page {page_num + 1} - Services: {services}, Zones: {zones}")

                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        print(f"Found {len(tables)} tables on page {page_num + 1}")

                        for table_num, table in enumerate(tables):
                            print(f"  Table {table_num + 1}: {len(table)} rows x {len(table[0]) if table else 0} cols")

                            self.process_table(table, page_num + 1, services, zones)
                    else:
                        print(f"No tables found on page {page_num + 1}")

        except Exception as e:
            print(f"Error processing PDF: {e}")

    def analyze_page_content(self, text):
        """Analyze page text to identify services and zones"""
        services = []
        zones = []

        if text:
            text_lower = text.lower()

            # Service detection
            service_patterns = {
                'first_overnight': ['first overnight'],
                'priority_overnight': ['priority overnight'],
                'standard_overnight': ['standard overnight'],
                '2day_am': ['2day a.m', '2day®a.m'],
                '2day': ['2day'],
                'express_saver': ['express saver'],
                'ground': ['ground'],
                'home_delivery': ['home delivery']
            }

            for service_code, patterns in service_patterns.items():
                for pattern in patterns:
                    if pattern in text_lower and service_code not in services:
                        services.append(service_code)

            # Zone detection
            zone_matches = re.findall(r'zone\s*(\d+)', text_lower)
            zones = [int(z) for z in zone_matches if 2 <= int(z) <= 8]

        return services, zones

    def process_table(self, table, page_num, services, zones):
        """Process a single table"""
        if not table or len(table) < 2:
            return

        # Analyze table structure
        headers = table[0] if table else []
        print(f"    Headers: {headers[:6]}...")  # Show first 6 headers

        # Look for pricing data in rows
        for row_idx, row in enumerate(table[1:], 1):  # Skip header
            if not row:
                continue

            # Clean row data
            cleaned_row = [str(cell).strip() if cell else '' for cell in row]

            # Try to extract weight and prices
            weight, prices = self.extract_weight_and_prices(cleaned_row)

            if weight and prices and len(prices) >= 4:
                # Create records
                packaging_types = ['FedEx Envelope', 'FedEx Pak', 'FedEx Box', 'FedEx Tube', 'Your Packaging']

                for service in services if services else ['ground']:  # Default service
                    for zone in zones if zones else [2]:  # Default zone
                        for i, price in enumerate(prices[:5]):  # Up to 5 packaging types
                            if i < len(packaging_types):
                                try:
                                    price_decimal = Decimal(str(price)).quantize(Decimal('0.01'))

                                    record = {
                                        'row_id': self.row_counter,
                                        'service': service,
                                        'zone': zone,
                                        'weight_lbs': weight,
                                        'packaging': packaging_types[i],
                                        'rate_usd': str(price_decimal),
                                        'page': f'pdf_page_{page_num}',
                                        'source_row': row_idx,
                                        'source_data': str(cleaned_row[:10]),  # First 10 cells for reference
                                        'extraction_method': 'pdfplumber'
                                    }

                                    self.extracted_data.append(record)
                                    self.row_counter += 1

                                except (ValueError, TypeError):
                                    continue

    def extract_weight_and_prices(self, row):
        """Extract weight and prices from a table row"""
        weight = None
        prices = []

        for cell in row:
            if not cell:
                continue

            # Look for weight (number at start, possibly with 'lbs')
            weight_match = re.match(r'^(\d+)(?:\s*lbs?\.?)?$', cell.strip())
            if weight_match and not weight:
                candidate_weight = int(weight_match.group(1))
                if 1 <= candidate_weight <= 150:
                    weight = candidate_weight

            # Look for prices (decimal numbers, possibly with $)
            price_match = re.match(r'^\$?(\d+\.\d{2})$', cell.strip())
            if price_match:
                price = float(price_match.group(1))
                if 5 <= price <= 2000:  # Reasonable price range
                    prices.append(price)

        return weight, prices

    def save_pdf_data(self, filename='fedex_pdf_extracted.csv'):
        """Save extracted PDF data"""
        if not self.extracted_data:
            print("No data extracted from PDF")
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['row_id', 'service', 'zone', 'weight_lbs', 'packaging', 'rate_usd', 'page', 'source_row', 'source_data', 'extraction_method']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.extracted_data:
                writer.writerow(row)

        print(f"\nPDF extraction saved to {filename}")
        print(f"Total records: {len(self.extracted_data)}")

        # Show breakdown
        services = {}
        for record in self.extracted_data:
            service = record['service']
            services[service] = services.get(service, 0) + 1

        print(f"\nService breakdown:")
        for service, count in services.items():
            print(f"  {service}: {count} records")

        # Show sample
        print(f"\nSample records:")
        for record in self.extracted_data[:5]:
            print(f"  Row {record['row_id']}: {record['service']} Z{record['zone']} {record['weight_lbs']}lb {record['packaging']} = ${record['rate_usd']}")

def main():
    print("PDF Table Extractor for FedEx Rates")
    print("=" * 40)

    extractor = PDFTableExtractor()
    extractor.extract_tables_from_pdf()
    extractor.save_pdf_data()

if __name__ == "__main__":
    main()