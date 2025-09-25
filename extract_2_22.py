#!/usr/bin/env python3
"""
extract_2_22.py

Extract tables from pages 2..22 of the FedEx_Standard_List_Rates_2025.pdf file,
normalize matrix-style tables into a long CSV (weight x zone rows), and optionally
write results into an SQLite DB.

Outputs:
  ./extracted/raw/page_{page}_table_{i}.csv         # raw table CSVs
  ./extracted/normalized/normalized_page_{page}_table_{i}.csv  # melted long CSVs
  ./extracted/provenance_pages_2_22.csv             # provenance registry
  ./fedex_rates.db                                   # optional consolidated SQLite DB

Dependencies:
  pip install pandas pdfplumber camelot-py[cv] sqlalchemy openpyxl
  (Camelot lattice mode requires ghostscript & opencv; tabula-java requires Java.)
  If you cannot install camelot or its system deps, the script will use pdfplumber fallback.

Example:
  python extract_2_22.py --pdf /path/to/FedEx_Standard_List_Rates_2025.pdf --out ./extracted

Author: ChatGPT (script provided as-is). Adapt header mappings if needed for your PDF.

# basic run using pdfplumber fallback
python extract_2_22.py --pdf /mnt/data/FedEx_Standard_List_Rates_2025.pdf --out ./extracted --start 2 --end 22

# try Camelot first (if installed correctly)
python extract_2_22.py --pdf /mnt/data/FedEx_Standard_List_Rates_2025.pdf --out ./extracted --use-camelot --start 2 --end 22

# plus build SQLite DB from normalized CSVs
python extract_2_22.py --pdf /mnt/data/FedEx_Standard_List_Rates_2025.pdf --out ./extracted --build-sqlite --db-path fedex_rates.db

"""
import argparse
import os
import re
import math
import csv
from pathlib import Path
import traceback
import logging

import pandas as pd

# Try to import camelot (optional)
try:
    import camelot
    HAS_CAMELOT = True
except Exception:
    HAS_CAMELOT = False

