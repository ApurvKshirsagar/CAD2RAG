from pathlib import Path


def detect_file_type(filename: str) -> str:
    """
    Returns 'dxf', 'pdf', or raises ValueError for unsupported types.
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".dxf":
        return "dxf"
    elif suffix == ".pdf":
        return "pdf"
    else:
        raise ValueError(f"Unsupported file type: '{suffix}'. Only .dxf and .pdf are accepted.")