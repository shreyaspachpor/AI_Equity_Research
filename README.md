# AI Equity Research Report Generator

Upload a company's financial document (earnings release, investor presentation, or a CSV/TXT of financials) → an LLM extracts the key financials, metrics, and narrative → download a **Modern Dark Navy PDF research report** with tables, sections, paragraphs, and charts.

```
upload (PDF/CSV/TXT)  →  ingest  →  LLM extraction (structured)  →  charts  →  HTML template  →  PDF
```

---

## Tech Stack

| Layer | Library |
|---|---|
| **Frontend UI** | **React (Vite)** — clean, modern, and highly responsive |
| **Backend API** | **FastAPI** — high performance Python server |
| **Document Ingest** | **pypdf** (PDF text), **pandas** (CSV), plain read (TXT) |
| **AI Extraction** | **GPT-4o** via LiteLLM (configurable to Anthropic, Gemini, Mistral, Ollama, etc.) utilizing forced JSON function calling → validated by **Pydantic** |
| **Charts** | **matplotlib** (rendered headless to base64 PNG) |
| **PDF Generation** | **Jinja2** HTML/CSS → **WeasyPrint** (with MS Edge Headless printing fallback on Windows) |

---

## Where the template fields are defined

Everything the report can contain is defined **once** in [`core/schema.py`](core/schema.py) as the `ReportData` Pydantic model. That model is simultaneously:

* the **contract the LLM fills** (its JSON schema is handed to the model as a tool/function), and
* the **data the template renders** ([`templates/report.html`](templates/report.html) + [`templates/report.css`](templates/report.css)).

To add a new field or section, edit `core/schema.py` and `templates/report.html` — no other code changes. Financial statements, shareholding, estimates, etc. are all modelled as a generic `Table` (title + columns + rows), so a new table for a new company needs **zero** code changes.

---

## Setup & Running the App

Requires Python 3.10+ and an API key (OPENAI_API_KEY for the default gpt-4o, or others if configured).

**1. Setup Environment**
```bash
python -m venv venv
.\venv\Scripts\activate   # On Windows
pip install -r requirements.txt
```

**2. Add your API Keys**
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

**3. Run the application**
```bash
python start.py
```
This single command automatically starts both the **FastAPI Backend** (port 8000) and the **Vite React Frontend**! 

Open your browser to `http://localhost:8000` (FastAPI automatically mounts the built frontend). Upload your PDF, enter a company name, and click Generate.

---

## Batch Processing (CLI)

If you have multiple PDFs that you want to process automatically without using the UI, you can use the batch script!

1. Place all your PDFs into the `input/` directory.
2. Run the script:
```bash
python batch_process.py
```
3. The AI will process them one-by-one and save the beautifully styled Dark Navy PDFs into the `result/` directory.

---

## Features

* **Beautiful Dark Navy Theme:** The PDF renderer utilizes a modern, edge-to-edge dark navy theme with vibrant blue and teal accents.
* **Missing Data Handled Gracefully:** If the AI cannot find a piece of information (e.g. Market Cap or Target Price on a raw earnings deck), it will intelligently swap it out for the most important operational metrics it *can* find (like NPA Ratios for Banks).
* **Missing Chart Points:** If a chart has a missing year, the parser smoothly converts the null to a `NaN` gap on the Matplotlib chart instead of crashing.
* **Robust Fallback:** If WeasyPrint is missing system libraries (common on Windows), the app seamlessly falls back to headless Microsoft Edge to render the PDF perfectly.
* **Unit Tested:** Core modules are fully covered by a clean `pytest` suite (`python -m pytest`).

---

## Project Structure

```
research-report-generator/
├── frontend/               # React (Vite) UI source
├── server.py               # FastAPI backend API routes
├── start.py                # Wrapper to start both backend & frontend
├── batch_process.py        # CLI script to process multiple PDFs at once
├── core/
│   ├── schema.py           # ReportData — single source of truth for template fields
│   ├── ingest.py           # PDF / CSV / TXT → normalised text
│   ├── extractor.py        # LLM tool-use (via LiteLLM) → validated ReportData
│   ├── charts.py           # ChartSpec → base64 PNG (matplotlib)
│   └── report.py           # Jinja2 render + WeasyPrint/Edge fallback → PDF bytes
├── templates/
│   ├── report.html         # Jinja2 HTML layout
│   └── report.css          # Dark Navy CSS Theme
├── tests/
│   └── test_core.py        # Unit tests (pytest)
├── input/                  # Place PDFs here for batch_process.py
└── result/                 # Generated PDF outputs land here
```

## Notes & Limitations

* Raw company filings (investor presentations) carry no analyst rating/target/CMP, so those header fields render blank — by design. The AI is explicitly instructed *not* to invent financial predictions. Feed it a broker note to populate them.
* Figures are AI-extracted — always verify against the source before making any real financial decisions.
