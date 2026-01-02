#!/bin/bash
echo "========================================"
echo "  Stock Management System - Bicicleteria"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d ".stock" ]; then
    echo "[!] Virtual environment not found. Creating..."
    python3 -m venv .stock
    source .stock/bin/activate
    pip install -r requirements.txt
else
    source .stock/bin/activate
fi

echo ""
echo "[*] Starting application..."
echo "[*] Opening browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Open browser after 3 seconds (works on most Linux desktops)
(sleep 3 && xdg-open http://localhost:8501 2>/dev/null || open http://localhost:8501 2>/dev/null) &

# Run Streamlit
streamlit run app.py --server.headless true
