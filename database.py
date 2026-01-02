import sqlite3
import os
from datetime import datetime
import config

DB_NAME = config.DB_PATH

def init_db():
    """Initialize the database with necessary tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            description TEXT,
            image_path TEXT,
            cost_price REAL DEFAULT 0.0,
            stock_quantity INTEGER DEFAULT 0
        )
    ''')
    
    # Sales log table (for local db tracking, separate from text log file)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_amount REAL,
            items_json TEXT
        )
    ''')
    
    # Used orders table - tracks redeemed order files to prevent duplicates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_items INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def add_product(code, name, category, brand, cost_price, image_path=None, stock_quantity=0, description=None):
    """Add a single product or update if exists (upsert). Preserves existing stock_quantity."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Use INSERT OR REPLACE with special handling to preserve stock_quantity
        # First check if product exists to preserve its stock
        cursor.execute('SELECT stock_quantity, image_path FROM products WHERE code = ?', (code,))
        existing = cursor.fetchone()
        
        if existing:
            # Product exists - update price and details, preserve stock and image if new image is None
            existing_stock = existing[0]
            existing_image = existing[1]
            final_image = image_path if image_path else existing_image
            
            cursor.execute('''
                UPDATE products SET 
                    name = ?, category = ?, brand = ?, description = ?, 
                    cost_price = ?, image_path = ?
                WHERE code = ?
            ''', (name, category, brand, description, cost_price, final_image, code))
            conn.commit()
            print(f"Product {code} updated with new price: {cost_price}")
            return True
        else:
            # New product - insert with provided stock_quantity (default 0)
            cursor.execute('''
                INSERT INTO products (code, name, category, brand, description, cost_price, image_path, stock_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, name, category, brand, description, cost_price, image_path, stock_quantity))
            conn.commit()
            print(f"Product {code} added as new product.")
            return True
    except Exception as e:
        print(f"Error adding/updating product {code}: {e}")
        return False
    finally:
        conn.close()

def update_product(code, cost_price=None, stock_delta=None):
    """Update product details. stock_delta adds/subtracts from current stock."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if cost_price is not None:
        cursor.execute('UPDATE products SET cost_price = ? WHERE code = ?', (cost_price, code))
    
    if stock_delta is not None:
        cursor.execute('UPDATE products SET stock_quantity = stock_quantity + ? WHERE code = ?', (stock_delta, code))
        
    conn.commit()
    conn.close()

def get_all_products():
    """Retrieve all products as a list of dicts."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_all_products():
    """Delete all records from products and sales_log tables."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM sales_log')
    # Reset auto-increment counters
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='products'")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='sales_log'")
    conn.commit()
    conn.close()

def get_product(code):
    """Retrieve a single product by code."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE code = ?', (code,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_next_sale_number():
    """Get the next sale ID for logging purposes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT seq FROM sqlite_sequence WHERE name='sales_log'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0] + 1
    return 1 # Start at 1 if no sales yet (or if table empty/reset)

def log_sale_db(total_amount, items_json):
    """Log sale to internal DB."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sales_log (total_amount, items_json) VALUES (?, ?)', (total_amount, items_json))
    sale_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sale_id

def is_order_used(order_id):
    """Check if an order ID has already been redeemed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM used_orders WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def mark_order_used(order_id, total_items):
    """Mark an order ID as redeemed to prevent duplicate use."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO used_orders (order_id, total_items) VALUES (?, ?)', (order_id, total_items))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already exists
        return False
    finally:
        conn.close()

# Initialize DB on import if not exists
if not os.path.exists(DB_NAME):
    init_db()
else:
    # Ensure new tables exist in existing DB
    init_db()
