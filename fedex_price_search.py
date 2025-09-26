#!/usr/bin/env python3
"""
FedEx Price Search Tool
Complete working solution for searching FedEx rates from PDF data.
Uses LLM for input normalization as suggested in requirements.
"""

import csv
import re
import math
import argparse
import json
import os
from decimal import Decimal
from typing import Optional, Dict, List
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

class FedExPriceSearch:
    def __init__(self, csv_file: str = 'fedex_pdf_extracted.csv'):
        self.csv_file = csv_file
        self.rates_data = []
        self.load_rates()

        # Initialize OpenAI client
        self.openai_client = None
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and api_key != 'your_openai_api_key_here':
            self.openai_client = OpenAI(api_key=api_key)
            print("✅ OpenAI LLM enabled for input parsing")
        else:
            print("⚠️  OpenAI API key not found - using regex parsing fallback")

        # Service name mappings for synonyms (fallback if LLM not available)
        self.service_synonyms = {
            'first overnight': 'first_overnight',
            'priority overnight': 'priority_overnight',
            'standard overnight': 'standard_overnight',
            '2day': '2day',
            '2 day': '2day',
            'fedex 2day': '2day',
            '2day am': '2day_am',
            '2 day am': '2day_am',
            'fedex 2day am': '2day_am',
            'express saver': 'express_saver',
            'ground': 'ground',
            'fedex ground': 'ground',
            'home delivery': 'home_delivery',
            'fedex home delivery': 'home_delivery'
        }

    def load_rates(self):
        """Load rate data from CSV file"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.rates_data = [row for row in reader]
            print(f"Loaded {len(self.rates_data)} rate records")

            # Show available services
            services = set(row['service'] for row in self.rates_data)
            print(f"Available services: {sorted(services)}")

            # Show available zones
            zones = set(int(row['zone']) for row in self.rates_data)
            print(f"Available zones: {sorted(zones)}")

        except FileNotFoundError:
            print(f"CSV file {self.csv_file} not found. Please run the PDF extractor first.")
            self.rates_data = []

    def parse_input_with_llm(self, line: str) -> Dict[str, any]:
        """Use LLM to parse and normalize input as suggested in requirements"""
        if not self.openai_client:
            return self.parse_input_regex(line)

        try:
            print(f"🤖 Using OpenAI GPT-3.5-turbo to parse: '{line}'")
            prompt = f"""
            Parse this FedEx shipping query and extract the structured information in JSON format.

            Input: "{line}"

            Extract:
            - service: one of [first_overnight, priority_overnight, standard_overnight, 2day, 2day_am, express_saver, ground, home_delivery]
            - zone: number between 2-8
            - weight_lbs: weight in pounds (round UP to next whole number)
            - packaging: one of [FedEx Envelope, FedEx Pak, FedEx Box, FedEx Tube, Your Packaging]

            Service synonyms:
            - First Overnight, Priority Overnight, Standard Overnight
            - 2Day, 2Day AM, Express Saver, Ground, Home Delivery
            - "2Day" refers to 2day service, "2Day AM" refers to 2day_am

            Zone formats: Z5, Zone 5, z2, 5 (extract the number)
            Weight formats: 3 lb, 10 lbs, 5lb (round up: 3.2 lb -> 4)
            Default packaging: "Your Packaging" if not specified

            Return only valid JSON:
            {{"service": "service_name", "zone": number, "weight_lbs": number, "packaging": "packaging_type"}}
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            parsed = json.loads(response.choices[0].message.content)
            print(f"✅ LLM parsed successfully: {parsed}")

            # Validate parsed data
            if (parsed.get('service') and
                parsed.get('zone') and isinstance(parsed['zone'], int) and 2 <= parsed['zone'] <= 8 and
                parsed.get('weight_lbs') and isinstance(parsed['weight_lbs'], (int, float))):

                return {
                    'service': parsed['service'],
                    'zone': int(parsed['zone']),
                    'weight_lbs': int(math.ceil(parsed['weight_lbs'])),
                    'packaging': parsed.get('packaging', 'Your Packaging')
                }

        except Exception as e:
            print(f"LLM parsing failed ({e}), falling back to regex")

        return self.parse_input_regex(line)

    def parse_input_regex(self, line: str) -> Dict[str, any]:
        """Fallback regex-based parsing"""
        line = line.lower().strip()

        result = {
            'service': None,
            'zone': None,
            'weight_lbs': None,
            'packaging': 'Your Packaging'  # Default packaging
        }

        # Extract zone (Z5, Zone 5, z2, 5, etc.)
        zone_patterns = [
            r'z(?:one)?\s*(\d+)',
            r'zone\s*(\d+)',
            r'(?:^|\s)(\d+)(?:\s|$)'
        ]

        for pattern in zone_patterns:
            match = re.search(pattern, line)
            if match:
                zone = int(match.group(1))
                if 2 <= zone <= 8:  # Valid FedEx zones
                    result['zone'] = zone
                    break

        # Extract weight (3 lb, 10 lbs, 5lb, etc.)
        weight_patterns = [
            r'(\d+(?:\.\d+)?)\s*lbs?',
            r'(\d+(?:\.\d+)?)\s*pounds?'
        ]

        for pattern in weight_patterns:
            match = re.search(pattern, line)
            if match:
                weight = float(match.group(1))
                result['weight_lbs'] = math.ceil(weight)  # Round up as required
                break

        # Extract service type
        for synonym, service_code in self.service_synonyms.items():
            if synonym in line:
                result['service'] = service_code
                break

        # Extract packaging type
        packaging_keywords = {
            'envelope': 'FedEx Envelope',
            'pak': 'FedEx Pak',
            'box': 'FedEx Box',
            'tube': 'FedEx Tube',
            'other packaging': 'Your Packaging',
            'your packaging': 'Your Packaging'
        }

        for keyword, packaging in packaging_keywords.items():
            if keyword in line:
                result['packaging'] = packaging
                break

        return result

    def parse_input(self, line: str) -> Dict[str, any]:
        """Main parsing function - uses LLM if available, falls back to regex"""
        return self.parse_input_with_llm(line)

    def get_price(self, line: str) -> Optional[Decimal]:
        """
        Main function: get_price(line: str) -> Decimal|float
        Takes free-form line and returns USD price
        """
        if not self.rates_data:
            print("No rate data available. Please run the PDF extractor first.")
            return None

        parsed = self.parse_input(line)

        # Validate required fields
        if not all([parsed['service'], parsed['zone'], parsed['weight_lbs']]):
            missing = [k for k, v in parsed.items() if v is None and k != 'packaging']
            print(f"Could not parse: {missing} from input: '{line}'")
            print(f"Parsed: service={parsed['service']}, zone={parsed['zone']}, weight={parsed['weight_lbs']}")
            return None

        # Search for exact match in rate data
        for rate_record in self.rates_data:
            if (rate_record['service'] == parsed['service'] and
                int(rate_record['zone']) == parsed['zone'] and
                int(rate_record['weight_lbs']) == parsed['weight_lbs'] and
                rate_record['packaging'] == parsed['packaging']):

                return Decimal(rate_record['rate_usd'])

        # If exact weight not found, try to find closest weight
        closest_match = self.find_closest_weight_match(parsed)
        if closest_match:
            return Decimal(closest_match['rate_usd'])

        print(f"No rate found for: service={parsed['service']}, zone={parsed['zone']}, "
              f"weight={parsed['weight_lbs']}lb, packaging={parsed['packaging']}")
        return None

    def find_closest_weight_match(self, parsed: Dict) -> Optional[Dict]:
        """Find closest weight match if exact weight not available"""
        matches = []

        for rate_record in self.rates_data:
            if (rate_record['service'] == parsed['service'] and
                int(rate_record['zone']) == parsed['zone'] and
                rate_record['packaging'] == parsed['packaging']):
                matches.append(rate_record)

        if not matches:
            return None

        # Find closest weight
        target_weight = parsed['weight_lbs']
        closest = min(matches, key=lambda x: abs(int(x['weight_lbs']) - target_weight))

        print(f"Using closest weight match: {closest['weight_lbs']}lb for requested {target_weight}lb")
        return closest

    def demo_search(self, test_lines: List[str]):
        """Demonstrate the search functionality with test lines"""
        print("\n" + "="*60)
        print("FEDEX PRICE LOOKUP DEMO")
        print("="*60)

        for i, line in enumerate(test_lines, 1):
            print(f"\n{i}. Input: '{line}'")
            parsed = self.parse_input(line)
            print(f"   Parsed: {parsed}")

            price = self.get_price(line)
            if price:
                print(f"   Result: ${price}")
            else:
                print(f"   Result: No price found")

