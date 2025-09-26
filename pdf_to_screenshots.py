INPUT_PDF = "pdf/FedEx_Standard_List_Rates_2025.pdf"
OUTPUT_DIR = "data/fedex_pages"
ZIP_PATH = "data/fedex_pages.zip"
SCALE = 2.0  # 1.0 = ~72 dpi; 2.0 ≈ 144 dpi. Increase for higher resolution (e.g., 3.0).

import os
import sys
import zipfile

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def list_dir(path):
    try:
        return sorted(os.listdir(path))
    except Exception:
        return []

try:
    import fitz  # PyMuPDF
except Exception as e:
    print("ERROR: PyMuPDF (fitz) is not available in this environment.")
    print("To run this script locally, install PyMuPDF and Pillow, e.g.:")
    print("  python -m pip install --upgrade pip")
    print("  python -m pip install pymupdf pillow")
    raise

if not os.path.isfile(INPUT_PDF):
    print(f"ERROR: Input PDF not found at: {INPUT_PDF}")
    print("Current working directory contents:")
    for p in list_dir("."):
        print(" -", p)
    if os.path.isdir("data"):
        print("\nContents of data/:")
        for p in list_dir("data"):
            print(" -", p)
    raise FileNotFoundError(f"Input PDF not found: {INPUT_PDF}")

ensure_dir(OUTPUT_DIR)

doc = fitz.open(INPUT_PDF)
num_pages = doc.page_count
print(f"Opened PDF: {INPUT_PDF}  —  pages: {num_pages}")

matrix = fitz.Matrix(SCALE, SCALE)
saved_files = []

for i in range(num_pages):
    page = doc.load_page(i)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    filename = f"page_{i+1:03d}.png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    pix.save(out_path)
    saved_files.append(out_path)
    print(f"Saved page {i+1}/{num_pages} -> {out_path}")

doc.close()

with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for f in saved_files:
        zf.write(f, arcname=os.path.basename(f))

print(f"\nAll pages saved to directory: {OUTPUT_DIR}")
print(f"Zipped screenshots to: {ZIP_PATH}")
