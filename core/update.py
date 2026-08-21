import json
import os
import uuid
import asyncio
import litellm
litellm.suppress_debug_info = True
import httpx
from datetime import datetime
from core.audit import log_update_run

async def call_mcp_http(method: str, params: dict = None) -> dict:
    url = "https://www.bull-ai.in/mcp"
    headers = {
        "Authorization": "Bearer bai_mcp_I2x0xX0J3_vkGCsuPXjqx9mgBakPDFx650nf8-iU_VA",
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method
    }
    if params:
        payload["params"] = params
        
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        if isinstance(data, list):
            data = data[0] if data else {}
            
        if isinstance(data, dict):
            return data.get("result", {})
        return {}

def _apply_patch(report_data: dict, patch: dict) -> bool:
    """Apply a patch to the report data using index-based targeting.
    Supported actions:
      - replace_value: replace a top-level string field
      - replace_item: replace a string item in a list by index
      - append_item: append a new string to a list
      - update_table_cell: update a cell in a financial table (needs table_index, row_index, col_index, new_value)
      - add_table_column: add a new column to a financial table (needs table_index, column_name, row_values)
      - update_dict_value: update a dict item's "value" in a list of dicts (e.g. company_data KeyValues)
    """
    section_id = patch.get("section_id", "")
    action = patch.get("action", "")
    new_value = patch.get("new_value", "")
    
    if not section_id or section_id not in report_data:
        return False
    
    val = report_data[section_id]
    
    if action == "replace_value" and isinstance(val, str):
        if not new_value:
            return False
        report_data[section_id] = new_value
        return True
        
    elif action == "replace_item" and isinstance(val, list):
        index = patch.get("index")
        if index is not None and isinstance(index, int) and 0 <= index < len(val):
            if isinstance(val[index], str) and new_value:
                val[index] = new_value
                return True
                
    elif action == "append_item" and isinstance(val, list):
        if new_value:
            val.append(new_value)
            return True
            
    elif action == "update_dict_value" and isinstance(val, list):
        # For company_data: list of {"label": ..., "value": ...}
        index = patch.get("index")
        if index is not None and isinstance(index, int) and 0 <= index < len(val):
            if isinstance(val[index], dict) and new_value:
                val[index]["value"] = new_value
                return True
    
    elif action == "update_table_cell" and isinstance(val, list):
        # For financials: list of tables, each with rows[].cells[]
        table_index = patch.get("table_index", patch.get("index"))
        row_index = patch.get("row_index")
        col_index = patch.get("col_index")
        if (table_index is not None and row_index is not None and col_index is not None
            and isinstance(table_index, int) and isinstance(row_index, int) and isinstance(col_index, int)):
            if 0 <= table_index < len(val):
                table = val[table_index]
                if isinstance(table, dict):
                    rows = table.get("rows", [])
                    if 0 <= row_index < len(rows):
                        row = rows[row_index]
                        if isinstance(row, dict):
                            cells = row.get("cells", [])
                            if 0 <= col_index < len(cells):
                                cells[col_index] = new_value
                                return True
                                
    elif action == "add_table_column" and isinstance(val, list):
        # Add a new column to a financial table
        table_index = patch.get("table_index", patch.get("index"))
        column_name = patch.get("column_name", "")
        row_values = patch.get("row_values", [])
        if table_index is not None and isinstance(table_index, int) and 0 <= table_index < len(val):
            table = val[table_index]
            if isinstance(table, dict) and column_name:
                table.get("columns", []).append(column_name)
                rows = table.get("rows", [])
                for i, row in enumerate(rows):
                    if isinstance(row, dict):
                        if "cells" not in row or not isinstance(row["cells"], list):
                            row["cells"] = []
                        cell_val = str(row_values[i]) if i < len(row_values) else ""
                        row["cells"].append(cell_val)
                return True

    elif action == "add_chart_data_point" and isinstance(val, list):
        # Add a new data point (e.g. Q1-2027) to a chart
        chart_index = patch.get("chart_index", patch.get("index"))
        x_label = patch.get("x_label", "")
        y_values = patch.get("y_values", [])
        if chart_index is not None and isinstance(chart_index, int) and 0 <= chart_index < len(val):
            chart = val[chart_index]
            if isinstance(chart, dict) and x_label:
                chart.get("x", []).append(x_label)
                series_list = chart.get("series", [])
                for i, s in enumerate(series_list):
                    if isinstance(s, dict):
                        y_val = y_values[i] if i < len(y_values) else None
                        s.get("y", []).append(y_val)
                return True

    elif action == "update_chart_point" and isinstance(val, list):
        # Update an existing data point in a chart
        chart_index = patch.get("chart_index", patch.get("index"))
        point_index = patch.get("point_index")
        x_label = patch.get("x_label", None)
        y_values = patch.get("y_values", [])
        if (chart_index is not None and point_index is not None
            and isinstance(chart_index, int) and isinstance(point_index, int)
            and 0 <= chart_index < len(val)):
            chart = val[chart_index]
            if isinstance(chart, dict):
                x_arr = chart.get("x", [])
                if 0 <= point_index < len(x_arr):
                    if x_label:
                        x_arr[point_index] = x_label
                    series_list = chart.get("series", [])
                    for i, s in enumerate(series_list):
                        if isinstance(s, dict):
                            y_arr = s.get("y", [])
                            if 0 <= point_index < len(y_arr) and i < len(y_values):
                                y_arr[point_index] = y_values[i]
                    return True

    elif action == "replace_chart_spec" and isinstance(val, list):
        chart_index = patch.get("chart_index", patch.get("index"))
        chart_dict = patch.get("chart_dict", {})
        if (chart_index is not None and isinstance(chart_index, int)
            and 0 <= chart_index < len(val) and isinstance(chart_dict, dict) and chart_dict):
            val[chart_index] = chart_dict
            return True
    
    return False

