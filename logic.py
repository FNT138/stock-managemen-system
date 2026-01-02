import os
import time
import requests
import pdfplumber
import re
import datetime
import json
from bs4 import BeautifulSoup
from database import update_product, log_sale_db, get_next_sale_number, add_product

import config

# --- CONFIGURATION ---
LOG_DIR = config.LOG_DIR
DOWNLOADS_DIR = config.STATIC_DIR
MISSING_IMAGES_LOG = "missing_images.txt"

# Search Template - Editable
# Example: https://norbertominero.com.ar/buscar?controller=search&s=1010
SEARCH_TEMPLATE = "https://norbertominero.com.ar/buscar?controller=search&s={CODE}"

# Request Headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def calculate_sale_price(cost_price):
    if cost_price is None: return 0.0
    return round(cost_price * 1.51, 2)

# ==============================================================================
# PHASE 1: The Data Skeleton (PDF Parsing)
# ==============================================================================

def extract_brand_from_cell(page, cell_rect):
    """
    Scans a specific rectangular area (the Description cell) for text 
    that is BOTH Bold and UPPERCASE.
    
    cell_rect: (x0, top, x1, bottom)
    """
    # Crop the page to the cell
    try:
        # pdfplumber rect is (x0, top, x1, bottom)
        cell_crop = page.crop(cell_rect)
        
        # Extract words with font info
        words = cell_crop.extract_words(extra_attrs=['fontname'])
        
        brand_parts = []
        for w in words:
            text = w['text']
            font = w['fontname'].lower()
            
            # Check criteria
            is_bold = 'bold' in font or 'black' in font
            is_upper = text.isupper()
            # Ignore numbers or small tokens if needed, but User said "Bold AND UPPER".
            # Sometimes brands have numbers like "3M". 
            
            if is_bold and is_upper:
                brand_parts.append(text)
        
        if brand_parts:
            return " ".join(brand_parts)
            
    except Exception:
        pass # Cropping might fail if rect is invalid
        
    return "Generic" # Default

