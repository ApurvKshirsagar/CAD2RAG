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
import base64

genai.configure(api_key=settings.gemini_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")


def query_with_context(context: str, question: str, file_type: str) -> str:
    """For DXF and text-based PDFs — text only query."""
    if file_type == "dxf":
        system_prompt = """You are an expert CAD drawing analyst.
You have been given structured data extracted from a DXF CAD file including entities, layers, and geometry.
Answer questions about the drawing accurately based on the provided data.
When referencing specific elements, mention their layer, type, and key measurements.
If the data doesn't contain enough information to answer, say so clearly."""
    else:
        system_prompt = """You are an expert document analyst.
You have been given text extracted from a PDF document.
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


def query_with_images(page_images: list[dict], question: str) -> str:
    """
    For image-based PDFs — sends pages as images to Gemini vision.
    Caps at 5 pages to stay within token limits.
    """
    system_prompt = """You are an expert architectural and engineering drawing analyst.
You are looking at scanned PDF pages which may contain floor plans, technical drawings, 
site plans, or engineering documents.
Answer questions accurately based on what you can see in the images.
Be specific about locations, labels, dimensions, and annotations you can read.
If something is not visible or unclear in the images, say so."""

    # Build content parts — text first, then images
    parts = [system_prompt + f"\n\nUser question: {question}\n\nHere are the PDF pages:"]

    # Cap at 5 pages to avoid token limits
    images_to_send = page_images[:5]

    for img_data in images_to_send:
        parts.append(f"\n[Page {img_data['page_number']}]")
        parts.append({
            "mime_type": "image/png",
            "data": img_data["base64"]
        })

    try:
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"Gemini error: {str(e)}"