# stock-managemen-system
Sistema de gestión de stock y ventas desarrollado con Python, Flask y SQLite.

Prompt
Role: Python Data Engineer specialist in PDF Extraction (ETL).
Task: Create a script to populate a SQLite database from two separate PDF sources.
​Source 1: Data PDF (Text only)
​Library: Use pdfplumber to extract tables.
​Logic:
​Iterate through pages.
​Extract the table. Columns to keep: Code, Category, Description, Price.
​Crucial - Brand Extraction: The "Brand" is NOT in a separate column. It is embedded in the text but distinguished by style: It is in ALL CAPS and BOLD font. You must inspect the char objects in pdfplumber to detect words that satisfy object['fontname'] containing 'Bold' AND text.isupper(). Extract this as the Brand field.
​Ignore/Drop the column named "xbulto".
​Source 2: Catalog PDF (Images)
​Library: Use PyMuPDF (fitz) for high-speed image extraction.
​Logic:
​This PDF contains the images. The link between Image and Product is the Product Code.
​For each page, extract the text to find the "Product Code".
​Extract the image located nearest to that Product Code's bounding box (coordinates).
​Save the image to a folder named /images and rename the file to [Product_Code].png.
​Output:
​A Python script that processes both PDFs.
​It must save the data into a SQLite table products with columns: code (PK), category, name (description), brand, cost_price, image_path.
​Handle exceptions where an image matches multiple codes (take the closest one).