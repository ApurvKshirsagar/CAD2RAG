import ezdxf
import re
from ezdxf.document import Drawing
from pathlib import Path
from typing import Any
from app.utils.helpers import safe_float, safe_str


def parse_dxf(file_path: str) -> dict:
    """
    Parse a DXF file and extract all meaningful entities.
    Pre-processes the file to fix malformed scientific notation
    e.g. '1.000000000000000E 20' -> '1.000000000000000E+20'
    """
    # Fix malformed scientific notation before ezdxf reads it
    fixed_path = _fix_dxf_encoding(file_path)

    doc: Drawing = ezdxf.readfile(fixed_path)
    msp = doc.modelspace()

    parsed = {
        "metadata": extract_metadata(doc),
        "layers": extract_layers(doc),
        "entities": extract_entities(msp)
    }

    return parsed


def _fix_dxf_encoding(file_path: str) -> str:
    """
    Reads the DXF file, fixes broken scientific notation,
    writes to a temp file, returns the temp path.
    Only fixes lines that are purely numeric values.
    """
    import os

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    fixed_lines = []
    for line in lines:
        stripped = line.rstrip('\n\r')
        # Only apply fix if the line looks like a float with broken exponent
        # e.g. '1.000000000000000E 20' — starts with digit or minus, has 'E '
        if re.match(r'^-?\d+\.?\d*E\s\d+', stripped):
            fixed_line = re.sub(r'(E)\s+(\d)', r'E+\2', stripped)
            fixed_lines.append(fixed_line + '\n')
        else:
            fixed_lines.append(line)

    base, ext = os.path.splitext(file_path)
    fixed_path = base + "_fixed" + ext
    with open(fixed_path, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    return fixed_path


def extract_metadata(doc: Drawing) -> dict:
    header = doc.header
    return {
        "dxf_version": doc.dxfversion,
        "filename": Path(doc.filename).name if doc.filename else "unknown",
        "created_by": safe_str(header.get("$ACADVER", "unknown")),
        "units": safe_str(header.get("$INSUNITS", "unknown")),
        "drawing_limits_min": safe_str(header.get("$LIMMIN", "unknown")),
        "drawing_limits_max": safe_str(header.get("$LIMMAX", "unknown")),
    }


def extract_layers(doc: Drawing) -> list[dict]:
    layers = []
    for layer in doc.layers:
        layers.append({
            "name": layer.dxf.name,
            "color": safe_float(layer.dxf.get("color", 7)),
            "linetype": safe_str(layer.dxf.get("linetype", "CONTINUOUS")),
            "is_on": layer.is_on(),
            "is_locked": layer.is_locked(),
        })
    return layers


def extract_entities(msp) -> list[dict]:
    entities = []

    for entity in msp:
        etype = entity.dxftype()

        try:
            if etype == "LINE":
                entities.append(parse_line(entity))
            elif etype == "CIRCLE":
                entities.append(parse_circle(entity))
            elif etype == "ARC":
                entities.append(parse_arc(entity))
            elif etype == "LWPOLYLINE":
                entities.append(parse_lwpolyline(entity))
            elif etype == "POLYLINE":
                entities.append(parse_polyline(entity))
            elif etype in ("TEXT", "MTEXT"):
                entities.append(parse_text(entity, etype))
            elif etype == "INSERT":
                entities.append(parse_insert(entity))
            elif etype == "DIMENSION":
                entities.append(parse_dimension(entity))
            elif etype == "SPLINE":
                entities.append(parse_spline(entity))
            elif etype == "ELLIPSE":
                entities.append(parse_ellipse(entity))
            elif etype == "HATCH":
                entities.append(parse_hatch(entity))
            else:
                # Catch-all for unknown types
                entities.append({
                    "type": etype,
                    "layer": safe_str(entity.dxf.get("layer", "0")),
                    "handle": safe_str(entity.dxf.handle),
                })
        except Exception as e:
            # Never let one bad entity crash the whole parse
            entities.append({
                "type": etype,
                "layer": "unknown",
                "handle": safe_str(getattr(entity.dxf, "handle", "unknown")),
                "parse_error": str(e)
            })

    return entities


# ── Individual entity parsers ──────────────────────────────────────────────────

def parse_line(e) -> dict:
    return {
        "type": "LINE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "start": point_to_dict(e.dxf.start),
        "end": point_to_dict(e.dxf.end),
        "length": safe_float(e.dxf.start.distance(e.dxf.end)),
    }

def parse_circle(e) -> dict:
    return {
        "type": "CIRCLE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "center": point_to_dict(e.dxf.center),
        "radius": safe_float(e.dxf.radius),
    }

def parse_arc(e) -> dict:
    return {
        "type": "ARC",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "center": point_to_dict(e.dxf.center),
        "radius": safe_float(e.dxf.radius),
        "start_angle": safe_float(e.dxf.start_angle),
        "end_angle": safe_float(e.dxf.end_angle),
    }

def parse_lwpolyline(e) -> dict:
    points = [{"x": p[0], "y": p[1]} for p in e.get_points()]
    return {
        "type": "LWPOLYLINE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "point_count": len(points),
        "points": points[:20],  # Cap at 20 to avoid huge nodes
        "is_closed": e.is_closed,
    }

def parse_polyline(e) -> dict:
    try:
        points = [point_to_dict(v.dxf.location) for v in e.vertices]
    except Exception:
        points = []
    return {
        "type": "POLYLINE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "point_count": len(points),
        "points": points[:20],
    }

def parse_text(e, etype: str) -> dict:
    if etype == "MTEXT":
        text_value = safe_str(e.plain_mtext())
        insert = e.dxf.insert
    else:
        text_value = safe_str(e.dxf.get("text", ""))
        insert = e.dxf.get("insert", None)
    return {
        "type": etype,
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "text": text_value,
        "insert": point_to_dict(insert) if insert else {},
        "height": safe_float(e.dxf.get("height", 0)),
    }

def parse_insert(e) -> dict:
    return {
        "type": "INSERT",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "block_name": safe_str(e.dxf.name),
        "insert": point_to_dict(e.dxf.insert),
        "x_scale": safe_float(e.dxf.get("xscale", 1.0)),
        "y_scale": safe_float(e.dxf.get("yscale", 1.0)),
        "rotation": safe_float(e.dxf.get("rotation", 0.0)),
    }

def parse_dimension(e) -> dict:
    return {
        "type": "DIMENSION",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "dim_type": safe_float(e.dxf.get("dimtype", 0)),
        "text": safe_str(e.dxf.get("text", "")),
        "defpoint": point_to_dict(e.dxf.get("defpoint", None)),
    }

def parse_spline(e) -> dict:
    return {
        "type": "SPLINE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "degree": safe_float(e.dxf.get("degree", 3)),
        "control_point_count": len(e.control_points),
        "is_closed": e.closed,
    }

def parse_ellipse(e) -> dict:
    return {
        "type": "ELLIPSE",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "center": point_to_dict(e.dxf.center),
        "major_axis": point_to_dict(e.dxf.major_axis),
        "ratio": safe_float(e.dxf.ratio),
    }

def parse_hatch(e) -> dict:
    return {
        "type": "HATCH",
        "handle": safe_str(e.dxf.handle),
        "layer": safe_str(e.dxf.layer),
        "pattern_name": safe_str(e.dxf.get("pattern_name", "")),
        "solid_fill": bool(e.dxf.get("solid_fill", 0)),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def point_to_dict(point) -> dict:
    if point is None:
        return {}
    try:
        return {
            "x": round(float(point.x), 4),
            "y": round(float(point.y), 4),
            "z": round(float(point.z), 4) if hasattr(point, "z") else 0.0,
        }
    except Exception:
        return {}