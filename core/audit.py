import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

DB_PATH = Path(__file__).resolve().parent.parent / "result" / "audit.db"
IST = timezone(timedelta(hours=5, minutes=30))

def _get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite database with required tables."""
    conn = _get_conn()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            company_name TEXT,
            model TEXT,
            timestamp DATETIME,
            data JSON
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS enrichments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT,
            status TEXT,
            fallback_used BOOLEAN,
            timestamp DATETIME
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS updates (
            id TEXT PRIMARY KEY,
            report_id TEXT,
            claims JSON,
            decisions JSON,
            outcome TEXT,
            timestamp DATETIME,
            mcp_tool_calls JSON
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS patches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            update_id TEXT,
            section_id TEXT,
            before_text TEXT,
            after_text TEXT,
            rationale TEXT,
            evidence TEXT,
            timestamp DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

def log_report_generation(report_id: str, company_name: str, model: str, data: dict):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO reports (id, company_name, model, timestamp, data)
        VALUES (?, ?, ?, ?, ?)
    ''', (report_id, company_name, model, datetime.now(IST), json.dumps(data)))
    conn.commit()
    conn.close()

def log_enrichment(report_id: str, status: str, fallback_used: bool):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO enrichments (report_id, status, fallback_used, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (report_id, status, fallback_used, datetime.now(IST)))
    conn.commit()
    conn.close()

def log_update_run(
    update_id: str, 
    report_id: str, 
    claims: list, 
    decisions: list, 
    outcome: str,
    mcp_tool_calls: list,
    patches: list
):
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.now(IST)
    
    c.execute('''
        INSERT INTO updates (id, report_id, claims, decisions, outcome, timestamp, mcp_tool_calls)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        update_id, 
        report_id, 
        json.dumps(claims), 
        json.dumps(decisions), 
        outcome, 
        now, 
        json.dumps(mcp_tool_calls)
    ))
    
    for patch in patches:
        c.execute('''
            INSERT INTO patches (update_id, section_id, before_text, after_text, rationale, evidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            update_id,
            patch.get('section_id', ''),
            patch.get('before_text', ''),
            patch.get('after_text', ''),
            patch.get('rationale', ''),
            patch.get('evidence', ''),
            now
        ))
        
    conn.commit()
    conn.close()

# Initialize on import
init_db()
