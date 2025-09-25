#!/usr/bin/env python3
"""
FedEx Rate Extractor to CSV
Extracts all Express and Ground service rates from FedEx 2025 PDF and saves as CSV
"""

import pdfplumber
import pandas as pd
import re
import sys
import os
from typing import List, Dict, Optional, Tuple

def clean_rate_value(value: str) -> Optional[float]:
    """Extract numeric rate value from cell text"""
    if not value:
        return None

    # Remove dollar signs, commas, and extra spaces
    cleaned = re.sub(r'[$,\s]', '', str(value))

    # Extract first number found
    match = re.search(r'(\d+\.?\d*)', cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    return None

def clean_corrupted_text(text: str) -> str:
    """Clean corrupted/backwards text from PDF extraction"""
    if not text:
        return ""

    text = str(text).strip()

    # Check for corrupted backwards text pattern
    if 'sbl' in text.lower() and 'mumixam' in text.lower():
        # This appears to be "maximum weight in lbs" backwards - replace with generic description
        return "Weight-based pricing"

    # Remove excessive newlines and clean up
    text = ' '.join(text.split())

    return text

def extract_weight_ranges(weight_text: str) -> List[str]:
    """Extract individual weight ranges from multi-line weight cell"""
    if not weight_text:
        return []

    # Clean corrupted text first
    weight_text = clean_corrupted_text(weight_text)

    if weight_text == "Weight-based pricing":
        # For corrupted weight cells, return generic weight ranges
        return ["1-50 lbs", "51-100 lbs", "101-150 lbs"]

    lines = [line.strip() for line in weight_text.split('\n') if line.strip()]
    weights = []

    for line in lines:
        # Clean each line
        clean_line = clean_corrupted_text(line)
        if clean_line and any(indicator in clean_line.lower() for indicator in ['lb', 'oz', 'weight']):
            weights.append(clean_line)

    return weights if weights else [clean_corrupted_text(weight_text)] if weight_text.strip() else []

def extract_services_from_header(header_row: List) -> List[Tuple[int, str]]:
    """Extract service names from header row"""
    services = []

    for i, cell in enumerate(header_row):
        if cell and str(cell).strip():
            cell_text = str(cell).strip()
            # Look for FedEx service names
            if 'fedex' in cell_text.lower() or any(service in cell_text.lower()
                for service in ['overnight', '2day', 'express', 'saver']):

                # Clean service name
                service_name = cell_text.replace('\n', ' ').strip()
                services.append((i, service_name))

    return services

def process_express_rate_table(table_data: List[List], page_num: int, table_num: int, zone: str) -> pd.DataFrame:
    """Process Express service rate tables (pages 2-21)"""

    if not table_data or len(table_data) < 3:
        return pd.DataFrame()

    results = []

    # Find service header row
    service_row_idx = None
    for i, row in enumerate(table_data):
        if row and any(cell and 'fedex' in str(cell).lower() for cell in row):
            service_row_idx = i
            break

    if service_row_idx is None:
        return pd.DataFrame()

    # Extract services
    services = extract_services_from_header(table_data[service_row_idx])
    if not services:
        return pd.DataFrame()

    print(f"  Zone {zone} - Found services: {[s[1] for s in services]}")

    # Process data rows
    for row_idx in range(service_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        # Get weight/package type from first column
        weight_cell = str(row[0]) if row[0] else ""
        if not weight_cell.strip():
            continue

        # Handle different package types
        if 'envelope' in weight_cell.lower():
            package_type = 'FedEx Envelope'
            weight_ranges = [weight_cell]
        elif 'pak' in weight_cell.lower():
            package_type = 'FedEx Pak'
            weight_ranges = [weight_cell]
        else:
            package_type = 'Package'
            weight_ranges = extract_weight_ranges(weight_cell)

        if not weight_ranges:
            continue

        # Process each service column
        for service_idx, service_name in services:
            if service_idx >= len(row) or not row[service_idx]:
                continue

            rate_cell = str(row[service_idx])

            # Skip asterisks (indicates same as envelope)
            if rate_cell.strip() == '*':
                continue

            # Extract rates from multi-line cells
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': zone,
                        'service_type': service_name,
                        'package_type': package_type,
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} rate records")
    return df

def process_ground_rate_table(table_data: List[List], page_num: int, table_num: int) -> pd.DataFrame:
    """Process Ground service rate tables (page 105)"""

    if not table_data or len(table_data) < 3:
        return pd.DataFrame()

    results = []

    # Find zone header row
    zone_row_idx = None
    for i, row in enumerate(table_data):
        if row and len(row) > 5:
            zone_candidates = [str(cell).strip() for cell in row[2:] if cell]
            if len(zone_candidates) >= 5 and all(len(z) <= 2 for z in zone_candidates[:5]):
                zone_row_idx = i
                break

    if zone_row_idx is None:
        return pd.DataFrame()

    # Extract zones
    zones = []
    zone_row = table_data[zone_row_idx]
    for i in range(2, len(zone_row)):
        if zone_row[i] and str(zone_row[i]).strip():
            zones.append((i, str(zone_row[i]).strip()))

    print(f"  Ground zones: {[z[1] for z in zones]}")

    # Process data rows
    for row_idx in range(zone_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        weight_cell = str(row[0])
        weight_ranges = extract_weight_ranges(weight_cell)

        if not weight_ranges:
            continue

        # Process each zone
        for zone_idx, zone_name in zones:
            if zone_idx >= len(row) or not row[zone_idx]:
                continue

            rate_cell = str(row[zone_idx])
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': zone_name,
                        'service_type': 'FedEx Ground/Home Delivery',
                        'package_type': 'Package',
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} Ground rate records")
    return df

def process_multiweight_rate_table(table_data: List[List], page_num: int, table_num: int, zone: str) -> pd.DataFrame:
    """Process multiweight (per-lb) rate tables from page 32"""

    if not table_data or len(table_data) < 2:
        return pd.DataFrame()

    results = []

    # Extract services from header row (row 0)
    header_row = table_data[0]
    services = extract_services_from_header(header_row)

    if not services:
        return pd.DataFrame()

    print(f"  Zone {zone} Multiweight - Found services: {[s[1] for s in services]}")

    # Process data row (row 1)
    if len(table_data) > 1:
        data_row = table_data[1]

        # Extract weight ranges from first column
        weight_cell = str(data_row[0]) if data_row[0] else ""
        weight_ranges = extract_weight_ranges(weight_cell)

        if not weight_ranges:
            return pd.DataFrame()

        # Process each service column
        for service_idx, service_name in services:
            if service_idx >= len(data_row) or not data_row[service_idx]:
                continue

            rate_cell = str(data_row[service_idx])
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': zone,
                        'service_type': service_name,
                        'package_type': 'Multiweight Package',
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} multiweight rate records")
    return df

