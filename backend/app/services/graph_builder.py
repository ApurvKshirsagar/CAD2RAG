import json
from app.db.neo4j_client import Neo4jClient


def build_graph(session_id: str, parsed_data: dict) -> dict:
    """
    Takes parsed DXF data and writes it into Neo4j.
    Everything is namespaced under session_id so multiple
    uploads don't collide.
    Returns a summary of what was written.
    """
    _clear_session(session_id)

    meta_count = _write_metadata(session_id, parsed_data["metadata"])
    layer_count = _write_layers(session_id, parsed_data["layers"])
    entity_count = _write_entities(session_id, parsed_data["entities"])
    _write_layer_relationships(session_id, parsed_data["entities"])

    return {
        "session_id": session_id,
        "metadata_nodes": meta_count,
        "layer_nodes": layer_count,
        "entity_nodes": entity_count,
    }


def _clear_session(session_id: str):
    """Remove all nodes for this session before re-writing."""
    Neo4jClient.run_query(
        "MATCH (n {session_id: $sid}) DETACH DELETE n",
        {"sid": session_id}
    )


def _write_metadata(session_id: str, metadata: dict) -> int:
    Neo4jClient.run_query(
        """
        CREATE (m:DXFMetadata {
            session_id: $sid,
            dxf_version: $dxf_version,
            filename: $filename,
            units: $units,
            created_by: $created_by
        })
        """,
        {
            "sid": session_id,
            **metadata
        }
    )
    return 1


def _write_layers(session_id: str, layers: list) -> int:
    for layer in layers:
        Neo4jClient.run_query(
            """
            CREATE (l:Layer {
                session_id: $sid,
                name: $name,
                color: $color,
                linetype: $linetype,
                is_on: $is_on,
                is_locked: $is_locked
            })
            """,
            {"sid": session_id, **layer}
        )
    return len(layers)


def _write_entities(session_id: str, entities: list) -> int:
    count = 0
    for entity in entities:
        etype = entity.get("type", "UNKNOWN")
        props = _flatten_entity(entity)

        Neo4jClient.run_query(
            f"""
            CREATE (e:Entity:{etype} {{
                session_id: $sid,
                handle: $handle,
                layer: $layer,
                entity_type: $entity_type,
                properties: $properties
            }})
            """,
            {
                "sid": session_id,
                "handle": props.get("handle", ""),
                "layer": props.get("layer", "0"),
                "entity_type": etype,
                "properties": json.dumps(props),  # full data as JSON string
            }
        )
        count += 1
    return count


def _write_layer_relationships(session_id: str, entities: list):
    """
    Create relationships: (Entity)-[:ON_LAYER]->(Layer)
    """
    Neo4jClient.run_query(
        """
        MATCH (e:Entity {session_id: $sid})
        MATCH (l:Layer {session_id: $sid, name: e.layer})
        CREATE (e)-[:ON_LAYER]->(l)
        """,
        {"sid": session_id}
    )


def query_graph(session_id: str, question: str) -> str:
    """
    Smart query: tries to pull relevant entities based on
    keywords in the question. Returns a text summary for Gemini.
    """
    keywords = question.lower()

    # Layer-specific query
    if "layer" in keywords:
        results = Neo4jClient.run_query(
            """
            MATCH (l:Layer {session_id: $sid})
            RETURN l.name AS name, l.color AS color,
                   l.linetype AS linetype, l.is_on AS is_on
            ORDER BY l.name
            """,
            {"sid": session_id}
        )
        return f"Layers in drawing:\n{_format_results(results)}"

    # Text/labels query
    if any(k in keywords for k in ["text", "label", "annotation", "note"]):
        results = Neo4jClient.run_query(
            """
            MATCH (e:Entity {session_id: $sid})
            WHERE e.entity_type IN ['TEXT', 'MTEXT']
            RETURN e.properties AS props
            LIMIT 50
            """,
            {"sid": session_id}
        )
        return f"Text entities found:\n{_format_results(results)}"

    # Dimension query
    if any(k in keywords for k in ["dimension", "size", "measurement", "length"]):
        results = Neo4jClient.run_query(
            """
            MATCH (e:Entity {session_id: $sid})
            WHERE e.entity_type IN ['DIMENSION', 'LINE']
            RETURN e.entity_type AS type, e.properties AS props
            LIMIT 50
            """,
            {"sid": session_id}
        )
        return f"Dimension/measurement entities:\n{_format_results(results)}"

    # Block/component query
    if any(k in keywords for k in ["block", "component", "insert", "symbol"]):
        results = Neo4jClient.run_query(
            """
            MATCH (e:Entity {session_id: $sid})
            WHERE e.entity_type = 'INSERT'
            RETURN e.properties AS props
            LIMIT 50
            """,
            {"sid": session_id}
        )
        return f"Block insertions found:\n{_format_results(results)}"

    # Default: return a general summary
    results = Neo4jClient.run_query(
        """
        MATCH (e:Entity {session_id: $sid})
        RETURN e.entity_type AS type, COUNT(*) AS count
        ORDER BY count DESC
        """,
        {"sid": session_id}
    )
    layer_results = Neo4jClient.run_query(
        """
        MATCH (l:Layer {session_id: $sid})
        RETURN l.name AS layer, l.is_on AS active
        """,
        {"sid": session_id}
    )
    return (
        f"Drawing summary:\nEntity counts: {_format_results(results)}\n"
        f"Layers: {_format_results(layer_results)}"
    )


def _flatten_entity(entity: dict) -> dict:
    """Flatten nested dicts (like points) into strings for Neo4j storage."""
    flat = {}
    for k, v in entity.items():
        if isinstance(v, dict):
            flat[k] = json.dumps(v)
        elif isinstance(v, list):
            flat[k] = json.dumps(v)
        else:
            flat[k] = v
    return flat


def _format_results(results: list) -> str:
    if not results:
        return "No results found."
    return "\n".join(str(r) for r in results)