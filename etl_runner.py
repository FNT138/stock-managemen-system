import sys
import os
import argparse
import logic

# Force unbuffered stdout so Streamlit receives updates immediately
sys.stdout.reconfigure(line_buffering=True)

def update_progress(current, total):
    """
    Print progress in a format we can parse:
    PROGRESS:current:total
    """
    print(f"PROGRESS:{current}:{total}")

def main():
    parser = argparse.ArgumentParser(description="Run ETL Pipeline")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    args = parser.parse_args()
    
    pdf_path = args.pdf_path
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: File not found: {pdf_path}")
        sys.exit(1)
        
    try:
        print("STATUS:Starting ETL...")
        count = logic.run_etl_pipeline(pdf_path, progress_callback=update_progress)
        print(f"RESULT:SUCCESS:{count}")
    except Exception as e:
        print(f"RESULT:ERROR:{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