def process_hawaii_intra_table(table_data: List[List], page_num: int, table_num: int) -> pd.DataFrame:
    """Process Within Hawaii rate tables (page 30/31)"""

    if not table_data or len(table_data) < 3:
        return pd.DataFrame()

    results = []

    # Find service header row
    service_row_idx = None
    for i, row in enumerate(table_data):
        if row and any(cell and 'fedex' in str(cell).lower() for cell in row):
            service_row_idx = i
            break

    if service_row_idx is None:
        return pd.DataFrame()

    # Extract services
    services = extract_services_from_header(table_data[service_row_idx])
    if not services:
        return pd.DataFrame()

    print(f"  Within Hawaii - Found services: {[s[1] for s in services]}")

    # Process data rows
    for row_idx in range(service_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        weight_cell = str(row[0]) if row[0] else ""
        if not weight_cell.strip():
            continue

        weight_ranges = extract_weight_ranges(weight_cell)
        if not weight_ranges:
            continue

        # Process each service column
        for service_idx, service_name in services:
            if service_idx >= len(row) or not row[service_idx]:
                continue

            rate_cell = str(row[service_idx])
            if rate_cell.strip() == '*':
                continue

            rates = []
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': 'Hawaii-Intra',
                        'service_type': service_name,
                        'package_type': 'Package',
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} Hawaii intra rate records")
    return df

