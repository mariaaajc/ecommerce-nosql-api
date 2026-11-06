"""Endpoints de pedidos. Aquí vive la lógica de negocio principal:
validar stock por variación, descontarlo de forma atómica y guardar el
pedido con un snapshot (copia) de nombre/precio de cada ítem."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pymongo import ASCENDING, DESCENDING

from app.db import pedidos, productos, usuarios
from app.schemas import PedidoIn, EstadoUpdate
from app.utils import to_oid, serialize, paginar

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

# Máquina de estados: desde cada estado, a cuáles se puede pasar
TRANSICIONES = {
    "pendiente": {"pagado", "cancelado"},
    "pagado": {"enviado", "cancelado"},
    "enviado": {"entregado"},
    "entregado": set(),
    "cancelado": set(),
}


@router.post("", status_code=201)
def crear_pedido(body: PedidoIn):
    uid = to_oid(body.usuario_id)
    usuario = usuarios.find_one({"_id": uid})
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")

    # Dirección de envío: la indicada por alias o la principal
    direccion = None
    for d in usuario.get("direcciones", []):
        if (body.direccion_alias and d["alias"] == body.direccion_alias) or (not body.direccion_alias and d.get("principal")):
            direccion = d
            break
    if not direccion:
        raise HTTPException(400, "El usuario no tiene una dirección válida para el envío")

    items_snapshot = []
    descontados = []   # para revertir si algo falla a mitad de camino
    for item in body.items:
        pid = to_oid(item.producto_id)
        # Descuento atómico: solo aplica si ESA variación tiene stock suficiente
        res = productos.update_one(
            {"_id": pid, "activo": True,
             "variaciones": {"$elemMatch": {"sku": item.sku, "stock": {"$gte": item.cantidad}}}},
            {"$inc": {"variaciones.$.stock": -item.cantidad}},
        )
        if res.matched_count == 0:
            # Revertir los descuentos ya hechos
            for pid_r, sku_r, cant_r in descontados:
                productos.update_one({"_id": pid_r, "variaciones.sku": sku_r},
                                     {"$inc": {"variaciones.$.stock": cant_r}})
            raise HTTPException(409, f"Stock insuficiente o SKU inexistente: {item.sku}")
        descontados.append((pid, item.sku, item.cantidad))

        prod = productos.find_one({"_id": pid}, {"nombre": 1, "precio": 1, "variaciones": 1})
        var = next(v for v in prod["variaciones"] if v["sku"] == item.sku)
        items_snapshot.append({
            "producto_id": pid,
            "sku": item.sku,
            "nombre": prod["nombre"],                # snapshot: no cambia si el catálogo cambia
            "talla": var["talla"],
            "color": var["color"],
            "precio_unitario": prod["precio"],       # snapshot del precio cobrado
            "cantidad": item.cantidad,
            "subtotal": round(prod["precio"] * item.cantidad, 2),
        })

    subtotal = round(sum(i["subtotal"] for i in items_snapshot), 2)
    envio = 0.0 if subtotal >= 50 else 3.99
    pedido = {
        "usuario_id": uid,
        "fecha": datetime.now(timezone.utc),
        "estado": "pendiente",
        "metodo_pago": body.metodo_pago,
        "direccion_envio": direccion,
        "items": items_snapshot,
        "subtotal": subtotal,
        "envio": envio,
        "total": round(subtotal + envio, 2),
        "historial_estados": [{"estado": "pendiente", "fecha": datetime.now(timezone.utc)}],
    }
    res = pedidos.insert_one(pedido)
    return {"id": str(res.inserted_id), "total": pedido["total"]}


@router.get("")
def listar_pedidos(
    estado: Optional[str] = Query(None, pattern="^(pendiente|pagado|enviado|entregado|cancelado)$"),
    usuario_id: Optional[str] = None,
    metodo_pago: Optional[str] = None,
    total_min: Optional[float] = Query(None, ge=0),
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    sku: Optional[str] = Query(None, description="Pedidos que contengan este SKU en sus items"),
    sort: str = Query("fecha", pattern="^(fecha|total)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    filtro = {}
    if estado:
        filtro["estado"] = estado
    if usuario_id:
        filtro["usuario_id"] = to_oid(usuario_id)
    if metodo_pago:
        filtro["metodo_pago"] = metodo_pago
    if total_min is not None:
        filtro["total"] = {"$gte": total_min}
    if fecha_desde or fecha_hasta:
        filtro["fecha"] = {}
        if fecha_desde:
            filtro["fecha"]["$gte"] = fecha_desde
        if fecha_hasta:
            filtro["fecha"]["$lte"] = fecha_hasta
    if sku:
        filtro["items.sku"] = sku      # consulta sobre array de subdocumentos
    return paginar(pedidos, filtro, page, limit, sort, ASCENDING if order == "asc" else DESCENDING)


@router.get("/{pedido_id}")
def obtener_pedido(pedido_id: str):
    doc = pedidos.find_one({"_id": to_oid(pedido_id)})
    if not doc:
        raise HTTPException(404, "Pedido no encontrado")
    return serialize(doc)


@router.patch("/{pedido_id}/estado")
def cambiar_estado(pedido_id: str, body: EstadoUpdate):
    oid = to_oid(pedido_id)
    pedido = pedidos.find_one({"_id": oid}, {"estado": 1, "items": 1})
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")
    actual = pedido["estado"]
    if body.estado not in TRANSICIONES[actual]:
        raise HTTPException(409, f"Transición no permitida: {actual} -> {body.estado}")

    # Si se cancela, se devuelve el stock a cada variación
    if body.estado == "cancelado":
        for it in pedido["items"]:
            productos.update_one({"_id": it["producto_id"], "variaciones.sku": it["sku"]},
                                 {"$inc": {"variaciones.$.stock": it["cantidad"]}})

    pedidos.update_one(
        {"_id": oid},
        {"$set": {"estado": body.estado},
         "$push": {"historial_estados": {"estado": body.estado, "fecha": datetime.now(timezone.utc)}}},
    )
    return {"estado_anterior": actual, "estado_nuevo": body.estado}
