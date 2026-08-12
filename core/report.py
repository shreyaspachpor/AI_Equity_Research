"""
Report renderer — ReportData -> HTML (Jinja2) -> PDF (WeasyPrint).
=================================================================

The template/CSS live in ../templates and recreate the Geojit sample layout.
This module wires the data + rendered charts into the template and produces
the final PDF bytes for one-click download.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.charts import render_all
from core.schema import ReportData

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_DEFAULT_DISCLAIMER = (
    "This report is generated automatically from a company-provided financial document for "
    "demonstration purposes. It is not investment advice. Figures are extracted by an AI model "
    "and may contain errors; verify against the source document before relying on them."
)

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _value_or_blank(v: str) -> str:
    return v if (v and str(v).strip()) else "—"


_env.filters["blank"] = _value_or_blank


def render_html(data: ReportData) -> str:
    charts = render_all(data.charts)
    template = _env.get_template("report.html")
    return template.render(
        d=data,
        charts=charts,
        disclaimer=data.disclaimer.strip() or _DEFAULT_DISCLAIMER,
    )


def render_pdf(data: ReportData) -> bytes:
    """Render the report to PDF bytes using WeasyPrint or headless browser fallback."""
    html = render_html(data)
    try:
        from weasyprint import HTML
        return HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()
    except (Exception, OSError, ImportError) as exc:
        # Fallback for Windows without GTK3 system libraries installed
        import os
        import tempfile
        import subprocess

        browsers = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ]
        browser_bin = next((b for b in browsers if os.path.exists(b)), None)

        if not browser_bin:
            raise RuntimeError(f"WeasyPrint failed ({exc}) and no headless browser found for PDF generation.")

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "report.html")
            pdf_path = os.path.join(tmpdir, "report.pdf")
            css_path = os.path.join(tmpdir, "report.css")
            
            import shutil
            shutil.copy(os.path.join(str(_TEMPLATE_DIR), "report.css"), css_path)
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            cmd = [
                browser_bin,
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}",
                html_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
            raise RuntimeError("Headless PDF rendering failed.")


