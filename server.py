"""
FastAPI Backend Server for AI Equity Research Report Generator
===============================================================
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from core.ingest import ingest
from core.extractor import extract_report, missing_keys_for, DEFAULT_MODEL
from core.report import render_pdf
from core.charts import render_all

app = FastAPI(title="AI Research Report Generator API")

# Enable CORS for Vite frontend (default port 5173 / 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = Path(__file__).resolve().parent
RESULT_DIR = WORKSPACE_DIR / "result"
RESULT_DIR.mkdir(exist_ok=True)

# Static samples mapping
SAMPLE_FILES = {
    "ICICI Bank": WORKSPACE_DIR / "ICICI Q2FY26.pdf",
    "JSW Energy": WORKSPACE_DIR / "JSW Energy Q2FY26.pdf",
    "LTTS": WORKSPACE_DIR / "LTTS Q2FY26.pdf",
    "POCL": WORKSPACE_DIR / "POCL Q2FY26.pdf",
    "Eternal (Zomato)": WORKSPACE_DIR / "Eternal-Geojit.pdf",
    "Sample Financials (CSV)": WORKSPACE_DIR / "test_data" / "sample_financials.csv",
}

# Cache stored generated reports: id -> file_path
GENERATED_REPORTS = {}

@app.get("/api/health")
def health_check(model: str = DEFAULT_MODEL):
    missing = missing_keys_for(model)
    return {
        "status": "ok",
        "default_model": DEFAULT_MODEL,
        "selected_model": model,
        "missing_keys": missing,
        "api_key_status": {
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")),
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "GROQ_API_KEY": bool(os.getenv("GROQ_API_KEY")),
            "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
        }
    }


@app.get("/api/samples")
def list_samples():
    samples = []
    for name, path in SAMPLE_FILES.items():
        if path.exists():
            samples.append({
                "name": name,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "type": path.suffix.replace(".", "").upper()
            })
    return {"samples": samples}

@app.post("/api/generate")
async def generate_report(
    company_name: str = Form(""),
    model: str = Form(DEFAULT_MODEL),
    sample_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        filename = ""
        file_bytes = b""

        if file and file.filename:
            filename = file.filename
            file_bytes = await file.read()
        elif sample_name and sample_name in SAMPLE_FILES:
            sample_path = SAMPLE_FILES[sample_name]
            if not sample_path.exists():
                raise HTTPException(status_code=404, detail=f"Sample file {sample_name} not found.")
            filename = sample_path.name
            file_bytes = sample_path.read_bytes()
        else:
            raise HTTPException(
                status_code=400, detail="Please upload a document or select a sample company document."
            )

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Provided document is empty.")

        # Step 1: Ingest document
        doc = ingest(filename, file_bytes)
        
        report_id = str(uuid.uuid4())

        # Step 2: AI extraction
        effective_company = company_name if company_name and company_name != "Other…" else sample_name or ""
        report_data = extract_report(doc, effective_company, model=model, report_id=report_id)
        
        from core.audit import log_report_generation
        log_report_generation(report_id, report_data.company_name or effective_company, model, report_data.model_dump())

        # Step 3: Render charts as base64 images for frontend preview
        charts_b64 = render_all(report_data.charts)

        # Step 4: Render PDF
        pdf_bytes = render_pdf(report_data)

        safe_name = (report_data.company_name or effective_company or "research_report").replace(" ", "_")
        pdf_filename = f"{safe_name}_{report_id[:8]}.pdf"
        out_path = RESULT_DIR / pdf_filename
        out_path.write_bytes(pdf_bytes)

        GENERATED_REPORTS[report_id] = {
            "path": out_path,
            "filename": pdf_filename,
            "display_name": f"{report_data.company_name or 'Research'}_report.pdf",
            "data": report_data.model_dump()
        }

        return {
            "success": True,
            "report_id": report_id,
            "pdf_filename": pdf_filename,
            "data": report_data.model_dump(),
            "charts_b64": charts_b64,
            "download_url": f"/api/download/{report_id}",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{report_id}")
def download_report(report_id: str):
    if report_id in GENERATED_REPORTS:
        info = GENERATED_REPORTS[report_id]
        filepath = info["path"]
        if filepath.exists():
            return FileResponse(
                path=filepath,
                media_type="application/pdf",
                filename=info["display_name"],
                content_disposition_type="inline"
            )
    
    # Try looking in RESULT_DIR directly
    for pdf_file in RESULT_DIR.glob("*.pdf"):
        if report_id in pdf_file.name:
            return FileResponse(
                path=pdf_file,
                media_type="application/pdf",
                filename=pdf_file.name,
                content_disposition_type="inline"
            )

    raise HTTPException(status_code=404, detail="Report PDF not found.")

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat/{report_id}")
async def chat_with_report(report_id: str, req: ChatRequest, model: str = DEFAULT_MODEL):
    if report_id not in GENERATED_REPORTS:
        raise HTTPException(status_code=404, detail="Report not found in memory.")
    
    from core.chat import answer_chat
    from core.schema import ReportData
    from core.report import render_pdf
    from fastapi.responses import StreamingResponse
    import json
    
    report_data = GENERATED_REPORTS[report_id]["data"]
    
    async def event_generator():
        try:
            async for chunk in answer_chat(req.message, report_data, model):
                if chunk.get("type") == "done" and chunk.get("updated"):
                    # The data was surgically updated, we must regenerate the PDF
                    new_data = chunk.get("updated_data", report_data)
                    GENERATED_REPORTS[report_id]["data"] = new_data
                    
                    try:
                        report_obj = ReportData(**new_data)
                        pdf_bytes = render_pdf(report_obj)
                        out_path = GENERATED_REPORTS[report_id]["path"]
                        out_path.write_bytes(pdf_bytes)
                    except Exception as e:
                        chunk["reply"] += f"\n\n*(Error regenerating PDF: {e})*"
                
                # Yield as Server-Sent Event
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount frontend static files if built in production
FRONTEND_DIST = WORKSPACE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
