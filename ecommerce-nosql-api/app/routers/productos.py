"""Endpoints de productos: escritura, lectura con filtro multicriterio,
opiniones embebidas ($push) y ajuste de stock por variación ($inc posicional)."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, WriteError

from app.db import productos, usuarios
from app.schemas import ProductoIn, ProductoUpdate, OpinionIn, StockAjuste
from app.utils import to_oid, serialize, paginar

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.post("", status_code=201)
def crear_producto(body: ProductoIn):
    doc = body.model_dump()
    doc.update({
        "opiniones": [],
        "rating_promedio": None,
        "creado_en": datetime.now(timezone.utc),
    })
    try:
        res = productos.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Ya existe un producto con alguno de esos SKU")
    except WriteError as e:
        # La regla $jsonSchema rechazó el documento
        raise HTTPException(422, f"Documento rechazado por la validación de MongoDB: {e.details.get('errmsg')}")
    return {"id": str(res.inserted_id)}


@router.get("")
def listar_productos(
    q: Optional[str] = Query(None, description="Texto a buscar en nombre o descripción"),
    categoria: Optional[str] = None,
    marca: Optional[str] = None,
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    talla: Optional[str] = None,
    color: Optional[str] = None,
    en_stock: Optional[bool] = Query(None, description="true = al menos una variación con stock > 0"),
    etiqueta: Optional[str] = None,
    rating_min: Optional[float] = Query(None, ge=1, le=5),
    sort: str = Query("creado_en", pattern="^(precio|nombre|rating_promedio|creado_en)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    """Filtro multicriterio. Cada parámetro agrega una condición al $and.
    Los filtros sobre variaciones usan $elemMatch para que talla, color y stock
    se evalúen sobre la MISMA variación."""
    condiciones = [{"activo": True}]

    if q:
        condiciones.append({"$or": [
            {"nombre": {"$regex": q, "$options": "i"}},
            {"descripcion": {"$regex": q, "$options": "i"}},
        ]})
    if categoria:
        condiciones.append({"categoria": categoria})
    if marca:
        condiciones.append({"marca": marca})
    if precio_min is not None or precio_max is not None:
        rango = {}
        if precio_min is not None:
            rango["$gte"] = precio_min
        if precio_max is not None:
            rango["$lte"] = precio_max
        condiciones.append({"precio": rango})
    if etiqueta:
        condiciones.append({"etiquetas": etiqueta})          # match dentro de array
    if rating_min is not None:
        condiciones.append({"rating_promedio": {"$gte": rating_min}})

    variacion = {}
    if talla:
        variacion["talla"] = talla
    if color:
        variacion["color"] = color
    if en_stock is True:
        variacion["stock"] = {"$gt": 0}
    if variacion:
        condiciones.append({"variaciones": {"$elemMatch": variacion}})
    elif en_stock is False:
        condiciones.append({"variaciones": {"$not": {"$elemMatch": {"stock": {"$gt": 0}}}}})

    filtro = {"$and": condiciones}
    direccion = ASCENDING if order == "asc" else DESCENDING
    return paginar(productos, filtro, page, limit, sort, direccion, projection={"opiniones": 0})


@router.get("/{producto_id}")
def obtener_producto(producto_id: str):
    doc = productos.find_one({"_id": to_oid(producto_id)})
    if not doc:
        raise HTTPException(404, "Producto no encontrado")
    return serialize(doc)


@router.patch("/{producto_id}")
def actualizar_producto(producto_id: str, body: ProductoUpdate):
    cambios = {k: v for k, v in body.model_dump().items() if v is not None}
    if not cambios:
        raise HTTPException(400, "No se enviaron campos para actualizar")
    try:
        res = productos.update_one({"_id": to_oid(producto_id)}, {"$set": cambios})
    except WriteError as e:
        raise HTTPException(422, f"Rechazado por $jsonSchema: {e.details.get('errmsg')}")
    if res.matched_count == 0:
        raise HTTPException(404, "Producto no encontrado")
    return {"modificados": res.modified_count}


@router.post("/{producto_id}/opiniones", status_code=201)
def agregar_opinion(producto_id: str, body: OpinionIn):
    """Embebe la opinión en el producto con $push y recalcula el promedio.
    Un usuario solo puede opinar una vez por producto."""
    oid = to_oid(producto_id)
    uid = to_oid(body.usuario_id)
    usuario = usuarios.find_one({"_id": uid}, {"nombre": 1, "apellido": 1})
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    opinion = {
        "usuario_id": uid,
        "usuario_nombre": f"{usuario['nombre']} {usuario['apellido']}",
        "calificacion": body.calificacion,
        "comentario": body.comentario,
        "fecha": datetime.now(timezone.utc),
    }
    # Filtro: el producto existe Y ese usuario no ha opinado todavía
    res = productos.update_one(
        {"_id": oid, "opiniones.usuario_id": {"$ne": uid}},
        {"$push": {"opiniones": opinion}},
    )
    if res.matched_count == 0:
        if not productos.find_one({"_id": oid}, {"_id": 1}):
            raise HTTPException(404, "Producto no encontrado")
        raise HTTPException(409, "Este usuario ya opinó sobre el producto")

    # Recalcular rating_promedio con una agregación sobre el array embebido
    calc = list(productos.aggregate([
        {"$match": {"_id": oid}},
        {"$project": {"promedio": {"$avg": "$opiniones.calificacion"}}},
    ]))
    promedio = round(calc[0]["promedio"], 2) if calc else None
    productos.update_one({"_id": oid}, {"$set": {"rating_promedio": promedio}})
    return {"rating_promedio": promedio}


@router.patch("/{producto_id}/variaciones/{sku}/stock")
def ajustar_stock(producto_id: str, sku: str, body: StockAjuste):
    """Ajusta el stock de UNA variación con $inc y el operador posicional $.
    Si es una salida, el filtro exige stock suficiente (operación atómica)."""
    filtro = {"_id": to_oid(producto_id), "variaciones": {"$elemMatch": {"sku": sku}}}
    if body.cantidad < 0:
        filtro["variaciones"]["$elemMatch"]["stock"] = {"$gte": -body.cantidad}
    res = productos.update_one(filtro, {"$inc": {"variaciones.$.stock": body.cantidad}})
    if res.matched_count == 0:
        raise HTTPException(409, "Producto/SKU no encontrado o stock insuficiente")
    doc = productos.find_one({"_id": to_oid(producto_id)}, {"variaciones": 1})
    return serialize(next(v for v in doc["variaciones"] if v["sku"] == sku))
