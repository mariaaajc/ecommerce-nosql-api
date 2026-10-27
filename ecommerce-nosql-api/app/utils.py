"""Helpers: conversión de ObjectId y paginación."""
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def to_oid(id_str: str) -> ObjectId:
    """Convierte un string a ObjectId o responde 400 si no es válido."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Id inválido: {id_str}")


def serialize(doc):
    """Convierte ObjectId a string (recursivo) para poder devolver JSON."""
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: serialize(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc


def paginar(coleccion, filtro: dict, page: int, limit: int, sort_field: str, sort_dir: int, projection=None):
    """Aplica orden + skip/limit y devuelve metadatos de paginación."""
    total = coleccion.count_documents(filtro)
    cursor = coleccion.find(filtro, projection).sort(sort_field, sort_dir).skip((page - 1) * limit).limit(limit)
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
        "data": serialize(list(cursor)),
    }
