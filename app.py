import streamlit as st
import pandas as pd
import database as db
import logic
import config
import os
import time

st.set_page_config(page_title="Stock Management S.A.", layout="wide")

# --- CSS Styling ---
st.markdown("""
    <style>
    .product-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
    .price-tag {
        font-size: 1.2em;
        font-weight: bold;
        color: #2e7bcf;
    }
    .stButton>button {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'last_log' not in st.session_state:
    st.session_state.last_log = None
if 'supply_order' not in st.session_state:
    st.session_state.supply_order = []


# --- Sidebar ---
with st.sidebar:
    st.title("Settings")
    if st.button("🔴 Reset Database", help="WARNING: This will delete all products and sales history!"):
        db.clear_all_products()
        st.cache_data.clear()
        st.success("Database cleared!")
        st.session_state.cart = [] # Clear cart too
        st.rerun()

# --- Tabs ---
tab1, tab2 = st.tabs(["Stock & Pricing (Manager)", "Point of Sale (POS)"])

# ==========================================
# INTERFACE A: Stock & Pricing Management
# ==========================================
with tab1:
    st.header("Manager View")
    
    # PDF Import
    st.subheader("Import Catalog (Web Scraper Pipeline)")
    
    st.info("Phase 1: PDF Text Extraction | Phase 2: Web Scraping Images (1s delay/item)")
    
    uploaded_pdf = st.file_uploader("Upload Data PDF", type=["pdf"])

    if uploaded_pdf:
        if st.button("Run ETL & Facelift"):
             progress_bar = st.progress(0, text="Starting ETL...")
             
             with st.spinner("Processing... Do not close this tab."):
                 # Save temporary file
                 temp_path = f"temp_{uploaded_pdf.name}"
                 with open(temp_path, "wb") as f:
                     f.write(uploaded_pdf.getbuffer())
                 
                 # Run ETL via Subprocess
                 # We use a loop to read stdout line by line (unbuffered in runner)
                 import subprocess
                 import sys
                 
                 # Use sys.executable to ensure we use the SAME interpreter (virtualenv)
                 cmd = [sys.executable, "etl_runner.py", temp_path]
                 
                 try:
                     # Start subprocess with stdout piped
                     process = subprocess.Popen(
                         cmd, 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.STDOUT, # Merge stderr to stdout for visibility
                         text=True,
                         bufsize=1, # Line buffered
                         encoding='utf-8', 
                         errors='replace'
                     )
                     
                     status_text = st.empty()
                     
                     # Poll output
                     while True:
                         line = process.stdout.readline()
                         if not line and process.poll() is not None:
                             break
                         
                         if line:
                             line = line.strip()
                             # Parse custom protocol
                             if line.startswith("PROGRESS:"):
                                 parts = line.split(":")
                                 if len(parts) >= 3:
                                     try:
                                         curr = int(parts[1])
                                         tot = int(parts[2])
                                         pct = int((curr / tot) * 100) if tot > 0 else 0
                                         progress_bar.progress(pct, text=f"Scraping Images: {curr}/{tot}")
                                     except:
                                         pass
                             elif line.startswith("STATUS:"):
                                 status_text.text(line.replace("STATUS:", ""))
                             elif line.startswith("RESULT:SUCCESS:"):
                                 count = line.split(":")[2]
                                 st.success(f"ETL Complete! Processed {count} products.")
                                 st.balloons()
                             elif line.startswith("RESULT:ERROR:"):
                                 err_msg = line.replace("RESULT:ERROR:", "")
                                 st.error(f"Critical Error: {err_msg}")
                             else:
                                 # Regular logs (DEBUG/INFO/WARN) - print to console or expandable
                                 # Optional: show last log line in UI
                                 if "[DEBUG]" not in line:
                                     status_text.text(line)
                                 print(line) # Still print to server console
                                     
                     retcode = process.poll()
                     if retcode != 0 and retcode is not None:
                         # check if we already showed RESULT:ERROR
                         # If not, show generic error
                         st.warning("Process finished with non-zero exit code.")
                         
                 except Exception as e:
                     st.error(f"Failed to launch ETL process: {e}")
                 finally:
                     if os.path.exists(temp_path): os.remove(temp_path)
                     time.sleep(2) # Show 100% briefly
                     st.rerun()

    st.divider()
    
    # Database Table
    st.subheader("Product Database")
    all_products = db.get_all_products()
    if all_products:
        df = pd.DataFrame(all_products)
        # Display simplified table
        st.dataframe(df[['code', 'name', 'brand', 'description', 'cost_price', 'stock_quantity']], width="stretch")
        
        # Edit Product Section
        st.subheader("Edit Product")
        col1, col2 = st.columns(2)
        with col1:
            selected_code = st.selectbox("Select Product to Edit", options=df['code'], format_func=lambda x: f"{x} - {df[df['code']==x]['name'].iloc[0]}")
        
        if selected_code:
            current_product = db.get_product(selected_code)
            
            with col2:
                st.info(f"Selected: {current_product['name']}")
                st.text_area("Description", value=current_product.get('description', '') or "", height=100, disabled=True)
                
            c_col1, c_col2, c_col3 = st.columns(3)
            with c_col1:
                # Cost price is READ-ONLY - can only be updated via PDF import
                st.metric("Cost Price", f"${current_product['cost_price']:.2f}")
                calculated_sale = logic.calculate_sale_price(current_product['cost_price'])
                st.metric("Sale Price (Cost + 51%)", f"${calculated_sale:.2f}")
                st.caption("💡 Update prices by uploading a new PDF")
            
            with c_col2:
                add_stock = st.number_input("Add Stock Quantity", min_value=0, value=0)
                if st.button("Add Stock"):
                    db.update_product(selected_code, stock_delta=add_stock)
                    st.success(f"Added {add_stock} units.")
                    st.rerun()
            
            with c_col3:
                # Robust Image Logic
                image_shown = False
                db_rel_path = current_product.get('image_path')
                
                # 1. Try DB Path
                if db_rel_path:
                    db_rel_path = db_rel_path.replace('\\', '/')
                    abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                    if os.path.exists(abs_path):
                        st.image(abs_path, caption="Product Image", width="stretch")
                        image_shown = True
                
                # 2. Fallback
                if not image_shown:
                    safe_code = current_product['code'].replace('/', '-')
                    fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                    if os.path.exists(fallback_abs_path):
                        st.image(fallback_abs_path, caption="Product Image", width="stretch")
                        image_shown = True

                if not image_shown:
                    st.image("https://placehold.co/150x150?text=No+Image", caption="Product Image", width="stretch")
    
    # --- Supply Order Section (Redesigned) ---
    st.divider()
    st.subheader("📦 Supply Order (Restocking)")
    st.info("Search for products by code, add quantities, and generate an order file.")
    
    if all_products:
        # Create product code list for search
        product_codes = [p['code'] for p in all_products]
        
        # Search and Add Product to Order
        so_col1, so_col2 = st.columns([2, 1])
        
        with so_col1:
            selected_order_code = st.selectbox(
                "🔍 Search Product by Code", 
                options=product_codes,
                format_func=lambda x: f"{x} - {next((p['name'] for p in all_products if p['code'] == x), 'Unknown')}",
                key="supply_order_search"
            )
        
        # Show selected product details
        if selected_order_code:
            order_product = db.get_product(selected_order_code)
            
            if order_product:
                st.markdown("---")
                prod_col1, prod_col2, prod_col3 = st.columns([1, 2, 1])
                
                with prod_col1:
                    # Product Image
                    image_shown = False
                    db_rel_path = order_product.get('image_path')
                    
                    if db_rel_path:
                        db_rel_path = db_rel_path.replace('\\', '/')
                        abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                        if os.path.exists(abs_path):
                            st.image(abs_path, width=150)
                            image_shown = True
                    
                    if not image_shown:
                        safe_code = order_product['code'].replace('/', '-')
                        fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                        if os.path.exists(fallback_abs_path):
                            st.image(fallback_abs_path, width=150)
                            image_shown = True
                    
                    if not image_shown:
                        st.image("https://placehold.co/150x150?text=No+Image", width=150)
                
                with prod_col2:
                    st.markdown(f"**{order_product['name']}**")
                    st.markdown(f"**Code:** `{order_product['code']}`")
                    st.markdown(f"**Brand:** {order_product.get('brand', 'N/A')}")
                    st.metric("Cost Price", f"${order_product['cost_price']:.2f}")
                    st.metric("Current Stock", order_product['stock_quantity'])
                
                with prod_col3:
                    order_qty = st.number_input("Order Quantity", min_value=1, value=1, key="order_qty_input")
                    
                    if st.button("➕ Add to Order", type="primary"):
                        # Check if already in order
                        existing = next((item for item in st.session_state.supply_order if item['code'] == order_product['code']), None)
                        if existing:
                            existing['quantity'] += order_qty
                            st.toast(f"Updated quantity for {order_product['name']}")
                        else:
                            st.session_state.supply_order.append({
                                'code': order_product['code'],
                                'name': order_product['name'],
                                'quantity': order_qty,
                                'cost_price': order_product['cost_price']
                            })
                            st.toast(f"Added {order_product['name']} to order")
                        st.rerun()
        
        # Show Current Order
        if st.session_state.supply_order:
            st.markdown("---")
            st.subheader("📋 Current Order")
            
            # Display order as dataframe
            order_df = pd.DataFrame(st.session_state.supply_order)
            order_df['total'] = order_df['quantity'] * order_df['cost_price']
            
            st.dataframe(
                order_df[['code', 'name', 'quantity', 'cost_price', 'total']],
                column_config={
                    "code": "Code",
                    "name": "Product Name",
                    "quantity": "Qty",
                    "cost_price": st.column_config.NumberColumn("Cost Price", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total", format="$%.2f")
                },
                hide_index=True,
                width="stretch"
            )
            
            total_order_cost = order_df['total'].sum()
            st.metric("💰 Total Order Cost", f"${total_order_cost:,.2f}")
            
            # Action buttons
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            
            with btn_col1:
                if st.button("📄 Generate Order File", type="primary"):
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    order_filename = f"order_{timestamp}.csv"
                    order_filepath = os.path.join(config.LOG_DIR, order_filename)
                    
                    # Save to CSV
                    order_df.to_csv(order_filepath, index=False)
                    st.success(f"Order saved to: {order_filename}")
                    st.session_state.last_order_file = order_filepath
            
            with btn_col2:
                if st.button("📥 Add Stock from Order"):
                    # Add the ordered quantities to stock
                    for item in st.session_state.supply_order:
                        db.update_product(item['code'], stock_delta=item['quantity'])
                    st.success("Stock updated from order!")
                    st.session_state.supply_order = []  # Clear order
                    st.rerun()
            
            with btn_col3:
                if st.button("🗑️ Clear Order"):
                    st.session_state.supply_order = []
                    st.rerun()

# ==========================================
# INTERFACE B: Point of Sale (POS)
# ==========================================
with tab2:
    st.header("Point of Sale")
    
    # Layout: Grid + Sidebar Cart
    pos_col1, pos_col2 = st.columns([3, 1])
    
    with pos_col1:
        # Search
        search_query = st.text_input("Search Product", placeholder="Name, Brand, or Code...")
        
        if all_products:
            # Filter: only show products with stock > 0 and matching search
            filtered_prods = [
                p for p in all_products 
                if p['stock_quantity'] > 0 and (
                    search_query.lower() in p['name'].lower() 
                    or search_query.lower() in str(p['brand']).lower() 
                    or search_query.lower() in str(p['code']).lower()
                )
            ]
            
            # Pagination / Limitation for Grid
            # Chunking for grid view
            chunk_size = 3
            chunks = [filtered_prods[i:i + chunk_size] for i in range(0, len(filtered_prods), chunk_size)]
            
            for chunk in chunks:
                cols = st.columns(chunk_size)
                for i, prod in enumerate(chunk):
                    sale_price = logic.calculate_sale_price(prod['cost_price'])
                    with cols[i]:
                        # Card container
                        with st.container():
                            # Image Logic
                            image_shown = False
                            
                            # Image Logic
                            image_shown = False
                            
                            db_rel_path = prod.get('image_path')
                            
                            # 1. Try DB Path (Resolved to Absolute)
                            if db_rel_path:
                                # Normalize just in case
                                db_rel_path = db_rel_path.replace('\\', '/')
                                # Construct Absolute Path
                                abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                                
                                if os.path.exists(abs_path):
                                    st.image(abs_path, width="stretch")
                                    image_shown = True
                            
                            # 2. Try Fallback to static/CODE.jpg
                            if not image_shown:
                                safe_code = prod['code'].replace('/', '-')
                                # Construct fallback absolute path
                                fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                                
                                if os.path.exists(fallback_abs_path):
                                    st.image(fallback_abs_path, width="stretch")
                                    image_shown = True
                                    
                            if not image_shown:
                                st.image("https://placehold.co/150x150?text=No+Image", width="stretch")
                                
                            st.markdown(f'''
                                <div class="product-card">
                                    <h5>{prod['name']}</h5>
                                    <p class="price-tag">${sale_price}</p>
                                    <small>{prod.get('brand','Generic')}</small><br>
                                    <small>Stock: {prod['stock_quantity']}</small>
                                </div>
                            ''', unsafe_allow_html=True)
                            
                            # Add to cart button
                            # Using partial callback or session state logic
                            key = f"add_{prod['code']}"
                            if st.button(f"Add to Cart", key=key):
                                # Add item to cart
                                existing = next((item for item in st.session_state.cart if item['code'] == prod['code']), None)
                                if existing:
                                    existing['quantity'] += 1
                                else:
                                    st.session_state.cart.append({
                                        'code': prod['code'],
                                        'name': prod['name'],
                                        'brand': prod['brand'],
                                        'sale_price': sale_price,
                                        'quantity': 1
                                    })
                                st.toast(f"Added {prod['name']} to cart")

    with pos_col2:
        st.subheader("🛒 Current Cart")
        
        if st.session_state.cart:
            total_sale = 0
            for idx, item in enumerate(st.session_state.cart):
                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    st.text(f"{item['name']}\n${item['sale_price']} x {item['quantity']}")
                with col_c2:
                     if st.button("❌", key=f"del_{idx}"):
                         st.session_state.cart.pop(idx)
                         st.rerun()
                
                total_sale += item['sale_price'] * item['quantity']
                st.divider()
            
            st.metric("Total", f"${total_sale:.2f}")
            
            if st.button("Finalize Sale", type="primary"):
                log_file = logic.process_sale_transaction(st.session_state.cart)
                st.session_state.last_log = log_file
                st.session_state.cart = [] # Clear cart
                st.success("Sale Completed!")
                st.rerun()
        else:
            st.info("Cart is empty")

        if st.session_state.last_log:
            st.success(f"Log generated: {st.session_state.last_log}")

