import sqlite3
import os
from datetime import datetime

DB_NAME = "products.db"

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
            brand TEXT,
            image_data BLOB,
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
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def add_product(code, name, brand, cost_price, image_data=None, stock_quantity=0):
    """Add a single product to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO products (code, name, brand, cost_price, image_data, stock_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (code, name, brand, cost_price, image_data, stock_quantity))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"Product with code {code} already exists.")
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

# Initialize DB on import if not exists
if not os.path.exists(DB_NAME):
    init_db()
