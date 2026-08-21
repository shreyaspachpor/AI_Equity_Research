import os
import json
import litellm

litellm.suppress_debug_info = True

async def answer_chat(message: str, report_data: dict, model: str) -> dict:
    """
    Acts as an intent router:
    1. Determines if the message is a QUERY or an UPDATE.
    2. If QUERY, answers the question using the report_data.
    3. If UPDATE, delegates to `process_update_batch`, applies the patch, and returns `updated=True`.
    """
    # Ensure API keys
    if not os.getenv("OPENROUTER_API_KEY") and os.getenv("API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = os.getenv("API_KEY", "")

    # Stage 1: Classify Intent
    intent_prompt = f"""You are an intent classifier for a financial research assistant.
The user is talking to the chatbot. 
Does their message represent a QUESTION about the report (e.g. "What is the revenue?", "Summarize the financials") 
OR does it represent an UPDATE/CORRECTION where the user wants to change the report or fetch new data to update it (e.g. "Actually Q3 profit was 20M", "The revenue is wrong", "Update the report with the latest revenue").

User message: "{message}"

Return a JSON object with this exact structure:
{{
    "intent": "QUERY" | "UPDATE"
}}
Return ONLY valid JSON.
"""
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": intent_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        intent_res = json.loads(resp.choices[0].message.content)
        intent = intent_res.get("intent", "QUERY")
    except Exception as e:
        intent = "QUERY"

    # Stage 2: Route
    if intent == "UPDATE":
        from core.update import process_update_batch
        
        # We will yield chunks from process_update_batch as they arrive
        async for chunk in process_update_batch([message], report_data, model):
            if chunk.get("type") == "done":
                # process_update_batch handles patching in-place
                patch_applied = chunk.get("suggested_patch", False)
                reply_msg = "Update Processed!\n\n"
                
                if chunk.get("has_conflict"):
                    conflicts = chunk.get('conflicts', [])
                    if conflicts:
                        reply_msg += f"⚠️ Research Triggered: {', '.join(conflicts)}\n\n"
                    reply_msg += f"{chunk.get('mcp_verification', '')}\n\n"
                else:
                    reply_msg += "✅ No conflicts detected.\n\n"
                    
                if patch_applied:
                    reply_msg += "The report has been surgically updated with your claims."
                else:
                    reply_msg += "No updates were applied to the report."
                
                yield {
                    "type": "done",
                    "reply": reply_msg,
                    "reasoning": chunk.get("reasoning", ""),
                    "updated": patch_applied,
                    "updated_data": report_data
                }
            else:
                yield chunk
            
        return
        # QUERY Intent
        system_prompt = (
            "You are an expert equity research analyst sidebar chatbot. Your purpose is to answer questions "
            "about the company using ONLY the provided one-pager financial report context below. "
            "Do not invent information. If the answer is not in the context, explicitly say that the one-pager "
            "does not contain enough information. Ground your answers in the current one-pager and refer "
            "to relevant sections when useful.\n\n"
            f"=== CURRENT ONE-PAGER CONTEXT ===\n{json.dumps(report_data, indent=2)}\n==========================="
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]
        
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=messages,
                stream=True,
                max_tokens=1000,
                temperature=0.2
            )
            
            reply_text = ""
            reasoning_text = ""
            
            async for chunk in resp:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None) or ""
                r = getattr(delta, "reasoning_content", None) or ""
                if not r:
                    extra = getattr(delta, "model_extra", {}) or {}
                    psf = extra.get("provider_specific_fields", {})
                    r = psf.get("reasoning", "") or ""
                
                reply_text += content
                reasoning_text += r
                
                if content or r:
                    yield {
                        "type": "chunk",
                        "content": content,
                        "reasoning": r
                    }
            
            yield {
                "type": "done",
                "reply": reply_text,
                "reasoning": reasoning_text,
                "updated": False
            }
        except Exception as e:
            yield {
                "type": "error",
                "message": f"Error connecting to AI model: {e}",
                "updated": False
            }
