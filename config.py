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

# Logs Directory
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Ensure directories exist
for d in [STATIC_DIR, LOG_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)
