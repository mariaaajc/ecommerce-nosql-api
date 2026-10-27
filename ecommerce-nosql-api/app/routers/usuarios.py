"""Endpoints de usuarios: perfil con direcciones embebidas."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, WriteError

from app.db import usuarios, pedidos
from app.schemas import UsuarioIn, Direccion
from app.utils import to_oid, serialize, paginar

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("", status_code=201)
def crear_usuario(body: UsuarioIn):
    doc = body.model_dump()
    doc["email"] = doc["email"].lower()
    doc["registrado_en"] = datetime.now(timezone.utc)
    try:
        res = usuarios.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Ya existe un usuario con ese email")
    except WriteError as e:
        raise HTTPException(422, f"Rechazado por $jsonSchema: {e.details.get('errmsg')}")
    return {"id": str(res.inserted_id)}


@router.get("")
def listar_usuarios(
    q: Optional[str] = Query(None, description="Busca en nombre, apellido o email"),
    departamento: Optional[str] = Query(None, description="Filtra por departamento de alguna dirección"),
    sort: str = Query("registrado_en", pattern="^(registrado_en|apellido|email)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    filtro = {}
    if q:
        filtro["$or"] = [
            {"nombre": {"$regex": q, "$options": "i"}},
            {"apellido": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    if departamento:
        filtro["direcciones.departamento"] = departamento
    return paginar(usuarios, filtro, page, limit, sort, ASCENDING if order == "asc" else DESCENDING)


@router.get("/{usuario_id}")
def obtener_usuario(usuario_id: str):
    doc = usuarios.find_one({"_id": to_oid(usuario_id)})
    if not doc:
        raise HTTPException(404, "Usuario no encontrado")
    return serialize(doc)


@router.get("/{usuario_id}/pedidos")
def pedidos_del_usuario(usuario_id: str, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """Muestra la relación referenciada: pedidos.usuario_id -> usuarios._id"""
    uid = to_oid(usuario_id)
    if not usuarios.find_one({"_id": uid}, {"_id": 1}):
        raise HTTPException(404, "Usuario no encontrado")
    return paginar(pedidos, {"usuario_id": uid}, page, limit, "fecha", DESCENDING)


@router.post("/{usuario_id}/direcciones", status_code=201)
def agregar_direccion(usuario_id: str, body: Direccion):
    uid = to_oid(usuario_id)
    if body.principal:
        # Solo puede haber una dirección principal: se desmarcan todas primero
        usuarios.update_one({"_id": uid}, {"$set": {"direcciones.$[].principal": False}})
    res = usuarios.update_one({"_id": uid}, {"$push": {"direcciones": body.model_dump()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Usuario no encontrado")
    return {"ok": True}