def process_data_pdf(pdf_path):
    """
    Parses the Text-PDF with strict 4-column layout:
    Col 0: Code
    Col 1: Content (Name TYPE BRAND Description)
    Col 2: Xbulto (Ignore)
    Col 3: Price
    """
    extracted_products = []
    
    print(f"[Phase 1] Parsing PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            if i % 1 == 0: print(f"[Phase 1] Processing Page {i+1}/{total_pages}...")
            
            # Find tables
            tables = page.find_tables()
            
            for table in tables:
                table_data = table.extract()
                table_rows = table.rows
                
                for row_idx, row_data in enumerate(table_data):
                    clean_row = [c for c in row_data if c and c.strip()]
                    
                    # Less than 3 valid items? Likely invalid
                    if len(clean_row) < 3: continue
                    
                    # MAPPING based on User feedback:
                    # Raw Row often has empty cells.
                    # e.g. ["W123", "Product Name...", "50", "12.00"]
                    # If some are empty, indices shift in `clean_row`.
                    # But `row_data` preserves Structure (None for empty).
                    
                    # We expect roughly 4 columns in the visual table.
                    # Let's rely on `row_data` indices if possible, or mapping clean_row.
                    
                    # 1. CODE (Always Col 0)
                    code = row_data[0]
                    if not code: code = clean_row[0] # Fallback
                    if not code or code.lower() in ['código', 'codigo', 'code']: continue
                    
                    # 2. PRICE (Heuristic Strategy)
                    # User states: Col 4 (index 3) is Price. Col 3 (index 2) is Ignore (Xbulto).
                    # We will try to fetch from Index 3 first. If not, scan backwards.
                    
                    cost_price = 0.0
                    
                    def parse_price_str(s):
                        if not s: return None
                        # Remove Currency symbol and whitespace
                        s_clean = s.replace('$', '').strip()
                        if not s_clean: return None
                        
                        # Handle formats:
                        # 1.234,56 (AR/EU) -> remove dots, replace comma with dot
                        # 1,234.56 (US) -> remove comma, keep dot (Less likely but possible)
                        # Simple Heuristic: 
                        # If matches ^[\d]+$ (Int) -> OK
                        # If matches ^[\d\.]+,[\d]+$ (AR) -> 1234.56
                        
                        # Aggressive cleaning for standard AR usage:
                        # Remove ALL spaces
                        s_clean = s_clean.replace(' ', '')
                        
                        # Replace . with nothing (thousands)
                        # Replace , with . (decimal)
                        # BUT be careful if it is 123.45 (US style simple float) and no thousands.
                        # Conflict: 1.200 (1200) vs 1.2 (1.20).
                        # Context: Prices usually > 1?
                        
                        # Let's try standard replace first
                        try_ar = s_clean.replace('.', '').replace(',', '.')
                        try:
                            return float(try_ar)
                        except:
                            pass
                            
                        # Try direct float (US style)
                        try:
                            return float(s_clean)
                        except:
                            return None

                    # A. Try strict Column 3 (4th column)
                    if len(row_data) > 3:
                        p_val = parse_price_str(row_data[3])
                        if p_val is not None:
                            cost_price = p_val
                            
                    # B. If failed, try last item of clean_row
                    if cost_price == 0.0 and len(clean_row) > 0:
                        p_val = parse_price_str(clean_row[-1])
                        if p_val is not None:
                            cost_price = p_val
                            
                    if cost_price == 0.0:
                        print(f"[WARN] Failed to parse price for CODE: {code}. Raw Row: {clean_row}")
                    
                    # 3. CONTENT (Col 1)
                    raw_content = ""
                    content_cell_rect = None
                    
                    if len(row_data) > 1 and row_data[1]:
                        raw_content = row_data[1].replace('\n', ' ').strip()
                        # Get rect for Brand extraction
                        if row_idx < len(table_rows) and len(table_rows[row_idx].cells) > 1:
                            content_cell_rect = table_rows[row_idx].cells[1]
                    else:
                         # Fallback if row_data[1] is None?? Unlikely for a valid row
                         continue

                    # 4. PARSING CONTENT
                    # Format: "Name TYPE Brand Description"
                    # - Brand: Extract via Bold Style
                    brand = "Generic"
                    if content_cell_rect:
                        brand = extract_brand_from_cell(page, content_cell_rect)
                    
                    # Remove Brand from content string to simplify parsing
                    # (Simple string replace, might correspond to exact substring)
                    if brand != "Generic":
                        # Case insensitive replace?
                        pattern = re.compile(re.escape(brand), re.IGNORECASE)
                        content_minus_brand = pattern.sub("", raw_content).strip()
                    else:
                        content_minus_brand = raw_content
                        
                    # Split Name vs Type vs Description
                    # User: "Name is first... Type is UPPERCASE... Description has numbers"
                    tokens = content_minus_brand.split()
                    
                    name_parts = []
                    type_parts = []
                    desc_parts = []
                    
                    # Heuristic State Machine being simple:
                    # 1. Accumulate Name until we hit an ALL-CAPS word (Type)?
                    #    But Name itself might be "ASIENTO" (all caps).
                    #    User ex: "Asiento NENA 14/16..." -> Name=Asiento, Type=NENA
                    #    User ex: "Asiento freestyle..." -> Type is Uppercase? "freestyle" is lower.
                    #    User said: "type (MTB, freestyle, etc.) always in uppercase"
                    #    So "FREESTYLE" would be type.
                    
                    # Let's try:
                    # First word is always Name?
                    # Then look for Type-like Uppercase words.
                    # The rest is Description.
                    
                    if not tokens:
                        final_name = "Unknown"
                        category = "Generic"
                        description = ""
                    else:
                        # Assumed Name = First Word + maybe more?
                        # Let's treat valid Categories as Upper Case words found early.
                        
                        # Simplistic approach:
                        # Name = First word
                        # Rest = Scan for Upper Case -> Category
                        # Everything else -> Description
                        
                        final_name = tokens[0] # "Asiento"
                        category_found = []
                        remaining_tokens = tokens[1:]
                        
                        desc_tokens = []
                        
                        for t in remaining_tokens:
                            # Uppercase and length > 2 (avoid 'A', 'Y', 'X' noise?)
                            # User said "always in uppercase". 
                            # "NENA", "KALF" (Wait, KALF might be Brand?)
                            # If we extracted Brand separately, KALF might be gone.
                            # If Brand wasn't bold, it might still be here.
                            
                            if t.isupper() and len(t) > 1 and not any(c.isdigit() for c in t):
                                category_found.append(t)
                            else:
                                desc_tokens.append(t)
                                
                        if category_found:
                            category = " ".join(category_found)
                        else:
                            category = "Generic"
                        
                        if desc_tokens:
                            description = " ".join(desc_tokens)
                        else:
                            description = ""
                            
                        # If the name is just one word, maybe append if description looks like text?
                        # User wants separate columns.
                    
                    extracted_products.append({
                        'code': code.strip(),
                        'name': final_name,
                        'brand': brand,
                        'category': category,
                        'description': description,
                        'cost_price': cost_price,
                        'image_path': None # Computed later
                    })

    print(f"[Phase 1] Completed. Found {len(extracted_products)} products.")
    return extracted_products

# ==============================================================================
# PHASE 2: The Image Skin (Web Scraping)
# ==============================================================================

def scrape_product_images(product_list, progress_callback=None):
    """
    Iterates through products, searches web, downloads image.
    Updates the 'image_path' key in the product dicts.
    
    progress_callback: function(current, total) for UI updates.
    """
    total = len(product_list)
    print(f"[Phase 2] Starting Web Scraping including 1s delay (Total: {total})...")
    
    with open(MISSING_IMAGES_LOG, "w") as missing_log:
        for i, product in enumerate(product_list):
            code = product['code']
            filename = f"{code.replace('/','-')}.jpg"
            # Absolute path for saving file
            local_abs_path = os.path.join(DOWNLOADS_DIR, filename)
            # Relative path for Database (portable)
            db_rel_path = f"{config.STATIC_DIR_NAME}/{filename}"

            print(f"[DEBUG] Processing {i}/{total} - Code: {code}")

            # 1. Check if we already have it locally
            if os.path.exists(local_abs_path):
                print(f"[DEBUG] Image already exists locally for CODE: {code}, skipping download")
                product['image_path'] = db_rel_path
                if progress_callback: progress_callback(i, total)
                continue

            # report progress
            if progress_callback:
                progress_callback(i, total)
            elif i % 10 == 0:
                print(f"[INFO] Scraping {i}/{total} - Code: {code}")
            
            # 2. Construct Search URL
            url = SEARCH_TEMPLATE.format(CODE=code)
            
            try:
                # 3. Request
                print(f"[DEBUG] Web request for CODE: {code} -> {url}")
                response = requests.get(url, headers=HEADERS, timeout=10)
                time.sleep(1) # Respectful delay
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 4. Extract Image URL
                    # ADAPT SELECTOR HERE based on site inspection.
                    img_tag = soup.select_one("article.product-miniature div.thumbnail-container img")
                    
                    # Fallback selectors if site is different
                    if not img_tag:
                        img_tag = soup.select_one(".product_img_link img") # Older PS
                    if not img_tag:
                         img_tag = soup.select_one(".product-image img")
                         
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src')
                        
                        # Download Image
                        if img_url:
                            print(f"[DEBUG] Downloading image for CODE: {code} from {img_url}")
                            img_data = requests.get(img_url, headers=HEADERS, timeout=10).content
                            
                            with open(local_abs_path, "wb") as f:
                                f.write(img_data)
                                
                            product['image_path'] = db_rel_path
                            print(f"[INFO] Downloaded image for CODE: {code}")
                        else:
                             print(f"[WARN] Img tag found but no src for CODE: {code}")
                             missing_log.write(f"{code}: Img tag found but no src\n")
                    else:
                        print(f"[WARN] No image selector matched for CODE: {code}")
                        missing_log.write(f"{code}: No image selector matched\n")
                else:
                    print(f"[ERROR] HTTP {response.status_code} for CODE: {code}")
                    missing_log.write(f"{code}: HTTP {response.status_code}\n")
                    
            except Exception as e:
                print(f"[ERROR] Exception processing {code}: {e}")
                missing_log.write(f"{code}: Exception {e}\n")
                
            # Default missing path
            if 'image_path' not in product:
                product['image_path'] = None

    if progress_callback: progress_callback(total, total)
    print("[Phase 2] Completed.")
    return product_list

# ==============================================================================
# PHASE 3: DB Assembly
# ==============================================================================

def run_etl_pipeline(pdf_path, progress_callback=None):
    """
    Master function to run Phase 1 (PDF) + Phase 2 (Scrape) + Phase 3 (DB).
    """
    # Phase 1
    products = process_data_pdf(pdf_path)
    
    # Phase 2
    products = scrape_product_images(products, progress_callback)
    
    # Phase 3
    added_count = 0
    print(f"[Phase 3] Updating Database with {len(products)} items...")
    for i, p in enumerate(products):
        print(f"[DEBUG] DB Sync {i}/{len(products)} - Code: {p['code']}")
        
        if add_product(
            code=p['code'],
            name=p['name'],
            category=p['category'],
            brand=p['brand'],
            cost_price=p['cost_price'],
            image_path=p['image_path'],
            description=p.get('description', '')
        ):
            added_count += 1
            print(f"[INFO] DB Insert/Update Success: {p['code']}")
        else:
             print(f"[WARN] DB Insert/Update Failed/Skipped: {p['code']}")
            
    print(f"[Phase 3] Done. Added/Updated {added_count} records.")
    return added_count

# ==============================================================================
# SALES LOGIC (Unchanged)
# ==============================================================================
def process_sale_transaction(cart_items):
    total_value = sum(item['quantity'] * item['sale_price'] for item in cart_items)
    sale_timestamp = datetime.datetime.now()
    sale_number = get_next_sale_number()
    
    for item in cart_items:
        update_product(item['code'], stock_delta=-item['quantity'])
    
    ts_str = sale_timestamp.strftime("%Y%m%d-%H%M%S")
    filename = f"venta_{sale_number}_{ts_str}.log"
    filepath = os.path.join(LOG_DIR, filename)
    
    log_content = []
    for item in cart_items:
        line = f"{item['name']}, {item.get('brand','N/A')}, {item['code']}, {item['quantity']}, {item['sale_price']}"
        log_content.append(line)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(log_content))
    except Exception as e:
        print(f"Error logging: {e}")

    items_json = json.dumps(cart_items)
    log_sale_db(total_value, items_json)
    
    return filename
