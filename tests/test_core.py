import pytest
import os
import base64
from pathlib import Path

from core.schema import ReportData, ChartSpec, ChartSeries, Table, TableRow
from core.ingest import ingest
from core.charts import render_chart, render_all

def test_schema_validation():
    data = ReportData(
        company_name="Test Corp",
        sector="Technology",
        report_date="Oct 10, 2025"
    )
    assert data.company_name == "Test Corp"
    assert data.sector == "Technology"
    assert data.report_date == "Oct 10, 2025"

def test_chart_series_missing_data():
    series = ChartSeries(name="Revenue", y=[10.5, None, 12.5])
    assert series.name == "Revenue"
    assert series.y == [10.5, None, 12.5]

def test_render_chart():
    spec = ChartSpec(
        title="Test Line",
        kind="line",
        x=["Q1", "Q2", "Q3"],
        series=[ChartSeries(name="Rev", y=[10.5, None, 12.5])]
    )
    b64 = render_chart(spec)
    assert b64 is not None
    assert isinstance(b64, str)
    decoded = base64.b64decode(b64)
    assert decoded.startswith(b"\x89PNG")

def test_render_chart_empty():
    spec = ChartSpec(title="Empty", x=[], series=[])
    b64 = render_chart(spec)
    assert b64 is None

def test_render_all():
    specs = [
        ChartSpec(title="A", x=["A"], series=[ChartSeries(name="1", y=[1.0])]),
        ChartSpec(title="B", x=[], series=[])
    ]
    results = render_all(specs)
    assert len(results) == 1
    assert results[0]["title"] == "A"
    assert "b64" in results[0]

def test_ingest_txt():
    content = b"This is a test document for text extraction that is sufficiently long to pass the usable text threshold of 150 characters. " * 5
    doc = ingest("test.txt", content)
    assert doc.fmt == "txt"
    assert doc.has_usable_text is True

def test_ingest_csv():
    content = b"Year,Revenue\n2023,100\n2024,150\n" * 20
    doc = ingest("data.csv", content)
    assert doc.fmt == "csv"
    assert doc.has_usable_text is True
    assert "Year" in doc.text and "Revenue" in doc.text

def test_table_schema():
    row = TableRow(label="Row1", cells=["A", "B"])
    table = Table(title="Test", columns=["Col1", "Col2"], rows=[row])
    assert table.title == "Test"
    assert len(table.columns) == 2
    assert table.rows[0].label == "Row1"
