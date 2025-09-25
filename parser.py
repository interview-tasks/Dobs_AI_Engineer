import pdfplumber
import pandas as pd
import re
import os

def clean_cell(cell_text):
    """
    Cleans the text extracted from a PDF table cell by removing currency symbols,
    newlines, and extra whitespace, and correcting common OCR errors.
    """
    if cell_text is None:
        return ''
    # Replace newlines with a single space
    cleaned_text = cell_text.replace('\n', ' ').strip()
    # Remove the dollar sign
    cleaned_text = cleaned_text.replace('$', '').strip()
    # Correct OCR errors where a colon is used instead of a decimal point
    cleaned_text = re.sub(r'(\d):(\d)', r'\1.\2', cleaned_text)
    return cleaned_text

def extract_fedex_rates_to_csv(pdf_path, start_page, end_page, output_csv):
    """
    Extracts FedEx U.S. package rate tables from specified pages of a PDF,
    identifies the shipping zone for each table, and saves the consolidated
    data into a single CSV file.

    Args:
        pdf_path (str): The file path to the FedEx rates PDF.
        start_page (int): The starting page number to process (1-based).
        end_page (int): The ending page number to process (1-based).
        output_csv (str): The name of the output CSV file.
    """
    all_table_rows = []
    current_zone = "Unknown"

    print(f"Starting extraction from '{pdf_path}'...")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Adjust page numbers for 0-based indexing
            pages_to_process = pdf.pages[start_page - 1 : end_page]

            for i, page in enumerate(pages_to_process, start=start_page):
                print(f"Processing page {i}...")
                page_text = page.extract_text()

                # Find and update the current zone if a new one is found on the page
                zone_match = re.search(r'U\.S\. package rates: Zone (\w+)', page_text)
                if zone_match:
                    # Clean up the zone identifier, removing any stray characters
                    current_zone = zone_match.group(1).replace("'", "")

                tables = page.extract_tables()
                if not tables:
                    print(f"  - No tables found on page {i}.")
                    continue

                for table in tables:
                    for row in table:
                        # Skip empty rows or rows that are clearly headers
                        if not row or not row[0] or any(header in row[0].lower() for header in ['delivery', 'service', 'commitment', 'fedex']):
                            continue
                        
                        # A valid data row should have at least 7 columns (Weight + 6 Services)
                        if len(row) >= 7:
                            weight = clean_cell(row[0])
                            
                            # Clean the rate cells
                            rates = [clean_cell(cell) for cell in row[1:7]]
                            
                            # Add the full row with zone information to our list
                            full_row_data = [current_zone, weight] + rates
                            all_table_rows.append(full_row_data)

        if not all_table_rows:
            print("Extraction complete, but no valid data rows were found.")
            return
            
        # Define the headers for the final CSV file
        headers = [
            'Zone', 'Weight (lbs)', 'First Overnight', 'Priority Overnight', 
            'Standard Overnight', '2Day A.M.', '2Day', 'Express Saver'
        ]

        # Create a pandas DataFrame
        df = pd.DataFrame(all_table_rows, columns=headers)

        # Remove any rows that might be malformed headers or footers
        df = df[~df['Weight (lbs)'].str.contains('packaging / maximum', case=False, na=False)]
        df.dropna(how='all', inplace=True)

        # Save the DataFrame to a CSV file
        df.to_csv(output_csv, index=False)
        print(f"\n✅ Success! Extracted {len(df)} rows of data into '{output_csv}'.")

    except FileNotFoundError:
        print(f"❌ Error: The file '{pdf_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Main execution ---
if __name__ == "__main__":
    PDF_FILE = 'data/FedEx_Standard_List_Rates_2025.pdf'
    OUTPUT_FILE = 'fedex_rates_pages_2_to_21.csv'
    
    # Check if the PDF file exists in the same directory as the script
    if os.path.exists(PDF_FILE):
        # Extract data from page 2 to page 21
        extract_fedex_rates_to_csv(
            pdf_path=PDF_FILE,
            start_page=2,
            end_page=21,
            output_csv=OUTPUT_FILE
        )
    else:
        print(f"❌ Error: Make sure the file '{PDF_FILE}' is in the same directory as this script.")