def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(description='FedEx Price Search Tool')
    parser.add_argument('--demo', action='store_true', help='Run demo with test cases')
    parser.add_argument('--line', type=str, help='Single line to lookup')
    parser.add_argument('--csv', type=str, default='fedex_pdf_extracted.csv',
                       help='CSV file with rate data')

    args = parser.parse_args()

    search = FedExPriceSearch(csv_file=args.csv)

    if args.demo:
        # Test cases from the requirements (exact examples provided)
        test_lines = [
            "FedEx 2Day, Zone 5, 3 lb",
            "Standard Overnight, z2, 10 lbs, other packaging",
            "Express Saver Z8 1 lb",
            "Ground Z6 12 lb",
            "Home Delivery zone 3 5 lb",
            # Additional tests
            "Ground Zone 2 1 lb",
            "2Day Zone 3 10 lb"
        ]
        search.demo_search(test_lines)

    elif args.line:
        price = search.get_price(args.line)
        if price:
            print(f"${price}")
        else:
            print("No price found")

    else:
        # Interactive mode
        print("FedEx Price Search - Interactive Mode")
        print("Enter shipping details (e.g., 'Ground Zone 5, 3 lb')")
        print("Type 'quit' to exit\n")

        while True:
            try:
                line = input("Enter shipping details: ").strip()
                if line.lower() == 'quit':
                    break

                if line:
                    price = search.get_price(line)
                    if price:
                        print(f"Price: ${price}\n")
                    else:
                        print("No price found\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break

if __name__ == "__main__":
    main()