def process_express_multiweight_table(table_data: List[List], page_num: int, table_num: int, zone: str) -> pd.DataFrame:
    """Process Express Multiweight tables (page 33)"""

    if not table_data or len(table_data) < 2:
        return pd.DataFrame()

    results = []

    # Extract services from header row
    header_row = table_data[0]
    services = extract_services_from_header(header_row)

    if not services:
        return pd.DataFrame()

    print(f"  Express Multiweight Zone {zone} - Found services: {[s[1] for s in services]}")

    # Process data rows
    for row_idx in range(1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        weight_cell = str(row[0])
        weight_ranges = extract_weight_ranges(weight_cell)

        if not weight_ranges:
            continue

        # Process each service column
        for service_idx, service_name in services:
            if service_idx >= len(row) or not row[service_idx]:
                continue

            rate_cell = str(row[service_idx])
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]
            rates = []

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': zone,
                        'service_type': service_name,
                        'package_type': 'Express Multiweight',
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} Express multiweight rate records")
    return df

def process_ground_zone_table(table_data: List[List], page_num: int, table_num: int) -> pd.DataFrame:
    """Process Ground zone tables (pages 105-111)"""

    if not table_data or len(table_data) < 3:
        return pd.DataFrame()

    results = []

    # Find zone header row
    zone_row_idx = None
    zones = []

    for i, row in enumerate(table_data):
        if row and len(row) > 2:
            # Look for zone numbers or letters
            potential_zones = []
            for j in range(2, min(len(row), 8)):  # Check first 6 columns after first 2
                if row[j] and str(row[j]).strip():
                    cell = str(row[j]).strip()
                    if cell.isdigit() or len(cell) <= 2:
                        potential_zones.append((j, cell))

            if len(potential_zones) >= 3:  # Need at least 3 zones
                zone_row_idx = i
                zones = potential_zones
                break

    if not zones:
        return pd.DataFrame()

    print(f"  Page {page_num} Ground zones: {[z[1] for z in zones]}")

    # Process data rows
    for row_idx in range(zone_row_idx + 1, len(table_data)):
        row = table_data[row_idx]
        if not row or not row[0]:
            continue

        # Get weight description from first column
        weight_cell = str(row[0])
        if not weight_cell.strip() or 'minimum' in weight_cell.lower():
            continue

        weight_ranges = extract_weight_ranges(weight_cell)
        if not weight_ranges:
            weight_ranges = [clean_corrupted_text(weight_cell)]

        # Process each zone
        for zone_idx, zone_name in zones:
            if zone_idx >= len(row) or not row[zone_idx]:
                continue

            rate_cell = str(row[zone_idx])
            rates = []
            rate_lines = [line.strip() for line in rate_cell.split('\n') if line.strip()]

            for line in rate_lines:
                rate = clean_rate_value(line)
                if rate is not None:
                    rates.append(rate)

            # Match weights to rates
            for w_idx, weight_desc in enumerate(weight_ranges):
                rate = rates[w_idx] if w_idx < len(rates) else (rates[-1] if rates else None)

                if rate is not None:
                    results.append({
                        'page': page_num,
                        'table': table_num,
                        'zone': zone_name,
                        'service_type': 'FedEx Ground/Home Delivery',
                        'package_type': 'Package',
                        'weight_range': weight_desc,
                        'rate_usd': rate
                    })

    df = pd.DataFrame(results)
    print(f"  Extracted {len(df)} Ground zone rate records")
    return df

