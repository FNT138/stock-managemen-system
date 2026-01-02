import sqlite3
import os
import config

conn = sqlite3.connect(config.DB_PATH)
cursor = conn.cursor()

print("Scanning and fixing DB paths...")

cursor.execute("SELECT code, image_path FROM products WHERE image_path IS NOT NULL")
rows = cursor.fetchall()

fixed_count = 0
for code, path in rows:
    new_path = path
    
    # 1. Replace backslashes
    new_path = new_path.replace('\\', '/')
    
    # 2. Replace downloads with static
    if 'downloads/' in new_path:
        new_path = new_path.replace('downloads/', 'static/')
        
    # 3. Ensure it starts with static/
    if '/' in new_path and not new_path.startswith('static/'):
        # If it's just "filename.jpg", prepend static/
        # Check if it has the prefix
        pass # Assume if it has slash it might be full path, but we want relative.
    
    # Simple heuristic: If it ends with .jpg and doesn't start with static/, fix it.
    filename = os.path.basename(new_path)
    final_path = f"static/{filename}"
    
    if final_path != path:
        print(f"Fixing {code}: {path} -> {final_path}")
        cursor.execute("UPDATE products SET image_path = ? WHERE code = ?", (final_path, code))
        fixed_count += 1

conn.commit()
conn.close()
print(f"Fixed {fixed_count} paths.")
