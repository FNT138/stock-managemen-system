import streamlit as st
import pandas as pd
import database as db
import logic
import os

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
tab1, tab2, tab3 = st.tabs(["Stock & Pricing (Manager)", "Supply Order (Restock)", "Point of Sale (POS)"])

# ==========================================
# INTERFACE A: Stock & Pricing Management
# ==========================================
with tab1:
    st.header("Manager View")
    
    # PDF Import
    st.subheader("Import Catalog")
    uploaded_pdf = st.file_uploader("Upload Supplier PDF", type=["pdf"])
    if uploaded_pdf:
        if st.button("Parse and Update Database"):
             with st.spinner("Parsing PDF..."):
                 # Save temporary file for parsing
                 temp_path = f"temp_{uploaded_pdf.name}"
                 with open(temp_path, "wb") as f:
                     f.write(uploaded_pdf.getbuffer())
                 
                 products = logic.parse_pdf_catalog(temp_path)
                 os.remove(temp_path)
                 
                 if products:
                     count = 0
                     for p in products:
                         # Default dummy values for missing info
                         if db.add_product(p['code'], p['name'], p['brand'], p['cost_price']):
                             count += 1
                     st.success(f"Successfully processed. Added {count} new products.")
                     st.rerun()
                 else:
                     st.warning("No products found or PDF format not recognized.")

    st.divider()
    
    # Database Table
    st.subheader("Product Database")
    all_products = db.get_all_products()
    if all_products:
        df = pd.DataFrame(all_products)
        # Display simplified table
        st.dataframe(df[['code', 'name', 'brand', 'cost_price', 'stock_quantity']], use_container_width=True)
        
        # Edit Product Section
        st.subheader("Edit Product")
        col1, col2 = st.columns(2)
        with col1:
            selected_code = st.selectbox("Select Product to Edit", options=df['code'], format_func=lambda x: f"{x} - {df[df['code']==x]['name'].iloc[0]}")
        
        if selected_code:
            current_product = db.get_product(selected_code)
            
            with col2:
                st.info(f"Selected: {current_product['name']}")
                
            c_col1, c_col2, c_col3 = st.columns(3)
            with c_col1:
                new_cost = st.number_input("Cost Price", value=current_product['cost_price'])
                calculated_sale = logic.calculate_sale_price(new_cost)
                st.metric("New Sale Price (Cost + 51%)", f"${calculated_sale}")
                if st.button("Update Price"):
                    db.update_product(selected_code, cost_price=new_cost)
                    st.success("Price updated!")
                    st.rerun()
            
            with c_col2:
                add_stock = st.number_input("Add Stock Quantity", min_value=0, value=0)
                if st.button("Add Stock"):
                    db.update_product(selected_code, stock_delta=add_stock)
                    st.success(f"Added {add_stock} units.")
                    st.rerun()
            
            with c_col3:
                st.image("https://placehold.co/150x150?text=No+Image", caption="Product Image", width=150) # Placeholder

# ==========================================
# INTERFACE B: Supply Order
# ==========================================
with tab2:
    st.header("Restocking Plan")
    
    st.info("Select quantities to order.")
    if all_products:
        df_restock = pd.DataFrame(all_products)
        df_restock['Order Qty'] = 0
        
        # Use data editor to allow editing 'Order Qty'
        edited_df = st.data_editor(
            df_restock[['code', 'name', 'brand', 'stock_quantity', 'cost_price', 'Order Qty']],
            column_config={
                "Order Qty": st.column_config.NumberColumn(
                    "Order Qty",
                    help="Quantity to order",
                    min_value=0,
                    step=1,
                    required=True,
                ),
                 "cost_price": st.column_config.NumberColumn(
                    "Cost Price",
                    format="$%.2f",
                )
            },
            disabled=["code", "name", "brand", "stock_quantity", "cost_price"],
            hide_index=True,
            use_container_width=True
        )
        
        # Calculate totals
        to_order = edited_df[edited_df['Order Qty'] > 0]
        
        if not to_order.empty:
            st.divider()
            st.subheader("Order Summary")
            st.dataframe(to_order[['code', 'name', 'Order Qty', 'cost_price']])
            
            total_order_cost = (to_order['Order Qty'] * to_order['cost_price']).sum()
            st.metric("Total Order Cost", f"${total_order_cost:,.2f}")
            
            if st.button("Export to CSV"):
                csv = to_order.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Order CSV",
                    data=csv,
                    file_name='supply_order.csv',
                    mime='text/csv',
                )

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
            # Filter
            filtered_prods = [
                p for p in all_products 
                if search_query.lower() in p['name'].lower() 
                or search_query.lower() in str(p['brand']).lower() 
                or search_query.lower() in str(p['code']).lower()
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
                            st.markdown(f'''
                                <div class="product-card">
                                    <h5>{prod['name']}</h5>
                                    <p class="price-tag">${sale_price}</p>
                                    <small>{prod['brand']}</small><br>
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

