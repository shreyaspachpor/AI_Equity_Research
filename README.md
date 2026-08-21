# AI Equity Research Report Generator

Upload a company's financial document (earnings release, investor presentation, or a CSV/TXT of financials) → an LLM extracts the key financials, metrics, and narrative → download a **Modern Dark Navy PDF research report** with tables, sections, key takeaways, and charts. Features real-time interactive AI chat for editing & auditing reports on the fly!

```
upload (PDF/CSV/TXT) → ingest → LLM extraction + InsightSentry API enrichment → dynamic charts → interactive editing/chat → HTML/CSS template → PDF
```

---

## Tech Stack

| Layer | Technology / Library |
|---|---|
| **Frontend UI** | **React (Vite)** — modern, dark-themed responsive UI with live PDF preview & streaming AI Chat |
| **Backend API** | **FastAPI** — high performance Python API server with Server-Sent Events (SSE) streaming |
| **Document Ingest** | **pypdf** (PDF text extraction), **pandas** (CSV ingestion), plain text (TXT) |
| **AI Extraction & Chat** | **LiteLLM** (configurable across OpenAI GPT-4o, Gemini, Anthropic, OpenRouter, Groq) with forced JSON schemas via **Pydantic** |
| **Market Data API** | **InsightSentry RapidAPI** — automatically fetches live market cap, P/E, 52-week highs/lows & financials |
| **Charts Engine** | **matplotlib** (rendered headless to base64 PNG images) |
| **PDF Generation** | **Jinja2** HTML/CSS → **WeasyPrint** (with MS Edge Headless printing fallback on Windows) |
| **Audit & Database** | **SQLite** (`result/audit.db`) — tracks report generations, enrichments, tool calls, and patch diffs |

---

## Core Features

* **Interactive AI Chat & Live Report Editing:** Chat with your generated report! Ask questions (queries) or instruct the AI to update specific metrics/sections (updates). Updates trigger surgical report patching and instantly re-render the PDF.
* **Automatic Market Data Enrichment:** Integrates with the InsightSentry API (`core/insight_api.py`) to search stock tickers and pull live market data (Market Cap, P/E, EPS, Current Price) to supplement raw document uploads.
* **Auditability & Diff Logging:** Every generation, market enrichment, and interactive edit is logged into an SQLite database (`result/audit.db`) along with before/after text patches and rationale.
* **Multi-Model Support:** Seamlessly switch between GPT-4o, Claude 3.5, Gemini 1.5, Groq, and OpenRouter models from the UI or backend.
* **Beautiful Dark Navy PDF Theme:** Custom edge-to-edge dark navy CSS print layout with teal/blue accents, structured financial tables, and embedded Matplotlib charts.
* **Missing Data Handled Gracefully:** If metrics (e.g. Target Price or Market Cap) are missing in raw earnings decks, the model intelligently substitutes relevant operational metrics (like NPA Ratios for banks).
* **Missing Chart Points:** Handles missing data points smoothly by converting null values into `NaN` visual gaps rather than breaking chart generation.
* **Robust Fallback PDF Engine:** If WeasyPrint system dependencies are absent (common on Windows), the renderer automatically falls back to Microsoft Edge Headless printing.
* **CLI Batch Processing:** Run `batch_process.py` to automatically ingest and generate PDF reports for an entire folder of documents.

---

## Single Source of Truth (`core/schema.py`)

Everything the report contains is defined strictly in [`core/schema.py`](core/schema.py) as the `ReportData` Pydantic model. That model serves as:
1. The **JSON schema contract** provided to the LLM during structured extraction.
2. The **data model rendered** by Jinja2 templates ([`templates/report.html`](templates/report.html) + [`templates/report.css`](templates/report.css)).
3. The **target schema patched** during interactive AI chat updates.

To add new fields or sections, simply update `core/schema.py` and [`templates/report.html`](templates/report.html). Financial statements, shareholding tables, and estimates are modeled generically as `Table` (title + columns + rows), supporting arbitrary datasets without code changes.

---

## Setup & Quick Start

Requires Python 3.10+ and Node.js (for React/Vite frontend).

### 1. Setup Python Environment
```bash
python -m venv venv
.\venv\Scripts\activate   # On Windows (or source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and add your API keys:
```bash
cp .env.example .env
```
Key configuration settings in `.env`:
* `OPENAI_API_KEY` (or `OPENROUTER_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY`)
* `INSIGHTENTRY_KEY` (optional: RapidAPI key for automatic stock market enrichment)

### 3. Run the Application
```bash
python start.py
```
This single command automatically launches both the **FastAPI Backend** (port 8000) and the **Vite React Frontend** (port 5173 / mounted static production server). 

Open your browser to **`http://localhost:8000`** (or `http://localhost:5173` during frontend development).

---

## Batch Processing (CLI)

To process a directory of financial PDFs in bulk without using the web UI:

1. Copy your document files (`.pdf`, `.csv`, `.txt`) into the `input/` folder.
2. Execute the batch runner:
```bash
python batch_process.py
```
3. Processed PDF reports will be written to the `result/` directory.

---

## Project Structure

```
AI-Report-Generator/
├── frontend/               # React (Vite) dark navy UI source & components
├── server.py               # FastAPI backend with REST & SSE endpoints
├── start.py                # Concurrent launcher for backend & frontend
├── batch_process.py        # CLI script for bulk document processing
├── core/
│   ├── schema.py           # ReportData — single source of truth (Pydantic)
│   ├── ingest.py           # Ingestion for PDF, CSV, and TXT files
│   ├── extractor.py        # LiteLLM extraction pipeline with Pydantic validation
│   ├── insight_api.py      # InsightSentry RapidAPI integration for market stats
│   ├── audit.py            # SQLite audit database logger (audit.db)
│   ├── update.py           # Surgical Pydantic report updater & MCP verification
│   ├── chat.py             # Intent classifier (Query vs Update) & SSE router
│   ├── charts.py           # Matplotlib base64 chart renderer
│   └── report.py           # Jinja2 HTML rendering + WeasyPrint/Edge PDF fallback
├── templates/
│   ├── report.html         # Jinja2 HTML report layout
│   └── report.css          # Dark Navy print-optimized styling
├── tests/
│   └── test_core.py        # Pytest suite for core processing pipeline
├── input/                  # Input directory for CLI batch processing
└── result/                 # Generated PDF reports, audit.db, and debug artifacts
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Checks system status, default model, and active API keys |
| `GET` | `/api/samples` | Lists pre-loaded sample company documents |
| `POST` | `/api/generate` | Ingests document/sample, extracts data, enriches, and generates PDF |
| `GET` | `/api/download/{report_id}` | Downloads/streams the generated PDF report |
| `POST` | `/api/chat/{report_id}` | SSE streaming AI chat endpoint for Q&A and live report editing |

---

## Testing

Run unit tests using pytest:
```bash
python -m pytest
```

---

## Notes & Guidelines

* **AI Extraction Verification:** Figures and tables are extracted by LLMs. Always cross-verify financial metrics against official primary regulatory filings before making investment decisions.
* **Missing Target Prices:** Company earnings decks rarely include target prices or analyst ratings. When these are missing, header cards automatically display primary key operational indicators.
