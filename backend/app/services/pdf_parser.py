import fitz  # PyMuPDF
from pathlib import Path
import base64


def parse_pdf(file_path: str) -> dict:
    """
    Extract text from PDF if available.
    Always also convert pages to base64 images for vision-based querying.
    """
    doc = fitz.open(file_path)
    total_pages = len(doc)

    pages = []
    full_text = []
    page_images = []  # base64 encoded images

    for page_num in range(total_pages):
        page = doc[page_num]

        # Extract text
        text = page.get_text("text").strip()
        if text:
            pages.append({
                "page_number": page_num + 1,
                "text": text,
                "char_count": len(text)
            })
            full_text.append(f"[Page {page_num + 1}]\n{text}")

        # Convert page to image (300 DPI for good quality)
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        page_images.append({
            "page_number": page_num + 1,
            "base64": img_b64,
            "width": pix.width,
            "height": pix.height
        })

    doc.close()

    is_image_based = len(pages) == 0
    chunks = _chunk_text(full_text) if full_text else []

    return {
        "metadata": {
            "filename": Path(file_path).name,
            "total_pages": total_pages,
            "pages_with_text": len(pages),
            "total_chars": sum(p["char_count"] for p in pages),
            "is_image_based": is_image_based
        },
        "pages": pages,
        "chunks": chunks,
        "full_text": "\n\n".join(full_text),
        "page_images": page_images  # always populated
    }


def _chunk_text(page_texts: list[str], chunk_size: int = 2000) -> list[str]:
    combined = "\n\n".join(page_texts)
    chunks = []
    start = 0
    overlap = 200

    while start < len(combined):
        end = start + chunk_size
        chunks.append(combined[start:end])
        start = end - overlap

    return chunks