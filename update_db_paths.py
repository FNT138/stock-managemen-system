import sqlite3
import os

DB_PATH = 'products.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Updating paths relative to 'downloads' to 'static'...")
cursor.execute("UPDATE products SET image_path = REPLACE(image_path, 'downloads', 'static') WHERE image_path LIKE '%downloads%'")
print(f"Updated {cursor.rowcount} rows"A)

cursor.execute("UPDATE products SET image_path = REPLACE(image_path, 'downloads', 'static') WHERE image_path LIKE '%downloads\\%'")
print(f"Updated {cursor.rowcount} rows (backslashes)")

conn.commit()
conn.close()
