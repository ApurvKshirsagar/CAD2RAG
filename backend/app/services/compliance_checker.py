"""
Compliance checker for PDF sessions.

Strategy:
- For small rule sets (<=30): send all rules in one Gemini call → single JSON response
- For large rule sets (>30): batch into groups of 25 and run concurrently
  Each batch is one Gemini call returning partial JSON.

Each rule gets:
  status: "compliant" | "non_compliant" | "uncertain"
  reason: one-sentence explanation referencing the document
"""

import asyncio
import json
import re
import google.generativeai as genai

from app.config import settings
from app.db.session_store import get_session

genai.configure(api_key=settings.gemini_api_key)

BATCH_SIZE = 25
MAX_CONCURRENT = 4  # stay within Gemini rate limits


async def run_compliance_check(session_id: str, rules: list[str]) -> dict:
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found or expired. Please upload your files again."}

    files = session.get("files", [])
    pdf_files = [f for f in files if f["file_type"] == "pdf"]

    if not pdf_files:
        return {"error": "Compliance check is only available for PDF files. No PDFs found in this session."}

    # Build combined document context (text + image inventory)
    text_context, page_images = _build_context(pdf_files)

    # Split rules into batches
    batches = [rules[i:i + BATCH_SIZE] for i in range(0, len(rules), BATCH_SIZE)]

    # Run all batches concurrently (capped)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        _check_batch(semaphore, batch, start_idx, text_context, page_images)
        for start_idx, batch in zip(range(0, len(rules), BATCH_SIZE), batches)
    ]
    batch_results = await asyncio.gather(*tasks)

    # Flatten results preserving original order
    results = []
    for batch_res in batch_results:
        results.extend(batch_res)

    # Compute summary
    counts = {"compliant": 0, "non_compliant": 0, "uncertain": 0}
    for r in results:
        counts[r.get("status", "uncertain")] += 1

    return {
        "session_id": session_id,
        "total_rules": len(rules),
        "summary": counts,
        "results": results,
    }


def _build_context(pdf_files: list) -> tuple[str, list]:
    """Return (combined_text_context, page_images_list)."""
    text_sections = []
    page_images = []

    for entry in pdf_files:
        data = entry["data"]
        filename = entry["filename"]
        is_image_based = data.get("metadata", {}).get("is_image_based", False)

        if not is_image_based:
            text_sections.append(f"=== FILE: {filename} ===\n{data.get('full_text', '')}\n=== END: {filename} ===")
        else:
            # For image-based PDFs, take up to 5 pages per file
            pages = data.get("page_images", [])[:5]
            for p in pages:
                tagged = dict(p)
                tagged["filename"] = filename
                page_images.append(tagged)
            text_sections.append(f"=== FILE: {filename} === [image-based PDF — pages sent as images]")

    return "\n\n".join(text_sections), page_images


async def _check_batch(
    semaphore: asyncio.Semaphore,
    batch: list[str],
    start_idx: int,
    text_context: str,
    page_images: list,
) -> list[dict]:
    async with semaphore:
        return await asyncio.to_thread(
            _check_batch_sync, batch, start_idx, text_context, page_images
        )


def _check_batch_sync(
    batch: list[str],
    start_idx: int,
    text_context: str,
    page_images: list,
) -> list[dict]:
    model = genai.GenerativeModel("gemini-2.5-pro")

    numbered_rules = "\n".join(
        f"{start_idx + i + 1}. {rule}" for i, rule in enumerate(batch)
    )

    system_prompt = f"""You are an expert hospital compliance auditor reviewing architectural and planning documents.

You will be given a set of compliance rules and document content (text and/or floor plan images).
For each rule, determine whether the document shows:
- "compliant": the document clearly satisfies this rule
- "non_compliant": the document clearly violates this rule
- "uncertain": the document does not have enough information to determine compliance, or the area is ambiguous

Respond ONLY with a valid JSON array. No markdown, no backticks, no extra text.
Each element must have exactly these fields:
  "rule_index": integer (the rule number as given),
  "status": "compliant" | "non_compliant" | "uncertain",
  "reason": string (one concise sentence explaining why, referencing the document specifically)

Rules to check:
{numbered_rules}

Document content:
{text_context[:12000]}
"""

    parts = [system_prompt]

    # Add images if available (cap at 8 total to stay in token budget)
    for img in page_images[:8]:
        fname = img.get("filename", "")
        parts.append(f"\n[Page {img['page_number']}{' — ' + fname if fname else ''}]")
        parts.append({"mime_type": "image/png", "data": img["base64"]})

    try:
        response = model.generate_content(parts)
        raw = response.text.strip()

        # Strip markdown fences if Gemini added them anyway
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        parsed = json.loads(raw)

        # Normalise and validate each entry
        results = []
        for i, rule in enumerate(batch):
            rule_num = start_idx + i + 1
            # Find matching entry by rule_index
            entry = next((e for e in parsed if e.get("rule_index") == rule_num), None)
            if entry:
                status = entry.get("status", "uncertain")
                if status not in ("compliant", "non_compliant", "uncertain"):
                    status = "uncertain"
                results.append({
                    "rule_index": rule_num,
                    "rule": rule,
                    "status": status,
                    "reason": entry.get("reason", "No reason provided."),
                })
            else:
                # Gemini missed this rule — mark uncertain
                results.append({
                    "rule_index": rule_num,
                    "rule": rule,
                    "status": "uncertain",
                    "reason": "Could not be evaluated — not addressed in the document.",
                })
        return results

    except (json.JSONDecodeError, Exception) as e:
        # Fallback: mark entire batch as uncertain
        return [
            {
                "rule_index": start_idx + i + 1,
                "rule": rule,
                "status": "uncertain",
                "reason": f"Evaluation failed: {str(e)[:100]}",
            }
            for i, rule in enumerate(batch)
        ]