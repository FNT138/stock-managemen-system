import os
import datetime
import json
import pdfplumber
import re
from database import update_product, log_sale_db, get_next_sale_number

LOG_DIR = "logs"

def calculate_sale_price(cost_price):
    """Business rule: Cost + 51%"""
    if cost_price is None:
        return 0.0
    return round(cost_price * 1.51, 2)

def parse_pdf_catalog(pdf_file):
    """
    Parses a PDF using geometric analysis (extract_words) to handle grid layouts.
    Structure:
    - [Image space]
    - Name / Category / Brand (Text block)
    - "Código: ..."
    - "Precio sin IVA:..... 123.45"
    """
    products = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
                
                # 1. Identify Anchors: Price
                # We look for the sequence "Precio" "sin" "IVA" or just "Precio" close to a number.
                # However, words are individual tokens.
                # Let's group words into 'lines' first to simplify text searching while keeping geometry.
                
                # Sort by Y then X
                words.sort(key=lambda w: (round(w['top']), w['x0']))
                
                # Group into lines
                lines = []
                current_line = []
                if words:
                    current_y = words[0]['top']
                    for w in words:
                        if abs(w['top'] - current_y) > 5: # New line threshold
                            lines.append(current_line)
                            current_line = []
                            current_y = w['top']
                        current_line.append(w)
                    lines.append(current_line)
                
                # 2. Find Price Blocks and Code Blocks in lines
                price_blocks = [] # List of {'price': float, 'rect': (x0, top, x1, bottom)}
                code_blocks = [] # List of {'code': str, 'rect': ...}
                other_text_blocks = [] # Potential name text
                
                for line in lines:
                    # Reconstruct line text to check pattern
                    line_text = " ".join([w['text'] for w in line])
                    
                    # Check for Price
                    # Pattern: "Precio" ... digits
                    if "Precio" in line_text and "IVA" in line_text:
                        # Extract value. We can look at the words in the line.
                        # Usually the price is the last few tokens.
                        # Look for digits in the reverse order of words
                        price_val = 0.0
                        # Heuristic: Join all words that look like parts of a number at the end
                        # "7", ".420,00" -> "7.420,00"
                        # Or "180,00"
                        
                        # Find index of "IVA" or "IVA:" or "IVA:....."
                        try:
                            # Robust search for where the price 'headers' end
                            # We can just search for ANY sequence of chars that forms a valid price number at the end
                            # Iterate words backwards
                            num_str = ""
                            used_words = []
                            for w in reversed(line):
                                txt = w['text'].replace('.', '').replace(',', '.')
                                # Check if it looks like a part of number or currency
                                if re.match(r'^[\d\.]+$', txt):
                                    num_str = w['text'] + num_str # Prepend since we are going backwards
                                    used_words.append(w)
                                elif "IVA" in w['text'] or "..." in w['text']:
                                    break
                            
                            # Clean num_str
                            # "7.420,00" -> "7420.00"
                            clean_price = num_str.replace(' ', '').replace('.', '').replace(',', '.')
                            price_val = float(clean_price)
                            
                            # Define rect for this block (uses the whole line or just the center?)
                            # Use the geometric center of the 'Precio...Price' line as the anchor X
                            x_center = (line[0]['x0'] + line[-1]['x1']) / 2
                            rect = {
                                'x0': line[0]['x0'],
                                'top': line[0]['top'],
                                'bottom': line[0]['bottom'],
                                'x_center': x_center
                            }
                            price_blocks.append({'price': price_val, 'rect': rect})
                        except:
                            pass # Failed to parse price
                            
                    # Check for Code
                    elif "Código" in line_text or "Codigo" in line_text:
                        # Logic: Extract code text after "Código:"
                        # Sometimes "Código:" is its own word, sometimes "Código:W"
                        # We want the text after the label.
                        joined_text = "".join([w['text'] for w in line]) # Remove spaces to handle "Código: W" vs "Código :W"
                        # Regex on joined text might be safer
                        # joined: Código:W207001
                        # Regex: Código:?(.+)
                        match = re.search(r'Códiho:?(.+)', joined_text) or re.search(r'Código:?(.+)', joined_text)
                        if match:
                            code_str = match.group(1).strip()
                            x_center = (line[0]['x0'] + line[-1]['x1']) / 2
                            rect = {
                                'x0': line[0]['x0'],
                                'top': line[0]['top'],
                                'bottom': line[0]['bottom'],
                                'x_center': x_center
                            }
                            code_blocks.append({'code': code_str, 'rect': rect})
                            
                    else:
                        # Probably Name/Brand text
                        # Store it for matching
                        x_center = (line[0]['x0'] + line[-1]['x1']) / 2
                        rect = {
                            'x0': line[0]['x0'],
                            'top': line[0]['top'],
                            'bottom': line[0]['bottom'],
                            'x_center': x_center
                        }
                        other_text_blocks.append({'words': line, 'rect': rect})

                # 3. Match Blocks: Price -> Code -> Name
                # Strategy: For each Price, find the closest Code above it with similar X-center.
                # Threshold for X alignment: +/- 50 to 100 pixels (columns are usually distinct)
                
                for p_block in price_blocks:
                    p_rect = p_block['rect']
                    
                    # Find Code
                    # Candidates: strictly above price (bottom < price.top)
                    # Horizontally aligned (abs(code.x - price.x) < threshold)
                    candidates = [
                        c for c in code_blocks 
                        if c['rect']['bottom'] <= p_rect['top'] + 5 # slight overlap allowed
                        and abs(c['rect']['x_center'] - p_rect['x_center']) < 100
                    ]
                    # Pick the closest one vertically (max top)
                    if not candidates:
                        continue
                        
                    best_code = max(candidates, key=lambda c: c['rect']['top'])
                    
                    # Find Name
                    # Candidates: strictly above Code
                    # Horizontally aligned
                    # Stop if we hit another Code or Price (which would belong to row above)
                    
                    # Search range: From Code Top upwards to... say, 150 pixels? Or until another product.
                    # Actually, we can just grab all 'other_text' blocks that fit the geometry match
                    # and are "immediately" above.
                    
                    name_candidates = [
                        t for t in other_text_blocks
                        if t['rect']['bottom'] <= best_code['rect']['top'] + 5
                        and abs(t['rect']['x_center'] - p_rect['x_center']) < 100
                    ]
                    
                    # Sort candidates by top (highest first? or lowest first i.e. closest to code?)
                    # Text usually reads top-down.
                    # We need to filter out text that belongs to the product ABOVE this one.
                    # Heuristic: The gap between "This Product's Name" and "Product Above Price" is usually larger?
                    # Or simply: take the closest N lines?
                    # Let's take *all* candidates that are within a reasonable vertical distance (e.g. 100px) from Code.
                    
                    relevant_lines = []
                    for t in name_candidates:
                        if (best_code['rect']['top'] - t['rect']['bottom']) < 100:
                            relevant_lines.append(t)
                            
                    # Sort by Y (top to bottom)
                    relevant_lines.sort(key=lambda x: x['rect']['top'])
                    
                    full_name_words = []
                    for line_block in relevant_lines:
                        # Filter out potential garbage or headers if needed
                        full_name_words.extend([w['text'] for w in line_block['words']])
                        
                    # Now parsing Name/Brand from the collected words
                    # "Asiento MTB c/guia ... negro/rojo"
                    # User rules: 
                    # - Category (multiple words)
                    # - Brand (ALL CAPS)
                    # - Description (starts with Number or rest)
                    
                    brand = "Generic"
                    category = []
                    description = []
                    
                    state = "CATEGORY"
                    for word in full_name_words:
                        clean_word = word.strip(".,/")
                        if not clean_word: continue
                        
                        if state == "CATEGORY":
                            if word.isupper() and len(clean_word) > 1 and not word[0].isdigit():
                                brand = word
                                state = "DESCRIPTION"
                            elif word[0].isdigit():
                                state = "DESCRIPTION"
                                description.append(word)
                            else:
                                category.append(word)
                        else:
                            description.append(word)
                            
                    final_name = " ".join(category) + " " + " ".join(description)
                    if not final_name.strip():
                        final_name = "Unknown Product"

                    products.append({
                        "code": best_code['code'],
                        "name": final_name,
                        "brand": brand,
                        "cost_price": p_block['price']
                    })
                    
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        return []
        
    return products

