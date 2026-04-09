import fitz  # PyMuPDF
from pathlib import Path


def parse_pdf(file_path: str) -> dict:
    doc = fitz.open(file_path)

    total_pages = len(doc)  # ← get this BEFORE closing
    pages = []
    full_text = []

    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text("text").strip()

        if text:
            pages.append({
                "page_number": page_num + 1,
                "text": text,
                "char_count": len(text)
            })
            full_text.append(f"[Page {page_num + 1}]\n{text}")

    doc.close()

    chunks = _chunk_text(full_text)

    return {
        "metadata": {
            "filename": Path(file_path).name,
            "total_pages": total_pages,          # ← use saved value
            "pages_with_text": len(pages),
            "total_chars": sum(p["char_count"] for p in pages),
        },
        "pages": pages,
        "chunks": chunks,
        "full_text": "\n\n".join(full_text)
    }


def _chunk_text(page_texts: list[str], chunk_size: int = 2000) -> list[str]:
    """
    Merge all page texts then split into fixed-size chunks
    with 200 char overlap so context isn't lost at boundaries.
    """
    combined = "\n\n".join(page_texts)
    chunks = []
    start = 0
    overlap = 200

    while start < len(combined):
        end = start + chunk_size
        chunks.append(combined[start:end])
        start = end - overlap  # overlap with previous chunk

    return chunks