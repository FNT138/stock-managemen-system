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
tab1, tab2, tab3 = st.tabs(["📊 Stock & Pricing", "📦 Restocking", "🛒 Point of Sale"])

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
    
    # Product Grid View
    st.subheader("Product Database")
    all_products = db.get_all_products()
    if all_products:
        df = pd.DataFrame(all_products)
        
        # Search filter
        search_filter = st.text_input("🔍 Filter products", placeholder="Search by name, brand, code or description...", key="stock_search")
        
        if search_filter:
            filtered_products = [
                p for p in all_products 
                if search_filter.lower() in p['name'].lower() 
                or search_filter.lower() in str(p.get('brand', '')).lower() 
                or search_filter.lower() in str(p['code']).lower()
                or search_filter.lower() in str(p.get('description', '')).lower()
            ]
        else:
            filtered_products = all_products
        
        # Pagination settings
        products_per_page = 20
        total_pages = max(1, (len(filtered_products) + products_per_page - 1) // products_per_page)
        
        if 'stock_page' not in st.session_state:
            st.session_state.stock_page = 1
        
        # Page navigation
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        with nav_col1:
            if st.button("⬅️ Anterior", disabled=st.session_state.stock_page <= 1):
                st.session_state.stock_page -= 1
                st.rerun()
        with nav_col2:
            st.caption(f"Página {st.session_state.stock_page} de {total_pages} | {len(filtered_products)} productos")
        with nav_col3:
            if st.button("Siguiente ➡️", disabled=st.session_state.stock_page >= total_pages):
                st.session_state.stock_page += 1
                st.rerun()
        
        # Get current page products
        start_idx = (st.session_state.stock_page - 1) * products_per_page
        end_idx = start_idx + products_per_page
        page_products = filtered_products[start_idx:end_idx]
        
        # 4-column grid
        chunk_size = 4
        chunks = [page_products[i:i + chunk_size] for i in range(0, len(page_products), chunk_size)]
        
        for chunk in chunks:
            cols = st.columns(chunk_size)
            for i, prod in enumerate(chunk):
                with cols[i]:
                    with st.container(border=True):
                        # Image
                        image_shown = False
                        db_rel_path = prod.get('image_path')
                        
                        if db_rel_path:
                            db_rel_path = db_rel_path.replace('\\', '/')
                            abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                            if os.path.exists(abs_path):
                                st.image(abs_path, width="stretch")
                                image_shown = True
                        
                        if not image_shown:
                            safe_code = prod['code'].replace('/', '-')
                            fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                            if os.path.exists(fallback_abs_path):
                                st.image(fallback_abs_path, width="stretch")
                                image_shown = True
                        
                        if not image_shown:
                            st.image("https://placehold.co/150x150?text=No+Image", width="stretch")
                        
                        # Product Info
                        st.markdown(f"**{prod['name'][:30]}**")
                        st.caption(f"📦 `{prod['code']}`")
                        st.caption(f"Marca: {prod.get('brand', 'N/A')}")
                        
                        sale_price = logic.calculate_sale_price(prod['cost_price'])
                        st.markdown(f"💰 **Costo:** ${prod['cost_price']:,.0f}")
                        st.markdown(f"🏷️ **Venta:** ${sale_price:,.0f}")
                        st.markdown(f"📊 **Stock:** {prod['stock_quantity']}")
                        
                        desc = prod.get('description', '') or 'Sin descripción'
                        st.caption(f"{desc[:50]}...")
                        
                        # Add to Order button
                        with st.expander("📦 Agregar a Pedido"):
                            order_qty = st.number_input(
                                "Cantidad", 
                                min_value=1, 
                                value=1, 
                                key=f"stock_order_qty_{prod['code']}"
                            )
                            if st.button("➕ Agregar", key=f"stock_add_order_{prod['code']}", type="primary"):
                                existing = next((item for item in st.session_state.supply_order if item['code'] == prod['code']), None)
                                if existing:
                                    existing['quantity'] += order_qty
                                    st.toast(f"Actualizado: {prod['name']} (+{order_qty})")
                                else:
                                    st.session_state.supply_order.append({
                                        'code': prod['code'],
                                        'name': prod['name'],
                                        'quantity': order_qty,
                                        'cost_price': prod['cost_price']
                                    })
                                    st.toast(f"Agregado: {prod['name']} x{order_qty}")
                                st.rerun()
        
        # Bottom navigation
        st.markdown("---")
        bot_col1, bot_col2, bot_col3 = st.columns([1, 2, 1])
        with bot_col1:
            if st.button("⬅️ Anterior", key="prev_bottom", disabled=st.session_state.stock_page <= 1):
                st.session_state.stock_page -= 1
                st.rerun()
        with bot_col2:
            st.caption(f"Página {st.session_state.stock_page} de {total_pages}")
        with bot_col3:
            if st.button("Siguiente ➡️", key="next_bottom", disabled=st.session_state.stock_page >= total_pages):
                st.session_state.stock_page += 1
                st.rerun()
        
        # Back to top button (using HTML anchor)
        st.markdown('<a href="#product-database" style="text-decoration:none;">⬆️ Volver arriba</a>', unsafe_allow_html=True)
        
        st.divider()
        
        # Edit Product Section
        st.subheader("Edit Product")
        selected_code = st.selectbox(
            "🔍 Select Product to Edit", 
            options=df['code'], 
            format_func=lambda x: f"{x} - {df[df['code']==x]['name'].iloc[0]}"
        )
        
        if selected_code:
            current_product = db.get_product(selected_code)
            
            st.markdown("---")
            prod_col1, prod_col2, prod_col3 = st.columns([1, 2, 1])
            
            with prod_col1:
                # Product Image
                image_shown = False
                db_rel_path = current_product.get('image_path')
                
                if db_rel_path:
                    db_rel_path = db_rel_path.replace('\\', '/')
                    abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                    if os.path.exists(abs_path):
                        st.image(abs_path, width=150)
                        image_shown = True
                
                if not image_shown:
                    safe_code = current_product['code'].replace('/', '-')
                    fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                    if os.path.exists(fallback_abs_path):
                        st.image(fallback_abs_path, width=150)
                        image_shown = True
                
                if not image_shown:
                    st.image("https://placehold.co/150x150?text=No+Image", width=150)
            
            with prod_col2:
                st.markdown(f"**{current_product['name']}**")
                st.markdown(f"**Code:** `{current_product['code']}`")
                st.markdown(f"**Brand:** {current_product.get('brand', 'N/A')}")
                st.markdown(f"**Description:** {current_product.get('description', 'N/A')[:150]}")
                st.metric("Cost Price", f"${current_product['cost_price']:.2f}")
                calculated_sale = logic.calculate_sale_price(current_product['cost_price'])
                st.metric("Sale Price (Cost + 51%)", f"${calculated_sale:.2f}")
                st.metric("Current Stock", current_product['stock_quantity'])
            
            with prod_col3:
                st.caption("💡 Prices updated via PDF import")
                add_stock = st.number_input("Add Stock Quantity", min_value=0, value=0, key="edit_add_stock")
                if st.button("➕ Add Stock", type="primary"):
                    if add_stock > 0:
                        db.update_product(selected_code, stock_delta=add_stock)
                        st.success(f"Added {add_stock} units.")
                        st.rerun()
                    else:
                        st.warning("Enter a quantity > 0")

# ==========================================
# INTERFACE B: Restocking (Supply Order)
# ==========================================
with tab2:
    st.header("Restocking")
    st.info("� Gestión de pedidos de reposición. Agrega productos desde Stock & Pricing o importa un archivo de orden.")
    
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
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            if st.button("📄 Generate Order File", type="primary"):
                import datetime
                import uuid
                
                # Generate unique order ID
                order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
                timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                order_filename = f"order_{timestamp}.csv"
                order_filepath = os.path.join(config.LOG_DIR, order_filename)
                
                # Add order_id column to dataframe
                order_df['order_id'] = order_id
                
                # Save to CSV
                order_df.to_csv(order_filepath, index=False)
                st.success(f"Order saved: {order_filename}")
                st.info(f"📋 Order ID: **{order_id}**")
                st.session_state.last_order_file = order_filepath
        
        with btn_col2:
            if st.button("🗑️ Clear Order"):
                st.session_state.supply_order = []
                st.rerun()
    else:
        st.caption("No hay productos en el pedido actual. Agrega productos desde 📊 Stock & Pricing.")
    
    # Upload Order File Section
    st.markdown("---")
    st.subheader("📤 Import Order File")
    st.info("Upload a previously generated order CSV to add stock when products arrive.")
    
    uploaded_order = st.file_uploader("Upload Order CSV", type=["csv"], key="order_csv_upload")
    
    if uploaded_order:
        try:
            import_df = pd.read_csv(uploaded_order)
            
            # Validate required columns
            required_cols = ['code', 'quantity']
            if not all(col in import_df.columns for col in required_cols):
                st.error(f"CSV must contain columns: {required_cols}")
            elif 'order_id' not in import_df.columns:
                st.error("⚠️ This CSV doesn't have an Order ID. Only use order files generated by this system.")
            else:
                # Get the order_id (same for all rows)
                order_id = import_df['order_id'].iloc[0]
                
                # Check if order was already used
                if db.is_order_used(order_id):
                    st.error(f"❌ Order **{order_id}** was already redeemed. Cannot use the same order twice.")
                else:
                    st.success(f"Order file loaded: {len(import_df)} products")
                    st.info(f"📋 Order ID: **{order_id}**")
                    
                    # Preview
                    preview_cols = ['code', 'name', 'quantity'] if 'name' in import_df.columns else ['code', 'quantity']
                    st.dataframe(import_df[preview_cols], hide_index=True)
                    
                    total_items = int(import_df['quantity'].sum())
                    st.metric("Total Items to Add", total_items)
                    
                    if st.button("✅ Confirm & Add Stock", type="primary", key="confirm_import_order"):
                        # Mark order as used FIRST to prevent race conditions
                        if db.mark_order_used(order_id, total_items):
                            added_count = 0
                            for _, row in import_df.iterrows():
                                code = row['code']
                                qty = int(row['quantity'])
                                if db.update_product(code, stock_delta=qty):
                                    added_count += 1
                            st.success(f"✅ Stock updated! Order **{order_id}** processed ({added_count} products).")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ Order **{order_id}** was already redeemed (concurrent access prevented).")
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ==========================================
# INTERFACE C: Point of Sale (POS)
# ==========================================
with tab3:
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
            
            for prod in filtered_prods:
                sale_price = logic.calculate_sale_price(prod['cost_price'])
                
                # Calculate available quantity (stock - already in cart)
                in_cart_qty = sum(item['quantity'] for item in st.session_state.cart if item['code'] == prod['code'])
                available_qty = prod['stock_quantity'] - in_cart_qty
                
                # Skip if no stock available
                if available_qty <= 0:
                    continue
                
                st.markdown("---")
                prod_col1, prod_col2, prod_col3 = st.columns([1, 2, 1])
                
                with prod_col1:
                    # Product Image
                    image_shown = False
                    db_rel_path = prod.get('image_path')
                    
                    if db_rel_path:
                        db_rel_path = db_rel_path.replace('\\', '/')
                        abs_path = os.path.join(config.BASE_DIR, db_rel_path)
                        if os.path.exists(abs_path):
                            st.image(abs_path, width=150)
                            image_shown = True
                    
                    if not image_shown:
                        safe_code = prod['code'].replace('/', '-')
                        fallback_abs_path = os.path.join(config.STATIC_DIR, f"{safe_code}.jpg")
                        if os.path.exists(fallback_abs_path):
                            st.image(fallback_abs_path, width=150)
                            image_shown = True
                    
                    if not image_shown:
                        st.image("https://placehold.co/150x150?text=No+Image", width=150)
                
                with prod_col2:
                    st.markdown(f"**{prod['name']}**")
                    st.markdown(f"**Marca:** {prod.get('brand', 'N/A')}")
                    st.markdown(f"**Descripción:** {prod.get('description', 'Sin descripción')[:100]}")
                    st.markdown(f"**Precio de Venta:** :blue[${sale_price:.2f}]")
                    st.caption(f"Stock disponible: {available_qty}")
                
                with prod_col3:
                    qty_key = f"qty_{prod['code']}"
                    add_qty = st.number_input(
                        "Cantidad", 
                        min_value=1, 
                        max_value=available_qty, 
                        value=1, 
                        key=qty_key
                    )
                    
                    btn_key = f"add_{prod['code']}"
                    if st.button("🛒 Agregar al Carrito", key=btn_key, type="primary"):
                        # Add item to cart
                        existing = next((item for item in st.session_state.cart if item['code'] == prod['code']), None)
                        if existing:
                            existing['quantity'] += add_qty
                        else:
                            st.session_state.cart.append({
                                'code': prod['code'],
                                'name': prod['name'],
                                'brand': prod['brand'],
                                'sale_price': sale_price,
                                'quantity': add_qty
                            })
                        st.toast(f"Agregado {add_qty}x {prod['name']} al carrito")
                        st.rerun()

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