def process_sale_transaction(cart_items):
    """
    Finalize a sale.
    cart_items: List of dicts {'code': str, 'name': str, 'brand': str, 'quantity': int, 'sale_price': float}
    """
    total_value = sum(item['quantity'] * item['sale_price'] for item in cart_items)
    sale_timestamp = datetime.datetime.now()
    sale_number = get_next_sale_number()
    
    # 1. Update Stock in DB
    for item in cart_items:
        # Subtract quantity
        update_product(item['code'], stock_delta=-item['quantity'])
    
    # 2. Generate Log File
    # Filename: venta_[SaleNumber]_[Timestamp].log
    ts_str = sale_timestamp.strftime("%Y%m%d-%H%M%S")
    filename = f"venta_{sale_number}_{ts_str}.log"
    filepath = os.path.join(LOG_DIR, filename)
    
    # Content format: Product Name, Brand, Code, Quantity sold, Price sold
    log_content = []
    for item in cart_items:
        line = f"{item['name']}, {item.get('brand','N/A')}, {item['code']}, {item['quantity']}, {item['sale_price']}"
        log_content.append(line)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(log_content))
    except OSError as e:
        print(f"Error writing log file: {e}")

    # 3. Log to internal DB for record keeping
    items_json = json.dumps(cart_items)
    log_sale_db(total_value, items_json)
    
    return filename
