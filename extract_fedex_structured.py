#!/usr/bin/env python3
"""
FedEx Rate Extractor with Structured Schema
Extracts rates using proper database schema with individual weight mapping
"""

import pdfplumber
import pandas as pd
import re
import sys
import os
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import math

def clean_rate_value(value: str) -> Optional[Decimal]:
    """Extract numeric rate value from cell text as Decimal"""
    if not value:
        return None

    # Remove dollar signs, commas, and extra spaces
    cleaned = re.sub(r'[$,\s]', '', str(value))

    # Extract first number found
    match = re.search(r'(\d+\.?\d*)', cleaned)
    if match:
        try:
            return Decimal(match.group(1))
        except:
            pass

    return None

def extract_individual_weights_from_cell(weight_text: str) -> List[int]:
    """Extract individual weight values from multi-line weight cell"""
    if not weight_text:
        return []

    weights = []
    # Split by newlines and process each line
    lines = [line.strip() for line in weight_text.split('\n') if line.strip()]

    for line in lines:
        # Extract all numbers from the line
        numbers = re.findall(r'\b(\d+)\b', line)
        for num_str in numbers:
            try:
                weight = int(num_str)
                if 1 <= weight <= 2000:  # Reasonable weight range
                    weights.append(weight)
            except:
                continue

    return weights

def canonicalize_service_name(service_name: str) -> str:
    """Convert service name to canonical form"""
    if not service_name:
        return "UNKNOWN"

    # Clean and normalize the service name
    service_name = re.sub(r'\s+', ' ', service_name.replace('\n', ' ')).upper().strip()

    # Mapping to canonical service names
    if "FIRST OVERNIGHT" in service_name:
        return "FIRST_OVERNIGHT"
    elif "PRIORITY OVERNIGHT" in service_name:
        return "PRIORITY_OVERNIGHT"
    elif "STANDARD OVERNIGHT" in service_name:
        return "STANDARD_OVERNIGHT"
    elif "2DAY A.M." in service_name or "2DAY® A.M." in service_name:
        return "2DAY_AM"
    elif "2DAY" in service_name and "A.M." not in service_name:
        return "2DAY"
    elif "EXPRESS SAVER" in service_name:
        return "EXPRESS_SAVER"
    elif "GROUND" in service_name or "HOME DELIVERY" in service_name:
        return "GROUND"
    elif "ENVELOPE" in service_name:
        return "ENVELOPE"
    else:
        # Clean up the name for unknown services
        clean_name = re.sub(r'[^\w\s]', '', service_name)
        return clean_name.replace(' ', '_')

def determine_section(page_num: int, service_name: str, package_type: str) -> str:
    """Determine the section based on page number and service characteristics"""
    if 30 <= page_num <= 31:
        return "HAWAII_INTRA"
    elif page_num == 32:
        return "MULTIWEIGHT_BULK"
    elif page_num == 33:
        return "MULTIWEIGHT_EXPRESS"
    elif 105 <= page_num <= 111:
        return "GROUND"
    elif 2 <= page_num <= 21:
        return "US_PACKAGE"
    else:
        return "OTHER"

