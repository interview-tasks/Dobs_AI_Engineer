#!/usr/bin/env python3
"""
FedEx Rate Extractor to CSV
Extracts all Express and Ground service rates from FedEx 2025 PDF and saves as CSV
"""

import pdfplumber
import pandas as pd
import re
import sys
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

def extract_weight_ranges(weight_text: str) -> List[str]:
    """Extract individual weight ranges from multi-line weight cell"""
    if not weight_text:
        return []

    lines = [line.strip() for line in weight_text.split('\n') if line.strip()]
    weights = []

    for line in lines:
        if line and any(indicator in line.lower() for indicator in ['lb', 'oz']):
            weights.append(line)

    return weights if weights else [weight_text.strip()] if weight_text.strip() else []

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

        # Process Ground services (page 105)
        print("\nExtracting Ground Services...")
        if len(pdf.pages) >= 105:
            page = pdf.pages[104]  # Page 105 (0-indexed)
            tables = page.find_tables()

            print(f"Page 105: found {len(tables)} tables")

            for table_idx, table in enumerate(tables, 1):
                table_data = table.extract()
                if not table_data:
                    continue

                # Look for Ground rate matrix (zones A, C, D, etc.)
                all_text = ' '.join([str(cell) for row in table_data[:3] for cell in row if cell]).lower()
                if 'zones' in all_text and '$' in all_text:
                    df = process_ground_rate_table(table_data, 105, table_idx)
                    if not df.empty:
                        all_rates.append(df)

    return all_rates

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_fedex_rates_csv.py <pdf_path>")
        return 1

    pdf_path = sys.argv[1]
    output_path = "fedex_all_rates_2025.csv"

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

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())