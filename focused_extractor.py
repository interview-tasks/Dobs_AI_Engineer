#!/usr/bin/env python3
"""
Focused Data Extractor with Row Tracking
Extracts FedEx data with proper row tracking for traceability.
"""

import csv
import re
from decimal import Decimal
from PIL import Image
import pytesseract
import os

class FocusedExtractor:
    def __init__(self, screenshots_dir="data/ss"):
        self.screenshots_dir = screenshots_dir
        self.extracted_data = []
        self.row_counter = 1

    def extract_from_image(self, image_path, page_name):
        """Extract text and parse table data from single image"""
        print(f"\n=== Processing {page_name} ===")

        try:
            # Extract text using OCR
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, config='--psm 6')

            # Parse the text
            lines = text.split('\n')
            current_service = None
            current_zone = None

            # Print raw OCR text for debugging
            print("Raw OCR text (first 10 lines):")
            for i, line in enumerate(lines[:10]):
                if line.strip():
                    print(f"  {i+1:2d}: {line.strip()}")

            # Process each line
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Detect zone
                zone_match = re.search(r'Zone\s*(\d+)', line)
                if zone_match:
                    current_zone = int(zone_match.group(1))
                    print(f"Found Zone: {current_zone}")

                # Detect service
                service_detected = self.detect_service(line)
                if service_detected:
                    current_service = service_detected
                    print(f"Found Service: {current_service}")

                # Look for price rows
                price_data = self.extract_price_row(line, current_service, current_zone, page_name, line_num)
                if price_data:
                    for data in price_data:
                        data['row_id'] = self.row_counter
                        data['source_line'] = line_num + 1
                        data['source_text'] = line[:100]  # First 100 chars for reference
                        self.extracted_data.append(data)
                        self.row_counter += 1

        except Exception as e:
            print(f"Error processing {image_path}: {e}")

    def detect_service(self, line):
        """Detect service type from line"""
        line_lower = line.lower()

        if 'first overnight' in line_lower:
            return 'first_overnight'
        elif 'priority overnight' in line_lower:
            return 'priority_overnight'
        elif 'standard overnight' in line_lower:
            return 'standard_overnight'
        elif '2day am' in line_lower or '2day®a.m' in line_lower:
            return '2day_am'
        elif '2day' in line_lower and 'am' not in line_lower:
            return '2day'
        elif 'express saver' in line_lower:
            return 'express_saver'
        elif 'ground' in line_lower and 'overnight' not in line_lower:
            return 'ground'
        elif 'home delivery' in line_lower:
            return 'home_delivery'

        return None

    def extract_price_row(self, line, service, zone, page, line_num):
        """Extract price data from a line"""
        if not service or not zone:
            return []

        # Look for patterns like: weight followed by multiple prices
        # Pattern 1: weight | price price price price price
        pattern1 = r'(\d+)\s*\|\s*([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match1 = re.search(pattern1, line)

        # Pattern 2: weight price price price price price (without |)
        pattern2 = r'^(\d+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match2 = re.search(pattern2, line)

        # Pattern 3: weight followed by $ prices
        pattern3 = r'(\d+)(?:lbs?\.)?\s*\|\s*\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)'
        match3 = re.search(pattern3, line)

        match = match1 or match2 or match3
        if not match:
            return []

        try:
            weight = int(match.group(1))
            if weight < 1 or weight > 150:
                return []

            prices = []
            for i in range(2, 7):  # Extract 5 prices
                price_str = match.group(i).replace(',', '').replace('$', '')
                price = float(price_str)
                if 5 <= price <= 2000:  # Reasonable range
                    prices.append(price)
                else:
                    return []  # Skip if any price is unreasonable

            if len(prices) != 5:
                return []

            packaging_types = ['FedEx Envelope', 'FedEx Pak', 'FedEx Box', 'FedEx Tube', 'Your Packaging']

            result = []
            for pkg_type, price in zip(packaging_types, prices):
                result.append({
                    'service': service,
                    'zone': zone,
                    'weight_lbs': weight,
                    'packaging': pkg_type,
                    'rate_usd': str(Decimal(str(price)).quantize(Decimal('0.01'))),
                    'page': page
                })

            print(f"  Extracted: {weight}lb {service} Z{zone} -> {len(result)} pricing rows")
            return result

        except Exception as e:
            return []

    def process_all_screenshots(self):
        """Process all screenshots"""
        if not os.path.exists(self.screenshots_dir):
            print(f"Directory not found: {self.screenshots_dir}")
            return

        files = sorted([f for f in os.listdir(self.screenshots_dir) if f.endswith('.png')])
        print(f"Found {len(files)} screenshot files")

        for filename in files:
            image_path = os.path.join(self.screenshots_dir, filename)
            page_name = filename.replace('.png', '')
            self.extract_from_image(image_path, page_name)

    def save_to_csv(self, filename='fedex_focused_extraction.csv'):
        """Save with row tracking"""
        if not self.extracted_data:
            print("No data to save")
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['row_id', 'service', 'zone', 'weight_lbs', 'packaging', 'rate_usd', 'page', 'source_line', 'source_text']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.extracted_data:
                writer.writerow(row)

        print(f"\nExtraction Summary:")
        print(f"Total rows extracted: {len(self.extracted_data)}")
        print(f"Data saved to: {filename}")

        # Print sample of what was extracted
        print(f"\nSample extracted data:")
        for i, row in enumerate(self.extracted_data[:5]):
            print(f"Row {row['row_id']}: {row['service']} Z{row['zone']} {row['weight_lbs']}lb {row['packaging']} = ${row['rate_usd']}")

def main():
    print("Focused FedEx Data Extractor with Row Tracking")
    print("=" * 50)

    extractor = FocusedExtractor()
    extractor.process_all_screenshots()
    extractor.save_to_csv()

if __name__ == "__main__":
    main()