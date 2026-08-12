import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import core modules
from core.ingest import ingest
from core.extractor import extract_report
from core.report import render_pdf

def main():
    workspace_dir = Path(__file__).resolve().parent
    input_dir = workspace_dir / "input"
    result_dir = workspace_dir / "result"
    
    # Create directories if they don't exist
    input_dir.mkdir(exist_ok=True)
    result_dir.mkdir(exist_ok=True)
    
    # Find all PDFs in the input directory
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        print("Please place your financial PDF reports in the 'input' folder and run this script again.")
        return
        
    print(f"Found {len(pdf_files)} PDF(s) to process.\n")
    
    for pdf_path in pdf_files:
        print(f"Processing: {pdf_path.name}")
        try:
            # 1. Ingest the PDF
            file_bytes = pdf_path.read_bytes()
            doc = ingest(pdf_path.name, file_bytes)
            
            # Use the filename (without extension) as the fallback company name
            company_guess = pdf_path.stem
            
            # 2. Extract Data using AI
            print(f"  - Extracting financial data using AI (this may take a minute)...")
            report_data = extract_report(doc, company_name=company_guess, model="gpt-4o")
            
            # 3. Render the PDF with the Dark Navy styling
            print(f"  - Rendering beautifully styled PDF...")
            pdf_bytes = render_pdf(report_data)
            
            # 4. Save to results folder
            safe_name = (report_data.company_name or company_guess).replace(" ", "_")
            out_filename = f"{safe_name}_report.pdf"
            out_path = result_dir / out_filename
            
            out_path.write_bytes(pdf_bytes)
            print(f"  ✓ Success! Saved to: {out_path}\n")
            
        except Exception as e:
            print(f"  ✗ Failed to process {pdf_path.name}: {e}\n")
            
    print("Batch processing complete!")

if __name__ == "__main__":
    main()