def extract_express_table_structured(table_data: List[List], page_num: int, table_num: int, zone: str) -> List[Dict]:
    """Extract Express service rates using structured schema"""

    if not table_data or len(table_data) < 3:
        return []

    results = []
    id_counter = 1

    # Find service header row
    service_row_idx = None
    services = []

    for i, row in enumerate(table_data):
        if row and any(cell and 'fedex' in str(cell).lower() for cell in row):
            service_row_idx = i
            # Extract services
            for col_idx, cell in enumerate(row):
                if cell and 'FedEx' in str(cell):
                    service_name = str(cell).strip()
                    canonical_service = canonicalize_service_name(service_name)
                    services.append((col_idx, canonical_service, service_name))
            break

    if not services:
        return []

    section = determine_section(page_num, "", "")

    # Process data rows
    for row_idx in range(service_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        # Get weight cell content
        weight_cell = str(row[0]) if row[0] else ""
        if not weight_cell.strip():
            continue

        # Handle envelope/pak special cases
        if 'envelope' in weight_cell.lower():
            # Envelope is typically 8 oz = 0.5 lb, round up to 1 lb
            individual_weights = [1]
            original_weight_text = weight_cell
        elif 'pak' in weight_cell.lower():
            # Pak is also lightweight, round up to 1 lb
            individual_weights = [1]
            original_weight_text = weight_cell
        else:
            # Extract individual weights from the cell
            individual_weights = extract_individual_weights_from_cell(weight_cell)
            original_weight_text = weight_cell

        # Process each service column
        for col_idx, canonical_service, original_service_name in services:
            if col_idx >= len(row) or not row[col_idx]:
                continue

            rate_cell = str(row[col_idx])

            # Skip asterisks
            if rate_cell.strip() == '*':
                continue

            # Extract rates from multi-line cell
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            if individual_weights and rates:
                # Map each weight to corresponding rate
                for i in range(min(len(individual_weights), len(rates))):
                    weight_lb = individual_weights[i]
                    base_rate = rates[i]

                    # Clean text content for CSV
                    clean_weight_text = re.sub(r'\s+', ' ', original_weight_text.replace('\n', ' ')).strip()
                    clean_rate_text = re.sub(r'\s+', ' ', rate_cell.replace('\n', ' ')).strip()
                    clean_service_text = re.sub(r'\s+', ' ', original_service_name.replace('\n', ' ')).strip()

                    results.append({
                        'id': id_counter,
                        'service': canonical_service,
                        'section': section,
                        'zone': zone,
                        'weight_lb': weight_lb,
                        'base_rate': base_rate,
                        'rate_type': 'per_package',
                        'pdf_page': page_num,
                        'table_index': table_num,
                        'row_id': row_idx,
                        'col_id': col_idx,
                        'original_cell_text': f"Weight: '{clean_weight_text}' | Rate: '{clean_rate_text}'",
                        'notes': f"Original service: {clean_service_text}"
                    })
                    id_counter += 1

            # If no weights extracted but we have rates, infer sequential weights
            elif rates and not individual_weights:
                # For corrupted weight cells, start from reasonable base
                base_weight = 1 if row_idx <= service_row_idx + 2 else (row_idx - service_row_idx - 2) * 5 + 1

                for i, rate in enumerate(rates):
                    weight_lb = base_weight + i

                    # Clean text content for CSV
                    clean_weight_text = re.sub(r'\s+', ' ', original_weight_text.replace('\n', ' ')).strip()
                    clean_rate_text = re.sub(r'\s+', ' ', rate_cell.replace('\n', ' ')).strip()
                    clean_service_text = re.sub(r'\s+', ' ', original_service_name.replace('\n', ' ')).strip()

                    results.append({
                        'id': id_counter,
                        'service': canonical_service,
                        'section': section,
                        'zone': zone,
                        'weight_lb': weight_lb,
                        'base_rate': rate,
                        'rate_type': 'per_package',
                        'pdf_page': page_num,
                        'table_index': table_num,
                        'row_id': row_idx,
                        'col_id': col_idx,
                        'original_cell_text': f"Weight: '{clean_weight_text}' | Rate: '{clean_rate_text}'",
                        'notes': f"Inferred weight. Original service: {clean_service_text}"
                    })
                    id_counter += 1

    return results

def extract_ground_table_structured(table_data: List[List], page_num: int, table_num: int) -> List[Dict]:
    """Extract Ground service rates using structured schema"""

    if not table_data or len(table_data) < 3:
        return []

    results = []
    id_counter = 1

    # Find zone header row
    zone_row_idx = None
    zones = []

    for i, row in enumerate(table_data):
        if row and any(cell and str(cell).strip().isdigit() for cell in row):
            zone_row_idx = i
            # Extract zones
            for col_idx, cell in enumerate(row):
                if cell and str(cell).strip().isdigit():
                    zones.append((col_idx, str(cell).strip()))
            break

    if not zones:
        return []

    section = determine_section(page_num, "GROUND", "")

    # Process data rows after zone header
    for row_idx in range(zone_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        # Extract weight from first column
        weight_cell = str(row[0]) if row[0] else ""
        if not weight_cell.strip():
            continue

        # Extract individual weights
        individual_weights = extract_individual_weights_from_cell(weight_cell)

        # Process each zone column
        for col_idx, zone in zones:
            if col_idx >= len(row) or not row[col_idx]:
                continue

            rate_cell = str(row[col_idx])

            # Extract rates from multi-line cell
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            if individual_weights and rates:
                for i in range(min(len(individual_weights), len(rates))):
                    weight_lb = individual_weights[i]
                    base_rate = rates[i]

                    results.append({
                        'id': id_counter,
                        'service': 'GROUND',
                        'section': section,
                        'zone': zone,
                        'weight_lb': weight_lb,
                        'base_rate': base_rate,
                        'rate_type': 'per_package',
                        'pdf_page': page_num,
                        'table_index': table_num,
                        'row_id': row_idx,
                        'col_id': col_idx,
                        'original_cell_text': f"Weight: '{weight_cell}' | Rate: '{rate_cell}'",
                        'notes': f"Ground delivery zone {zone}"
                    })
                    id_counter += 1
            elif rates:
                # Single rate for multiple weights - use first weight if available
                weight_lb = individual_weights[0] if individual_weights else 51  # Default for Ground

                results.append({
                    'id': id_counter,
                    'service': 'GROUND',
                    'section': section,
                    'zone': zone,
                    'weight_lb': weight_lb,
                    'base_rate': rates[0],
                    'rate_type': 'per_package',
                    'pdf_page': page_num,
                    'table_index': table_num,
                    'row_id': row_idx,
                    'col_id': col_idx,
                    'original_cell_text': f"Weight: '{weight_cell}' | Rate: '{rate_cell}'",
                    'notes': f"Ground delivery zone {zone}"
                })
                id_counter += 1

    return results

def extract_multiweight_table_structured(table_data: List[List], page_num: int, table_num: int, zone: str) -> List[Dict]:
    """Extract Multiweight service rates using structured schema"""

    if not table_data or len(table_data) < 3:
        return []

    results = []
    id_counter = 1

    # Find service header row
    service_row_idx = None
    services = []

    for i, row in enumerate(table_data):
        if row and any(cell and 'fedex' in str(cell).lower() for cell in row):
            service_row_idx = i
            for col_idx, cell in enumerate(row):
                if cell and 'FedEx' in str(cell):
                    service_name = str(cell).strip()
                    canonical_service = canonicalize_service_name(service_name)
                    services.append((col_idx, canonical_service, service_name))
            break

    if not services:
        return []

    section = determine_section(page_num, "", "")

    # For multiweight, rates are typically per-lb for bulk shipping
    # Weight ranges are usually like "100-499 lbs", "500-999 lbs", etc.

    # Process data rows
    for row_idx in range(service_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        weight_cell = str(row[0]) if row[0] else ""
        if not weight_cell.strip():
            continue

        # For multiweight, extract weight ranges
        weight_ranges = []
        if "100" in weight_cell and "499" in weight_cell:
            weight_ranges = [100, 499]
        elif "500" in weight_cell and "999" in weight_cell:
            weight_ranges = [500, 999]
        elif "1000" in weight_cell or "1,000" in weight_cell:
            weight_ranges = [1000, 1999]
        elif "2000" in weight_cell or "2,000" in weight_cell:
            weight_ranges = [2000]
        else:
            # Extract any numbers we can find
            numbers = re.findall(r'(\d+)', weight_cell.replace(',', ''))
            weight_ranges = [int(n) for n in numbers if int(n) >= 100]

        # Process each service column
        for col_idx, canonical_service, original_service_name in services:
            if col_idx >= len(row) or not row[col_idx]:
                continue

            rate_cell = str(row[col_idx])

            # Extract rates
            rates = []
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # For multiweight, typically one rate per weight range
            if weight_ranges and rates:
                for i, weight_lb in enumerate(weight_ranges):
                    rate_idx = min(i, len(rates) - 1)
                    base_rate = rates[rate_idx]

                    results.append({
                        'id': id_counter,
                        'service': canonical_service,
                        'section': section,
                        'zone': zone,
                        'weight_lb': weight_lb,
                        'base_rate': base_rate,
                        'rate_type': 'per_lb',
                        'pdf_page': page_num,
                        'table_index': table_num,
                        'row_id': row_idx,
                        'col_id': col_idx,
                        'original_cell_text': f"Weight: '{weight_cell}' | Rate: '{rate_cell}'",
                        'notes': f"Multiweight rate. Original service: {original_service_name}"
                    })
                    id_counter += 1
            elif rates:
                # Default weight for multiweight if can't parse
                weight_lb = 100

                results.append({
                    'id': id_counter,
                    'service': canonical_service,
                    'section': section,
                    'zone': zone,
                    'weight_lb': weight_lb,
                    'base_rate': rates[0],
                    'rate_type': 'per_lb',
                    'pdf_page': page_num,
                    'table_index': table_num,
                    'row_id': row_idx,
                    'col_id': col_idx,
                    'original_cell_text': f"Weight: '{weight_cell}' | Rate: '{rate_cell}'",
                    'notes': f"Multiweight rate, default weight. Original service: {original_service_name}"
                })
                id_counter += 1

    return results

def extract_all_rates_structured(pdf_path: str) -> List[Dict]:
    """Extract all rates from PDF using structured schema"""

    all_records = []

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Processing PDF with {len(pdf.pages)} pages...")

        # Express Services (Pages 2-21)
        print("\nExtracting Express Services (Pages 2-21)...")
        for page_num in range(2, 22):
            if page_num > len(pdf.pages):
                break

            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()

            if tables:
                print(f"  Page {page_num}: {len(tables)} table(s)")

                # Determine zone from page number
                if page_num in [2, 3, 4]:
                    zone = "2"
                elif page_num in [5, 6, 7]:
                    zone = "3"
                elif page_num in [8, 9, 10]:
                    zone = "4"
                elif page_num in [11, 12, 13]:
                    zone = "5"
                elif page_num in [14, 15, 16]:
                    zone = "6"
                elif page_num in [17, 18, 19]:
                    zone = "7"
                elif page_num in [20, 21]:
                    zone = "8"
                else:
                    zone = "unknown"

                for table_idx, table_data in enumerate(tables):
                    records = extract_express_table_structured(table_data, page_num, table_idx, zone)
                    all_records.extend(records)
                    if records:
                        print(f"    Table {table_idx}: {len(records)} records")

        # Hawaii Intra (Pages 30-31)
        print("\nExtracting Hawaii Intra Services (Pages 30-31)...")
        for page_num in [30, 31]:
            if page_num > len(pdf.pages):
                continue

            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()

            if tables:
                print(f"  Page {page_num}: {len(tables)} table(s)")

                for table_idx, table_data in enumerate(tables):
                    records = extract_express_table_structured(table_data, page_num, table_idx, "HAWAII_INTRA")
                    all_records.extend(records)
                    if records:
                        print(f"    Table {table_idx}: {len(records)} records")

        # Multiweight Bulk (Page 32)
        print("\nExtracting Multiweight Bulk Services (Page 32)...")
        if 32 <= len(pdf.pages):
            page = pdf.pages[31]
            tables = page.extract_tables()

            if tables:
                print(f"  Page 32: {len(tables)} table(s)")

                for table_idx, table_data in enumerate(tables):
                    # Each table represents a different zone
                    zone_map = {0: "2", 1: "3", 2: "4", 3: "5", 4: "6", 5: "7"}
                    zone = zone_map.get(table_idx, str(table_idx + 2))

                    records = extract_multiweight_table_structured(table_data, 32, table_idx, zone)
                    all_records.extend(records)
                    if records:
                        print(f"    Table {table_idx} (Zone {zone}): {len(records)} records")

        # Express Multiweight (Page 33)
        print("\nExtracting Express Multiweight Services (Page 33)...")
        if 33 <= len(pdf.pages):
            page = pdf.pages[32]
            tables = page.extract_tables()

            if tables:
                print(f"  Page 33: {len(tables)} table(s)")

                for table_idx, table_data in enumerate(tables):
                    # Zone mapping for Express Multiweight
                    zone_map = {0: "2-3", 1: "4-5", 2: "6-7", 3: "8", 4: "EXPRESS_SPECIAL"}
                    zone = zone_map.get(table_idx, f"table_{table_idx}")

                    records = extract_multiweight_table_structured(table_data, 33, table_idx, zone)
                    all_records.extend(records)
                    if records:
                        print(f"    Table {table_idx} (Zone {zone}): {len(records)} records")

        # Ground Services (Pages 105-111)
        print("\nExtracting Ground Services (Pages 105-111)...")
        for page_num in range(105, 112):
            if page_num > len(pdf.pages):
                break

            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()

            if tables:
                print(f"  Page {page_num}: {len(tables)} table(s)")

                for table_idx, table_data in enumerate(tables):
                    records = extract_ground_table_structured(table_data, page_num, table_idx)
                    all_records.extend(records)
                    if records:
                        print(f"    Table {table_idx}: {len(records)} records")

    print(f"\nTotal records extracted: {len(all_records)}")
    return all_records

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_fedex_structured.py <pdf_path>")
        return 1

    pdf_filename = sys.argv[1]

    # Look for PDF in data folder first, then current directory
    if os.path.exists(f"data/{pdf_filename}"):
        pdf_path = f"data/{pdf_filename}"
    elif os.path.exists(pdf_filename):
        pdf_path = pdf_filename
    else:
        print(f"Error: PDF file not found in data/ or current directory: {pdf_filename}")
        return 1

    print(f"Extracting structured FedEx rates from: {pdf_path}")

    try:
        # Extract all rates
        all_records = extract_all_rates_structured(pdf_path)

        if not all_records:
            print("No records extracted!")
            return 1

        # Convert to DataFrame
        df = pd.DataFrame(all_records)

        # Save to CSV
        output_path = "data/fedex_rates_structured.csv"
        df.to_csv(output_path, index=False)

        print(f"\nExtraction completed!")
        print(f"Saved {len(df)} records to: {output_path}")

        # Show summary
        print("\nSummary by section:")
        print(df.groupby('section').size())

        print("\nSummary by service:")
        print(df.groupby('service').size())

        print("\nSample records:")
        print(df.head(10))

    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())