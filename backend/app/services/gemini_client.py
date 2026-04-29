"""
Available models:
models/gemini-2.5-flash
models/gemini-2.5-pro
models/gemini-2.0-flash
models/gemini-2.0-flash-001
models/gemini-2.0-flash-lite-001
models/gemini-2.0-flash-lite
models/gemini-2.5-flash-preview-tts
models/gemini-2.5-pro-preview-tts
models/gemma-3-1b-it
models/gemma-3-4b-it
models/gemma-3-12b-it
models/gemma-3-27b-it
models/gemma-3n-e4b-it
models/gemma-3n-e2b-it
models/gemma-4-26b-a4b-it
models/gemma-4-31b-it
models/gemini-flash-latest
models/gemini-flash-lite-latest
models/gemini-pro-latest
models/gemini-2.5-flash-lite
models/gemini-2.5-flash-image
models/gemini-3-pro-preview
models/gemini-3-flash-preview
models/gemini-3.1-pro-preview
models/gemini-3.1-pro-preview-customtools
models/gemini-3.1-flash-lite-preview
models/gemini-3-pro-image-preview
models/nano-banana-pro-preview
models/gemini-3.1-flash-image-preview
models/lyria-3-clip-preview
models/lyria-3-pro-preview
models/gemini-robotics-er-1.5-preview
models/gemini-2.5-computer-use-preview-10-2025
models/deep-research-pro-preview-12-2025
"""

import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-2.5-pro")


def query_with_context(context: str, question: str, file_type: str, filename: str = "") -> str:
    """For DXF and text-based PDFs — text only query."""
    file_label = f" ({filename})" if filename else ""
    if file_type == "dxf":
        system_prompt = f"""You are an expert CAD drawing analyst.
You have been given structured data extracted from a DXF CAD file{file_label} including entities, layers, and geometry.
Answer questions about the drawing accurately based on the provided data.
When referencing specific elements, mention their layer, type, and key measurements.
If the data doesn't contain enough information to answer, say so clearly."""
    else:
        system_prompt = f"""You are an expert document analyst.
You have been given text extracted from a PDF document{file_label}.
Answer questions about the document accurately based on the provided text.
Quote relevant sections when helpful. If the answer isn't in the document, say so clearly."""

    prompt = f"""{system_prompt}

--- EXTRACTED DATA ---
{context}
--- END DATA ---

User question: {question}

Answer:"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini error: {str(e)}"


def query_multi_context(text_sections: list[tuple[str, str]], question: str) -> str:
    """
    Merge context from multiple text-based files (DXF / text PDF) and answer
    a single question across all of them.
    text_sections: list of (filename, context_string)
    """
    system_prompt = """You are an expert analyst of architectural drawings and technical documents.
You have been given data extracted from MULTIPLE files (DXF CAD drawings and/or PDF documents).
Each section is labelled with its source filename.
Answer the user's question by referencing ALL relevant files.
If the answer differs or contradicts across files, highlight that.
If a file doesn't contain relevant information for the question, skip it but still mention it briefly."""

    combined = ""
    for filename, ctx in text_sections:
        combined += f"\n\n=== FILE: {filename} ===\n{ctx}\n=== END: {filename} ===\n"

    prompt = f"""{system_prompt}

--- ALL EXTRACTED DATA ---
{combined}
--- END DATA ---

User question: {question}

Answer (reference filenames where relevant):"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini error: {str(e)}"


def query_with_images(
    page_images: list[dict],
    question: str,
    filenames: list[str] = None,
    extra_text_sections: list[tuple[str, str]] = None,
) -> str:
    """
    For image-based PDFs — sends pages as images to Gemini vision.
    Supports multiple files via tagged page_images dicts (with optional 'filename' key).
    extra_text_sections: additional text context from DXF/text-PDF files in the same session.
    """
    filenames = filenames or []
    extra_text_sections = extra_text_sections or []

    file_label = f" from {', '.join(filenames)}" if filenames else ""
    system_prompt = f"""You are an expert architectural and engineering drawing analyst.
You are looking at scanned PDF pages{file_label} which may contain floor plans, technical drawings,
site plans, or engineering documents.
Answer questions accurately based on what you can see in the images.
Be specific about locations, labels, dimensions, and annotations you can read.
If something is not visible or unclear in the images, say so."""

    intro = system_prompt + f"\n\nUser question: {question}\n\nHere are the PDF pages:"
    if extra_text_sections:
        text_block = "\n".join(f"\n=== {fn} ===\n{ctx}" for fn, ctx in extra_text_sections)
        intro += f"\n\nAdditional context from other files in this session:\n{text_block}"

    parts = [intro]

    # Cap total images at 10 to stay within Gemini limits
    images_to_send = page_images[:10]
    for img_data in images_to_send:
        fname_label = img_data.get("filename", "")
        page_label = f"[Page {img_data['page_number']}" + (f" — {fname_label}]" if fname_label else "]")
        parts.append(f"\n{page_label}")
        parts.append({
            "mime_type": "image/png",
            "data": img_data["base64"],
        })

    try:
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"Gemini error: {str(e)}"