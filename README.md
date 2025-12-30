# stock-managemen-system
Sistema de gestión de stock y ventas desarrollado con Python, Flask y SQLite.

Prompt

Role & Objective:
Act as a Senior Full Stack Python Developer and System Architect. Your goal is to build a complete, robust, and functional Desktop Application for a small business to manage stock, pricing, and sales.
Tech Stack Requirements:
Language: Python 3.10+
Database: SQLite.
GUI Framework: Streamlit (preferred for easy image handling/mosaic views) OR CustomTkinter. Choose the one that best handles dynamic image grids.
PDF Parsing: pdfplumber or PyMuPDF (fitz).
Data Handling: Pandas.
Project Scope & Context:
You need to develop an ERP system with three distinct interfaces (tabs/pages). The business calculates the Sale Price as Cost Price + 51%.
Detailed Requirements by Module:
1. Database Schema & Setup:
Create a SQLite database.
Table products: id (PK), code (unique), name, brand, image_data (BLOB or path), cost_price (float), stock_quantity (int).
Table sales_log: To track the auto-increment number of sales.
2. Interface A: Stock & Pricing Management (The Manager View)
PDF Importer: Create a function to parse a supplier's PDF catalog. Extract: Name, Code, Price (Cost), and Image. Bulk insert/update this into the DB.
Product List: Display a list of products (Name, Brand).
Detail View: When a product is selected, show:
The Image.
Cost Price (editable).
Sale Price (Auto-calculated: Cost * 1.51).
Current Stock.
Actions:
"Update Price": Updates cost and re-calculates sale price in DB.
"Add Stock": Input field to add quantity to the existing stock.
3. Interface B: Supply Order (Restocking)
Data View: Display an "Excel-style" table showing: Code, Name, Brand, Image, and Current Stock.
Ordering System: Allow the user to select products to order.
Output: Generate a summary list showing Code and Quantity required.
Financials: Display the Total Cost Value of the generated order in a separate summary section.
4. Interface C: Point of Sale (POS) / User View
Search: Search bar filtering by Name, Brand, or Code.
Visual Layout: Display results in a Mosaic/Grid view. Each card must show: Image, Name, and Sale Price.
Interaction: Clicking a product opens a modal/expanded view to add to the "Sales Cart".
The Cart:
Show selected products, quantities, and Total Sale Value.
"Finalize Sale" Button:
Deduct quantity from the products table in SQLite.
Generate a local log file.
Logging Strict format:
Filename: venta_[SaleNumber]_[Timestamp].log (e.g., venta_105_20231027-143000.log).
Content: Text file listing Product Name, Brand, Code, Quantity sold, and Price sold.
Instructions for the AI:
Plan: Outline the file structure and logic flow first.
Code: Provide the complete, runnable Python code. If the code is too long, break it down into database.py, logic.py, and app.py.
Dependencies: List all pip install requirements.