def _build_section_map(report_data: dict) -> str:
    """Build a human-readable map of the report structure showing section keys, types, and indexed items."""
    lines = ["REPORT STRUCTURE MAP (use these exact section_ids and indices for patching):"]
    lines.append("=" * 70)
    
    for key, val in report_data.items():
        if isinstance(val, str) and val:
            preview = val[:150].replace('\n', ' ')
            lines.append(f'\n[STRING] section_id="{key}"')
            lines.append(f'  Current value: "{preview}..."' if len(val) > 150 else f'  Current value: "{preview}"')
        elif isinstance(val, list) and val:
            if not val:
                lines.append(f'\n[EMPTY_LIST] section_id="{key}"')
                continue
            first = val[0]
            if isinstance(first, str):
                lines.append(f'\n[STRING_LIST] section_id="{key}" ({len(val)} items)')
                for i, item in enumerate(val):
                    if isinstance(item, str):
                        preview = item[:150].replace('\n', ' ')
                        lines.append(f'  [{i}] "{preview}..."' if len(item) > 150 else f'  [{i}] "{preview}"')
            elif isinstance(first, dict):
                if "rows" in first or "columns" in first:
                    # Table list (financials)
                    lines.append(f'\n[TABLE_LIST] section_id="{key}" ({len(val)} tables)')
                    for ti, table in enumerate(val):
                        if isinstance(table, dict):
                            title = table.get("title", "Untitled")
                            columns = table.get("columns", [])
                            rows = table.get("rows", [])
                            lines.append(f'  Table[{ti}] "{title}"')
                            lines.append(f'    Columns: {columns}')
                            for ri, row in enumerate(rows):
                                if isinstance(row, dict):
                                    label = row.get("label", "")
                                    cells = row.get("cells", [])
                                    lines.append(f'    Row[{ri}] "{label}": {cells}')
                elif "series" in first or "kind" in first:
                    # Chart list (charts)
                    lines.append(f'\n[CHART_LIST] section_id="{key}" ({len(val)} charts)')
                    for ci, chart in enumerate(val):
                        if isinstance(chart, dict):
                            title = chart.get("title", "Untitled")
                            x = chart.get("x", [])
                            series = chart.get("series", [])
                            lines.append(f'  Chart[{ci}] "{title}" (kind: {chart.get("kind","bar")})')
                            lines.append(f'    X-labels: {x}')
                            for s in series:
                                if isinstance(s, dict):
                                    lines.append(f'    Series "{s.get("name")}": {s.get("y")}')
                elif "label" in first:
                    # KeyValue list (company_data)
                    lines.append(f'\n[KEYVALUE_LIST] section_id="{key}" ({len(val)} items)')
                    for i, item in enumerate(val):
                        if isinstance(item, dict):
                            lines.append(f'  [{i}] {item.get("label","")}: {item.get("value","")}')
                else:
                    lines.append(f'\n[DICT_LIST] section_id="{key}" ({len(val)} items)')
                    for i, item in enumerate(val):
                        if isinstance(item, dict):
                            lines.append(f'  [{i}] keys: {list(item.keys())}')
    
    return "\n".join(lines)

