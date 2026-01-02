import os

# Base directory of the project (where this file resides)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database Path
DB_PATH = os.path.join(BASE_DIR, "products.db")

# Static Assets Directory
# Streamlit serves this at /app/static/filename if enabled, 
# but we primarily use it for absolute file path resolution.
STATIC_DIR_NAME = "static"
STATIC_DIR = os.path.join(BASE_DIR, STATIC_DIR_NAME)

# Ensure static directory exists
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