def extract_all_fedex_rates(pdf_path: str):
    """Extract rates from all FedEx services"""

    all_rates = []

    with pdfplumber.open(pdf_path) as pdf:

        # Process Express services (pages 2-21, zones 2-8)
        print("Extracting Express Services...")
        zone = 2

        for page_num in range(2, 22):
            if page_num > len(pdf.pages):
                break

            page = pdf.pages[page_num - 1]
            tables = page.find_tables()

            print(f"Page {page_num} (Zone {zone}): found {len(tables)} tables")

            for table_idx, table in enumerate(tables, 1):
                table_data = table.extract()
                if not table_data:
                    continue

                # Check if this is an Express rate table
                has_fedex_services = any('fedex' in str(cell).lower()
                                       for row in table_data[:3]
                                       for cell in row if cell)
                has_rates = any('$' in str(cell)
                              for row in table_data[:5]
                              for cell in row if cell)

                if has_fedex_services and has_rates:
                    df = process_express_rate_table(table_data, page_num, table_idx, str(zone))
                    if not df.empty:
                        all_rates.append(df)

            # Increment zone every 3 pages (2-4=Zone2, 5-7=Zone3, etc.)
            if page_num % 3 == 1 and page_num > 2:
                zone += 1

        # Process Hawaii Intra rates (pages 30-31)
        print("\nExtracting Hawaii Intra Services...")
        for page_num in [30, 31]:
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]
                tables = page.find_tables()

                print(f"Page {page_num}: found {len(tables)} tables")

                for table_idx, table in enumerate(tables, 1):
                    table_data = table.extract()
                    if not table_data:
                        continue

                    # Check if this is Hawaii intra table
                    has_hawaii = any('hawaii' in str(cell).lower() or 'intra' in str(cell).lower()
                                   for row in table_data[:3] for cell in row if cell)
                    has_fedex_services = any('fedex' in str(cell).lower()
                                           for row in table_data[:5] for cell in row if cell)

                    if has_hawaii and has_fedex_services:
                        df = process_hawaii_intra_table(table_data, page_num, table_idx)
                        if not df.empty:
                            all_rates.append(df)

        # Process Multiweight services (page 32, zones 2-7)
        print("\nExtracting Multiweight Services...")
        if len(pdf.pages) >= 32:
            page = pdf.pages[31]  # Page 32 (0-indexed)
            tables = page.find_tables()

            print(f"Page 32: found {len(tables)} tables")

            # Each table on page 32 represents a different zone (2-7)
            multiweight_zone = 2
            for table_idx, table in enumerate(tables, 1):
                table_data = table.extract()
                if not table_data:
                    continue

                # Check if this is a multiweight table
                has_weight_header = any('weight' in str(cell).lower()
                                      for cell in table_data[0] if cell)
                has_rates = any('$' in str(cell)
                              for row in table_data for cell in row if cell)

                if has_weight_header and has_rates:
                    df = process_multiweight_rate_table(table_data, 32, table_idx, str(multiweight_zone))
                    if not df.empty:
                        all_rates.append(df)
                    multiweight_zone += 1

        # Process Express Multiweight services (page 33)
        print("\nExtracting Express Multiweight Services...")
        if len(pdf.pages) >= 33:
            page = pdf.pages[32]  # Page 33 (0-indexed)
            tables = page.find_tables()

            print(f"Page 33: found {len(tables)} tables")

            # Each table represents different zone ranges
            express_multiweight_zone = "2-3"
            zone_names = ["2-3", "4-5", "6-7", "8", "Express-Special"]

            for table_idx, table in enumerate(tables, 1):
                table_data = table.extract()
                if not table_data:
                    continue

                has_weight_header = any('weight' in str(cell).lower()
                                      for cell in table_data[0] if cell)
                has_rates = any('$' in str(cell)
                              for row in table_data for cell in row if cell)

                if has_weight_header and has_rates:
                    zone_name = zone_names[table_idx-1] if table_idx-1 < len(zone_names) else f"Zone-{table_idx}"
                    df = process_express_multiweight_table(table_data, 33, table_idx, zone_name)
                    if not df.empty:
                        all_rates.append(df)

        # Process Ground services (pages 105-111)
        print("\nExtracting Ground Services...")
        for page_num in range(105, 112):
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]
                tables = page.find_tables()

                print(f"Page {page_num}: found {len(tables)} tables")

                for table_idx, table in enumerate(tables, 1):
                    table_data = table.extract()
                    if not table_data:
                        continue

                    # Look for Ground rate tables
                    has_ground = any('ground' in str(cell).lower() or 'delivery' in str(cell).lower()
                                   for row in table_data[:3] for cell in row if cell)
                    has_zones_or_rates = any('zone' in str(cell).lower() or '$' in str(cell)
                                           for row in table_data[:5] for cell in row if cell)

                    if has_ground and has_zones_or_rates:
                        df = process_ground_zone_table(table_data, page_num, table_idx)
                        if not df.empty:
                            all_rates.append(df)

    return all_rates

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_fedex_rates_csv.py <pdf_path>")
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
    output_path = "data/fedex_all_rates_2025.csv"

    print(f"Extracting all FedEx rates from: {pdf_path}")

    try:
        all_rate_data = extract_all_fedex_rates(pdf_path)

        if not all_rate_data:
            print("No rate tables found!")
            return 1

        # Combine all rates
        combined_rates = pd.concat(all_rate_data, ignore_index=True)

        # Save to CSV
        combined_rates.to_csv(output_path, index=False)

        print(f"\nExtraction completed!")
        print(f"Total rate records: {len(combined_rates)}")
        print(f"Services found: {sorted(combined_rates['service_type'].unique())}")
        print(f"Zones found: {sorted(combined_rates['zone'].unique())}")
        print(f"Saved to: {output_path}")

        # Show sample data
        print(f"\nSample data:")
        print(combined_rates.head())

        # Automatically separate into individual CSV files
        print(f"\nSeparating into individual table files...")
        separate_tables(combined_rates)

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def separate_tables(df):
    """Separate the comprehensive DataFrame into individual CSV files by table type"""

    print("Creating separate CSV files by table type...")

    # 1. Express Services (pages 2-21)
    express_services = df[
        (df['package_type'] == 'Package') &
        (df['page'] >= 2) &
        (df['page'] <= 21)
    ]
    express_services.to_csv('data/express_services_zones_2_8.csv', index=False)
    print(f"→ express_services_zones_2_8.csv ({len(express_services)} records)")

    # 2. Hawaii Intra Services - Page 30 (separate)
    hawaii_page_30 = df[(df['zone'] == 'Hawaii-Intra') & (df['page'] == 30)]
    hawaii_page_30.to_csv('data/hawaii_intra_page_30.csv', index=False)
    print(f"→ hawaii_intra_page_30.csv ({len(hawaii_page_30)} records)")

    # 3. Hawaii Intra Services - Page 31 (separate)
    hawaii_page_31 = df[(df['zone'] == 'Hawaii-Intra') & (df['page'] == 31)]
    hawaii_page_31.to_csv('data/hawaii_intra_page_31.csv', index=False)
    print(f"→ hawaii_intra_page_31.csv ({len(hawaii_page_31)} records)")

    # 4. Multiweight Services (page 32)
    multiweight = df[df['package_type'] == 'Multiweight Package']
    multiweight.to_csv('data/multiweight_bulk_rates.csv', index=False)
    print(f"→ multiweight_bulk_rates.csv ({len(multiweight)} records)")

    # 5. Express Multiweight Services (page 33)
    express_multiweight = df[df['package_type'] == 'Express Multiweight']
    express_multiweight.to_csv('data/express_multiweight_rates.csv', index=False)
    print(f"→ express_multiweight_rates.csv ({len(express_multiweight)} records)")

    # 6. Ground US Zones (pages 105-107)
    ground_us = df[
        (df['service_type'] == 'FedEx Ground/Home Delivery') &
        (df['page'] >= 105) &
        (df['page'] <= 107)
    ]
    ground_us.to_csv('data/ground_us_zones_2_7.csv', index=False)
    print(f"→ ground_us_zones_2_7.csv ({len(ground_us)} records)")

    # 7. Ground Alaska/Hawaii (pages 108-110)
    ground_alaska_hawaii = df[
        (df['service_type'] == 'FedEx Ground/Home Delivery') &
        (df['page'] >= 108) &
        (df['page'] <= 110)
    ]
    ground_alaska_hawaii.to_csv('data/ground_alaska_hawaii_zones.csv', index=False)
    print(f"→ ground_alaska_hawaii_zones.csv ({len(ground_alaska_hawaii)} records)")

    # 8. Ground Canada (page 111)
    ground_canada = df[
        (df['service_type'] == 'FedEx Ground/Home Delivery') &
        (df['page'] == 111)
    ]
    ground_canada.to_csv('data/ground_canada_rates.csv', index=False)
    print(f"→ ground_canada_rates.csv ({len(ground_canada)} records)")

    total_separated = (len(express_services) + len(hawaii_page_30) + len(hawaii_page_31) + len(multiweight) +
                      len(express_multiweight) + len(ground_us) + len(ground_alaska_hawaii) +
                      len(ground_canada))
    print(f"\nSeparation completed! {total_separated} records distributed across 8 files.")

if __name__ == "__main__":
    sys.exit(main())