from app.db.session_store import get_session
from app.services.graph_builder import query_graph
from app.services.gemini_client import query_with_context, query_with_images, query_multi_context


def handle_query(session_id: str, question: str) -> dict:
    session = get_session(session_id)

    if not session:
        return {
            "error": "Session not found or expired. Please upload your file again.",
            "session_id": session_id,
        }

    files = session.get("files", [])
    if not files:
        return {
            "error": "No files in this session. Please upload at least one file.",
            "session_id": session_id,
        }

    # Single file — original path (backward compatible)
    if len(files) == 1:
        return _handle_single(session_id, files[0], question)

    # Multiple files — merge context
    return _handle_multi(session_id, files, question)


def _handle_single(session_id: str, file_entry: dict, question: str) -> dict:
    file_type = file_entry["file_type"]
    filename = file_entry["filename"]
    data = file_entry["data"]

    if file_type == "dxf":
        graph_id = data.get("graph_session_id")
        context = query_graph(graph_id, question)
        answer = query_with_context(context, question, file_type, filename=filename)

    else:  # pdf
        is_image_based = data.get("metadata", {}).get("is_image_based", False)
        if is_image_based:
            page_images = data.get("page_images", [])
            answer = query_with_images(page_images, question, filenames=[filename])
            context = f"[Image-based PDF — {len(page_images)} pages sent to Gemini vision]"
        else:
            context = _get_pdf_context(data, question)
            answer = query_with_context(context, question, file_type, filename=filename)

    return {
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "files_queried": [filename],
        "context_used": context[:300] + "..." if len(context) > 300 else context,
    }


def _handle_multi(session_id: str, files: list, question: str) -> dict:
    """Merge context from all files and send to Gemini in one call."""
    text_sections = []       # (filename, context_str)
    image_files = []         # (filename, page_images list)
    files_queried = []

    for entry in files:
        file_type = entry["file_type"]
        filename = entry["filename"]
        data = entry["data"]
        files_queried.append(filename)

        if file_type == "dxf":
            graph_id = data.get("graph_session_id")
            ctx = query_graph(graph_id, question)
            text_sections.append((filename, f"[DXF drawing]\n{ctx}"))

        else:  # pdf
            is_image_based = data.get("metadata", {}).get("is_image_based", False)
            if is_image_based:
                pages = data.get("page_images", [])
                image_files.append((filename, pages))
            else:
                ctx = _get_pdf_context(data, question)
                text_sections.append((filename, f"[PDF document]\n{ctx}"))

    # If we have image files, mix them with text via multi-modal call
    if image_files:
        all_page_images = []
        for fname, pages in image_files:
            # Tag each page with its filename so Gemini knows which file it came from
            for p in pages[:3]:  # cap per-file to 3 pages to stay within limits
                p_tagged = dict(p)
                p_tagged["filename"] = fname
                all_page_images.append(p_tagged)

        answer = query_with_images(
            all_page_images, question,
            filenames=[f for f, _ in image_files],
            extra_text_sections=text_sections,
        )
        context_used = f"[Multi-file: {len(image_files)} image PDF(s) + {len(text_sections)} text source(s)]"
    else:
        answer = query_multi_context(text_sections, question)
        preview = " | ".join(f"{n}: {c[:100]}" for n, c in text_sections)
        context_used = preview[:300] + "..." if len(preview) > 300 else preview

    return {
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "files_queried": files_queried,
        "context_used": context_used,
    }


def _get_pdf_context(data: dict, question: str) -> str:
    full_text = data.get("full_text", "")
    chunks = data.get("chunks", [])
    if len(full_text) < 8000:
        return full_text
    return "\n\n---\n\n".join(chunks[:5])