import pdfplumber
from sqlalchemy import create_engine, Table, Column, Integer, String, Numeric, MetaData

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def clean_money_cell(s: str):
    """Strip currency characters, asterisks and whitespace. Return raw numeric string or None."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return None
    # Remove footnote markers like '*' and text such as 'a'
    s = re.sub(r'[\*\†\•]+', '', s)
    # Remove currency symbol and comma
    s = re.sub(r'[^0-9\.\-]', '', s)
    return s if s != "" else None


def detect_matrix_and_melt(df: pd.DataFrame, page: int, table_index: int, out_normalized_dir: Path):
    """
    Heuristic: if first column name contains 'weight' or 'lb' or the first column values look numeric,
    treat as matrix: first col = weight, other cols = zones; melt to long format.
    Save normalized CSV and return DataFrame (long).
    """
    df_original = df.copy()
    # Normalize column names
    df.columns = [str(c).replace("\n", " ").strip() if c is not None else f"col_{i}" for i, c in enumerate(df.columns)]
    first_col = df.columns[0].lower()
    looks_like_weight_col = False

    # Heuristic 1: header contains 'weight' or 'lb'
    if "weight" in first_col or "lb" in first_col or "lbs" in first_col:
        looks_like_weight_col = True
    else:
        # Heuristic 2: first data cells are numeric or ranges like '1-5'
        sample = df.iloc[:, 0].dropna().astype(str).head(6).tolist()
        numeric_like = sum(1 for v in sample if re.search(r'\d', v))
        if numeric_like >= 1:
            looks_like_weight_col = True

    if not looks_like_weight_col:
        logging.info(f"Page {page} Table {table_index}: not recognized as weight×zone matrix (skipping melt).")
        return None

    # Determine zone columns: typically all columns after first
    zone_cols = list(df.columns[1:])
    if not zone_cols:
        logging.info(f"Page {page} Table {table_index}: no zone-like columns found.")
        return None

    # Melt
    try:
        long = df.melt(id_vars=[df.columns[0]], value_vars=zone_cols,
                       var_name="zone_raw", value_name="base_rate_raw")
    except Exception:
        # fallback: manual loop if melt fails
        rows = []
        weight_col = df.columns[0]
        for _, r in df.iterrows():
            w = r[weight_col]
            for z in zone_cols:
                rows.append({"weight_raw": w, "zone_raw": z, "base_rate_raw": r[z]})
        long = pd.DataFrame(rows)

    long = long.rename(columns={df.columns[0]: "weight_raw"})
    # Clean strings
    long['weight_raw'] = long['weight_raw'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    long['zone_raw'] = long['zone_raw'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    long['base_rate_clean'] = long['base_rate_raw'].apply(clean_money_cell)

    # Numeric conversion
    long['base_rate'] = pd.to_numeric(long['base_rate_clean'], errors='coerce')

    # Attempt to coerce weight_raw to integer weight_lb where possible:
    def parse_weight(w):
        w = str(w).strip()
        # handle ranges like '1 - 5' or '1-5'
        m = re.match(r'^\s*(\d+)\s*[-–]\s*(\d+)\s*$', w)
        if m:
            # represent as lower bound for now (caller may decide). We'll keep weight_raw and not overwrite.
            return int(m.group(1))
        # single number possibly with decimals
        m2 = re.match(r'^\s*(\d+(?:\.\d+)?)\s*$', w)
        if m2:
            val = float(m2.group(1))
            return math.ceil(val)
        # strings like 'Over 150'
        m3 = re.search(r'(\d+)', w)
        if m3:
            return int(m3.group(1))
        return None

    long['weight_lb'] = long['weight_raw'].apply(lambda x: parse_weight(x))
    # Add provenance
    long['pdf_page'] = page
    long['table_index'] = table_index
    # Save normalized CSV
    out_csv = out_normalized_dir / f"normalized_page_{page}_table_{table_index}.csv"
    long.to_csv(out_csv, index=False)
    logging.info(f"Saved normalized long CSV: {out_csv} (rows: {len(long)})")
    return long


def extract_with_camelot(pdf_path: str, pages: str, out_raw_dir: Path):
    """
    Use Camelot to extract tables. Pages argument is a page range string like '2-22'.
    Returns list of provenance entries.
    """
    prov = []
    if not HAS_CAMELOT:
        logging.warning("Camelot not available; skipping camelot extraction.")
        return prov

    logging.info(f"Running Camelot on pages {pages} (lattice first)")
    try:
        # Attempt lattice first (requires ruling lines)
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor="lattice", strip_text="\n")
    except Exception as e:
        logging.warning(f"Camelot lattice failed: {e}\nTrying stream flavor.")
        try:
            tables = camelot.read_pdf(pdf_path, pages=pages, flavor="stream", strip_text="\n")
        except Exception as e2:
            logging.error(f"Camelot stream also failed: {e2}")
            return prov

    # camelot returns a list of tables across pages in order
    for t in tables:
        page = t.page or None
        # t.df is a pandas DataFrame (strings)
        df = t.df.copy()
        # Camelot often includes repeating header rows; keep as raw CSV so we can inspect later
        table_index = getattr(t, 'parsing_report', {}).get('page', None)
        # Save raw CSV
        # If camelot didn't give page, attempt to parse t._page or similar (t has 'page' attr)
        if page is None:
            # fallback: set to -1 (unknown)
            page_num = -1
        else:
            page_num = int(page)
        # Determine a safe file name; camelot doesn't provide table index per page easily so just increment a counter
        # We'll append a uuid-like index based on table's position
        # But t has 'page' and DataFrame shape we can use
        idx_guess = f"{page_num}_{len(df)}_{df.shape[1]}"
        out_csv = out_raw_dir / f"page_{page_num}_table_{idx_guess}.csv"
        df.to_csv(out_csv, index=False)
        prov_entry = {
            "page": page_num,
            "table_index": idx_guess,
            "rows": df.shape[0],
            "cols": df.shape[1],
            "csv_path": str(out_csv),
            "method": "camelot"
        }
        prov.append(prov_entry)
        logging.info(f"Camelot saved raw CSV: {out_csv}")
    return prov


def extract_with_pdfplumber(pdf_path: str, start_page: int, end_page: int, out_raw_dir: Path):
    """
    Uses pdfplumber's extract_tables() fallback for pages start_page..end_page inclusive.
    Returns list of provenance entries.
    """
    prov = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page, end_page + 1):
            if page_num - 1 < 0 or page_num - 1 >= len(pdf.pages):
                logging.warning(f"Requested page {page_num} out of range. Skipping.")
                continue
            page = pdf.pages[page_num - 1]
            try:
                tables = page.extract_tables()
            except Exception as e:
                logging.warning(f"pdfplumber.extract_tables on page {page_num} failed: {e}")
                tables = []
            if not tables:
                # Save raw page text for manual inspection
                text_path = out_raw_dir / f"page_{page_num}_text.txt"
                with open(text_path, "w", encoding="utf-8") as f:
                    t = page.extract_text() or ""
                    f.write(t)
                prov.append({
                    "page": page_num,
                    "table_index": None,
                    "rows": 0,
                    "cols": 0,
                    "csv_path": str(text_path),
                    "method": "pdfplumber_text"
                })
                logging.info(f"Saved page text: {text_path} (no tables detected)")
                continue

            # Save each detected table
            for i, tbl in enumerate(tables, start=1):
                # tbl: list of rows, each row: list of cells
                if not tbl:
                    continue
                header = tbl[0]
                rows = tbl[1:]
                # Normalize and save
                df = pd.DataFrame(rows, columns=header)
                # sanitize column names
                df.columns = [ (str(c).replace("\n", " ").strip() if c is not None else f"col_{j}") for j,c in enumerate(df.columns) ]
                out_csv = out_raw_dir / f"page_{page_num}_table_{i}.csv"
                df.to_csv(out_csv, index=False)
                prov.append({
                    "page": page_num,
                    "table_index": i,
                    "rows": df.shape[0],
                    "cols": df.shape[1],
                    "csv_path": str(out_csv),
                    "method": "pdfplumber"
                })
                logging.info(f"Saved pdfplumber table CSV: {out_csv}")
    return prov


def build_sqlite_from_normalized(normalized_dir: Path, db_path: Path):
    """
    Consolidate all normalized CSVs into a single SQLite 'rates' table.
    This table assumes columns: weight_lb, zone_raw, base_rate, pdf_page, table_index, original_cell...
    """
    engine = create_engine(f"sqlite:///{db_path}")
    meta = MetaData()
    rates = Table('rates', meta,
                  Column('id', Integer, primary_key=True),
                  Column('service', String, nullable=True),
                  Column('section', String, nullable=True),
                  Column('zone_raw', String, nullable=True),
                  Column('weight_raw', String, nullable=True),
                  Column('weight_lb', Integer, nullable=True),
                  Column('base_rate', Numeric(10,2), nullable=True),
                  Column('base_rate_raw', String, nullable=True),
                  Column('pdf_page', Integer, nullable=True),
                  Column('table_index', String, nullable=True),
                  Column('original_csv', String, nullable=True),
                  Column('notes', String, nullable=True)
                  )
    meta.create_all(engine)
    # Append each normalized CSV
    normalized_files = sorted(normalized_dir.glob("normalized_page_*.csv"))
    total = 0
    for f in normalized_files:
        try:
            df = pd.read_csv(f, dtype=str)
        except Exception as e:
            logging.warning(f"Failed to read normalized CSV {f}: {e}")
            continue
        # Ensure expected columns present; map if necessary
        # We expect weight_raw, zone_raw, base_rate_raw, base_rate, weight_lb, pdf_page, table_index
        # Convert base_rate to numeric, weight_lb to integer
        if 'base_rate' in df.columns:
            df['base_rate'] = pd.to_numeric(df['base_rate'], errors='coerce')
        if 'weight_lb' in df.columns:
            df['weight_lb'] = pd.to_numeric(df['weight_lb'], errors='coerce').astype('Int64')
        df['original_csv'] = str(f)
        # Insert into DB in chunks
        df_to_insert = df[['weight_raw','zone_raw','weight_lb','base_rate','base_rate_raw','pdf_page','table_index','original_csv']].copy()
        # rename to match table
        df_to_insert = df_to_insert.rename(columns={
            'base_rate_raw': 'base_rate_raw',
            'weight_raw': 'weight_raw',
            'zone_raw': 'zone_raw'
        })
        # Add placeholder columns service/section/notes as null
        df_to_insert['service'] = None
        df_to_insert['section'] = None
        df_to_insert['notes'] = None
        # Reorder to match table definition
        # Use pandas.to_sql
        df_to_insert.to_sql('rates', engine, if_exists='append', index=False)
        total += len(df_to_insert)
        logging.info(f"Inserted {len(df_to_insert)} rows from {f} into SQLite DB")
    logging.info(f"Total inserted rows: {total} into DB {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract FedEx PDF pages 2-22 tables to CSV and normalized long CSVs.")
    parser.add_argument("--pdf", required=True, help="Path to FedEx_Standard_List_Rates_2025.pdf")
    parser.add_argument("--out", default="./extracted", help="Output directory (default: ./extracted)")
    parser.add_argument("--start", type=int, default=2, help="Start page (inclusive). Default 2")
    parser.add_argument("--end", type=int, default=22, help="End page (inclusive). Default 22")
    parser.add_argument("--use-camelot", action="store_true", help="Attempt camelot extraction first (requires camelot & system deps).")
    parser.add_argument("--build-sqlite", action="store_true", help="Build consolidated SQLite DB from normalized CSVs.")
    parser.add_argument("--db-path", default="fedex_rates.db", help="SQLite DB path if --build-sqlite is set.")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"
    normalized_dir = out_dir / "normalized"
    ensure_dir(raw_dir)
    ensure_dir(normalized_dir)

    # 1) Try Camelot if requested
    provenance = []
    if args.use_camelot and HAS_CAMELOT:
        try:
            pages_str = f"{args.start}-{args.end}"
            prov_c = extract_with_camelot(str(pdf_path), pages_str, raw_dir)
            provenance.extend(prov_c)
        except Exception:
            logging.warning("Camelot extraction raised an exception, falling back to pdfplumber.")
            logging.debug(traceback.format_exc())

    # 2) Use pdfplumber fallback for pages with no raw CSVs
    prov_pdf = extract_with_pdfplumber(str(pdf_path), args.start, args.end, raw_dir)
    provenance.extend(prov_pdf)

    # Save provenance registry
    prov_df = pd.DataFrame(provenance)
    prov_csv_path = out_dir / f"provenance_pages_{args.start}_{args.end}.csv"
    prov_df.to_csv(prov_csv_path, index=False)
    logging.info(f"Wrote provenance CSV: {prov_csv_path}")

    # 3) Normalize detected raw CSVs: attempt to melt matrix-like tables into long form
    # Identify raw CSV files in raw_dir
    raw_csvs = sorted(raw_dir.glob("*.csv"))
    normalized_count = 0
    for raw in raw_csvs:
        try:
            df = pd.read_csv(raw, dtype=str)
        except Exception:
            logging.warning(f"Could not read raw CSV {raw} as table; skipping")
            continue
        # Attempt to parse page/table index from filename
        m = re.search(r'page_(\d+)_table_(.+)\.csv$', raw.name)
        if m:
            page = int(m.group(1))
            table_index = m.group(2)
        else:
            page = None
            table_index = raw.name
        # Attempt to detect matrix and melt
        long_df = detect_matrix_and_melt(df, page, table_index, normalized_dir)
        if long_df is not None:
            normalized_count += 1

    logging.info(f"Normalized {normalized_count} CSVs under {normalized_dir}")

    # 4) Optionally build SQLite from normalized CSVs
    if args.build_sqlite:
        db_path = Path(args.db_path)
        build_sqlite_from_normalized(normalized_dir, db_path)
        logging.info("SQLite DB build complete.")

    logging.info("Extraction finished. See outputs under " + str(out_dir))


if __name__ == "__main__":
    main()