async def process_update_batch(updates: list[str], report_data: dict, model: str) -> dict:
    if not os.getenv("OPENROUTER_API_KEY") and os.getenv("API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = os.getenv("API_KEY", "")
        
    update_id = str(uuid.uuid4())
    combined_updates = "\n".join(updates)
    mcp_tool_calls = []
    
    # --- 1. Detect if research is needed ---
    conflict_prompt = f"""You are an intent analyzer for an equity research report update pipeline.
Here is the current structured data of the report:
{json.dumps(report_data, indent=2)}

Here is the user's message:
{combined_updates}

Analyze the user's message against the current report.
Identify if the user's message requires external research to verify or retrieve data. 
This is true if ANY of the following apply:
1. The user provides new numbers/claims that conflict with the report.
2. The user asks to update a metric, field, or section without providing the exact new numbers (e.g., "update the revenue", "fix the profit numbers").
3. The user requests to refresh the data to the latest period.

Return a JSON object with this exact structure:
{{
    "requires_research": true/false,
    "claims": ["List of all material claims or data points requested by the user"],
    "research_reason": ["Explanation of why research is needed"]
}}
Return ONLY valid JSON.
"""
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": conflict_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        result_str = resp.choices[0].message.content
        conflict_result = json.loads(result_str)
        has_conflict = conflict_result.get("requires_research", False)
        claims = conflict_result.get("claims", [])
        
        mcp_messages = []
        final_verification_notes = ""
        mcp_reasoning = ""
        
        # --- 2. MCP Verification Loop (Only if research required) ---
        if has_conflict:
            list_res = await call_mcp_http("tools/list")
            mcp_tools = list_res.get("tools", [])
            llm_tools = []
            
            for t in mcp_tools:
                schema = t.get("inputSchema", {})
                for forbidden_key in ["allOf", "anyOf", "oneOf", "not"]:
                    if forbidden_key in schema:
                        del schema[forbidden_key]
                if schema.get("type") != "object":
                    schema["type"] = "object"
                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description", ""),
                        "parameters": schema
                    }
                })
            
            company_data = report_data.get('company_data', {})
            if isinstance(company_data, list):
                company_data = company_data[0] if company_data else {}
            company_name_context = company_data.get('company_name', 'the company')
            
            yield {"type": "status", "message": "🚨 Research Required! Invoking Bull AI MCP..."}
            
            verification_prompt = f"""You are an expert equity research agent retrieving the latest financial data for a company.

Company in the report: {report_data.get('company_name', 'Unknown')}

User's Request: {combined_updates}

Reason for Research:
{json.dumps(conflict_result.get('research_reason', []), indent=2)}

You have access to the Bull AI MCP tools. Follow this workflow:
1. Call `search_companies` with the company name to get the identifier.
2. Call `search_company_documents` with the identifier and a query matching the user's request (e.g. "Q1 FY27 financial highlights earnings profit").

The search results will contain document EXCERPTS with actual financial data in them (e.g. "Profit after tax grew by 15.9% y-o-y to ₹148.05 bn").
Extract ALL numerical data directly from these excerpts. The excerpts ARE the source of truth.

If you need more detail, you can optionally call `get_document_chunks` with the document_id from the source URL and the specific page numbers. But often the search excerpts already have everything you need.

When you are done, return a final text summary listing ALL key financial metrics you found with their EXACT numerical values. Be specific — list every number.
Include the Markdown hyperlink to the source document (e.g., "Source: [Investor Presentation Q1 FY27](url)").
"""
            mcp_messages = [{"role": "user", "content": verification_prompt}]
            
            for loop_i in range(6):
                yield {"type": "status", "message": f"🔄 MCP tool loop iteration {loop_i + 1}..."}
                
                mcp_resp = await litellm.acompletion(
                    model=model,
                    messages=mcp_messages,
                    tools=llm_tools,
                    tool_choice="auto",
                    temperature=0.1,
                )
                mcp_msg = mcp_resp.choices[0].message
                msg_content = mcp_msg.content or ""
                
                # Collect reasoning from tool-call model
                rc = getattr(mcp_msg, "reasoning_content", None)
                if not rc:
                    extra = getattr(mcp_msg, "model_extra", {}) or {}
                    psf = extra.get("provider_specific_fields", {})
                    rc = psf.get("reasoning", "")
                if rc:
                    mcp_reasoning += rc + "\n"
                    yield {"type": "chunk", "content": "", "reasoning": rc + "\n"}
                
                mcp_messages.append(mcp_msg)
                
                if mcp_msg.tool_calls:
                    for tool_call in mcp_msg.tool_calls:
                        func_name = tool_call.function.name
                        func_args = json.loads(tool_call.function.arguments)
                        
                        mcp_tool_calls.append({"tool": func_name, "args": func_args})
                        yield {"type": "status", "message": f"🔧 Calling MCP tool: {func_name}..."}
                        
                        mcp_result = await call_mcp_http("tools/call", {"name": func_name, "arguments": func_args})
                        
                        content_parts = mcp_result.get("content", [])
                        content_str = "\n".join(
                            p.get("text", "") for p in content_parts if isinstance(p, dict) and p.get("type") == "text"
                        ) if isinstance(content_parts, list) else str(content_parts)
                        
                        print(f"\n[MCP Result for {func_name}]:\n{content_str}\n")
                        yield {"type": "chunk", "content": "", "reasoning": f"\n[MCP Result for {func_name}]:\n{content_str}\n\n"}
                        
                        mcp_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content_str if content_str else "No content returned."
                        })
                else:
                    final_verification_notes = msg_content
                    break
        else:
            final_verification_notes = "No conflicts detected. MCP not invoked."
            
        # --- 3. Final Explicit Routing Decision with Index-Based Patching ---
        section_map = _build_section_map(report_data)
        
        schema_def = {
            "type": "object",
            "properties": {
                "patches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "decision": {"type": "string", "enum": ["apply", "skip"]},
                            "rationale": {"type": "string"},
                            "section_id": {"type": "string"},
                            "action": {"type": "string", "enum": [
                                "replace_item", "replace_value", "append_item",
                                "update_table_cell", "add_table_column", "add_table_row", "update_dict_value",
                                "add_chart_data_point", "update_chart_point", "replace_chart_spec"
                            ]},
                            "index": {"type": "integer"},
                            "table_index": {"type": "integer"},
                            "row_index": {"type": "integer"},
                            "col_index": {"type": "integer"},
                            "chart_index": {"type": "integer"},
                            "point_index": {"type": "integer"},
                            "column_name": {"type": "string"},
                            "row_label": {"type": "string"},
                            "x_label": {"type": "string"},
                            "row_values": {"type": "array", "items": {"type": "string"}},
                            "y_values": {"type": "array", "items": {"type": "number"}},
                            "new_value": {"type": "string"}
                        },
                        "required": ["decision", "rationale", "section_id", "action"]
                    }
                }
            },
            "required": ["patches"]
        }
        
        routing_prompt = f"""You are the final update routing engine for an equity research report.

USER REQUEST:
{combined_updates}

MCP RESEARCH FINDINGS:
{final_verification_notes}

{section_map}

---

Based on the MCP research findings above, generate patches to update the report with the new data.

AVAILABLE ACTIONS:

1. For STRING fields (like "description", "thesis", "report_date"):
   - action: "replace_value", section_id, new_value

2. For STRING_LIST fields (like "highlights", "key_highlights"):
   - action: "replace_item", section_id, index (integer), new_value
   - action: "append_item", section_id, new_value

3. For TABLE_LIST fields (like "financials" - Table[0] P&L, Table[1] Balance Sheet, Table[2] Key Ratios):
   To update an existing cell:
   - action: "update_table_cell", section_id: "financials", table_index, row_index, col_index, new_value
   To add a new column (e.g. adding Q1-2027 data):
   - action: "add_table_column", section_id: "financials", table_index, column_name (e.g. "Q1-2027"), row_values (array of strings, one per row)
   To add a new row (e.g. adding a new line item):
   - action: "add_table_row", section_id: "financials", table_index, row_label (e.g. "Advances"), row_values (array of strings for each column)

4. For CHART_LIST fields ("charts"):
   To add a new data point to a chart (e.g. Q1-2027):
   - action: "add_chart_data_point", section_id: "charts", chart_index, x_label (e.g. "Q1-2027"), y_values (array of numbers, e.g. [216.35] for each series)
   To update an existing chart data point:
   - action: "update_chart_point", section_id: "charts", chart_index, point_index, x_label, y_values

5. For KEYVALUE_LIST fields (like "company_data"):
   - action: "update_dict_value", section_id, index, new_value

Each patch object must have:
- "decision": "apply" or "skip"
- "rationale": why
- Plus the action-specific fields listed above

IMPORTANT RULES:
1. Use EXACT section_ids and indices from the REPORT STRUCTURE MAP above.
2. ALWAYS update `charts` (section_id="charts") by adding the new period's data point (`add_chart_data_point`) whenever new period financials are retrieved.
3. ALWAYS update `key_highlights` (section_id="key_highlights") by appending or replacing bullet points with the new period's qualitative insights, outlook, or key drivers.
4. When adding a new column to a financial table, provide ALL row values in the correct order matching existing rows.
5. If the MCP findings don't provide enough data for a specific field, use decision "skip" for that field.
"""
        route_resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": routing_prompt}],
            response_format={"type": "json_schema", "json_schema": {"name": "routing", "schema": schema_def, "strict": False}},
            temperature=0.1
        )
        route_result = json.loads(route_resp.choices[0].message.content)
        patches = route_result.get("patches", [])
        
        # Extract reasoning
        msg_obj = route_resp.choices[0].message
        reasoning = getattr(msg_obj, "reasoning_content", None)
        if not reasoning:
            extra = getattr(msg_obj, "model_extra", {}) or {}
            psf = extra.get("provider_specific_fields", {})
            reasoning = psf.get("reasoning", "")
        
        final_reasoning = (mcp_reasoning.strip() + "\n\n" + (reasoning or "").strip()).strip()
        
        # --- 4. Apply Patches ---
        applied_patches = []
        decisions_log = []
        for p in patches:
            decision = p.get("decision", "skip")
            rationale = p.get("rationale", "")
            decisions_log.append({"decision": decision, "rationale": rationale})
            
            if decision == "apply":
                print(f"DEBUG Patch: section={p.get('section_id')} action={p.get('action')} index={p.get('index')} new_value={p.get('new_value', '')[:80]}...")
                success = _apply_patch(report_data, p)
                print(f"DEBUG Patch Success: {success}")
                if success:
                    applied_patches.append(p)
                    
        # Determine final outcome
        if len(applied_patches) > 0:
            outcome = "applied"
        else:
            outcome = "no_update"
            
        # Log to Audit DB
        log_update_run(
            update_id=update_id,
            report_id=report_data.get("company_name", "Unknown"),
            claims=claims,
            decisions=decisions_log,
            outcome=outcome,
            mcp_tool_calls=mcp_tool_calls,
            patches=applied_patches
        )
        
        yield {
            "type": "done",
            "has_conflict": has_conflict,
            "conflicts": conflict_result.get("research_reason", []),
            "mcp_verification": final_verification_notes or "Verification generated no text.",
            "routes": patches,
            "outcome": outcome,
            "suggested_patch": True if applied_patches else False,
            "reasoning": final_reasoning,
            "patch": applied_patches[0] if applied_patches else None
        }
        
    except Exception as e:
        import traceback
        print(f"UPDATE ROUTE CRASH:\n {traceback.format_exc()}")
        yield {"type": "error", "message": str(e)}
