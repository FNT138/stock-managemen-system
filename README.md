# stock-managemen-system
Sistema de gestión de stock y ventas desarrollado con Python, Flask y SQLite.

Prompt

Role: Senior Python Automation Engineer (Web Scraping & ETL Specialist).
Directives:
RESET CONTEXT: Ignore any previous code or approach regarding PDF parsing or "catalogo-repuestos". We are starting from scratch with a new, simplified architecture.
SINGLE SOURCE OF TRUTH (IMAGES): You must ONLY fetch images from the specific website: https://norbertominero.com.ar. Do not attempt to extract images from PDFs.
Task:
Develop a robust Python ETL pipeline that creates a product database (inventory.db) by merging data from a text-PDF and images from the web.
Phase 1: The Data Skeleton (PDF Parsing)
Input: A text-based PDF containing the columns: Code, Category, Description, and Price (ignore "xbulto").
Library: Use pdfplumber.
Brand Extraction Logic: The "Brand" is NOT in a column. It is embedded in the text description but stylistically distinct. You must iterate through char objects and extract text that is BOTH Bold AND UPPERCASE.
Output: A list/dict of dictionaries: {'code': '...', 'name': '...', 'brand': '...', 'price': ...}.
Phase 2: The Image Skin (Targeted Web Scraping)
Target Domain: https://norbertominero.com.ar
Logic:
For each code extracted in Phase 1, search the website.
Search Pattern: The script must define a SEARCH_TEMPLATE variable at the top. Assume a standard PrestaShop/e-commerce pattern like: https://norbertominero.com.ar/buscar?controller=search&s={CODE} (but make this string easily editable).
Scraping: Use requests (with User-Agent headers to avoid blocking) and BeautifulSoup.
Extraction: Find the product image URL from the search result or product page.
Download: Save the image locally to a folder downloads/ renamed as {code}.jpg.
Fallbacks: If no image is found for a code, log it to missing_images.txt and assume a placeholder image.
Respect: Add a time.sleep(1) delay between requests to avoid overloading the server.
Phase 3: Database Assembly
DB: SQLite.
Table: products
Columns:
id (PK)
code (Unique Index)
name
brand
cost_price
image_path (Relative path to the downloaded local file).
Deliverable:
Provide the complete, single-file Python script. Include comments indicating exactly where to adjust the HTML CSS selectors (e.g., soup.select_one(...)) for the product image, as I will need to inspect the site to get the final class name.