"""Endpoints de reportes: cada uno expone una tubería de agregación."""
from typing import Optional
from fastapi import APIRouter, Query
from app.db import pedidos
from app.utils import serialize

router = APIRouter(prefix="/reportes", tags=["Reportes"])

ESTADOS_VENTA = ["pagado", "enviado", "entregado"]   # pedidos que cuentan como venta


@router.get("/ventas-mensuales")
def ventas_mensuales(anio: Optional[int] = Query(None, ge=2000, le=2100)):
    """$match (estado y año) -> $group por año/mes -> $project -> $sort"""
    match = {"estado": {"$in": ESTADOS_VENTA}}
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"anio": {"$year": "$fecha"}, "mes": {"$month": "$fecha"}},
            "pedidos": {"$sum": 1},
            "ingresos": {"$sum": "$total"},
            "ticket_promedio": {"$avg": "$total"},
            "unidades": {"$sum": {"$sum": "$items.cantidad"}},
        }},
        {"$project": {
            "_id": 0,
            "anio": "$_id.anio", "mes": "$_id.mes",
            "pedidos": 1, "unidades": 1,
            "ingresos": {"$round": ["$ingresos", 2]},
            "ticket_promedio": {"$round": ["$ticket_promedio", 2]},
        }},
        {"$sort": {"anio": 1, "mes": 1}},
    ]
    if anio:
        pipeline.insert(1, {"$match": {"$expr": {"$eq": [{"$year": "$fecha"}, anio]}}})
    return serialize(list(pedidos.aggregate(pipeline)))


@router.get("/top-productos")
def top_productos(limit: int = Query(10, ge=1, le=50)):
    """$match -> $unwind items -> $group por producto -> $sort -> $limit -> $lookup productos"""
    pipeline = [
        {"$match": {"estado": {"$in": ESTADOS_VENTA}}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.producto_id",
            "nombre": {"$first": "$items.nombre"},
            "unidades_vendidas": {"$sum": "$items.cantidad"},
            "ingresos": {"$sum": "$items.subtotal"},
            "pedidos_distintos": {"$addToSet": "$_id"},
        }},
        {"$sort": {"unidades_vendidas": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": "productos",
            "localField": "_id",
            "foreignField": "_id",
            "as": "producto",
        }},
        {"$unwind": {"path": "$producto", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "producto_id": "$_id",
            "nombre": 1,
            "categoria": "$producto.categoria",
            "marca": "$producto.marca",
            "rating_promedio": "$producto.rating_promedio",
            "stock_actual": {"$sum": "$producto.variaciones.stock"},
            "unidades_vendidas": 1,
            "ingresos": {"$round": ["$ingresos", 2]},
            "pedidos_distintos": {"$size": "$pedidos_distintos"},
        }},
    ]
    return serialize(list(pedidos.aggregate(pipeline)))


@router.get("/ventas-por-categoria")
def ventas_por_categoria():
    """$unwind -> $lookup productos -> $group por categoría"""
    pipeline = [
        {"$match": {"estado": {"$in": ESTADOS_VENTA}}},
        {"$unwind": "$items"},
        {"$lookup": {"from": "productos", "localField": "items.producto_id",
                     "foreignField": "_id", "as": "producto"}},
        {"$unwind": "$producto"},
        {"$group": {
            "_id": "$producto.categoria",
            "unidades": {"$sum": "$items.cantidad"},
            "ingresos": {"$sum": "$items.subtotal"},
            "productos_distintos": {"$addToSet": "$items.producto_id"},
        }},
        {"$project": {
            "_id": 0, "categoria": "$_id", "unidades": 1,
            "ingresos": {"$round": ["$ingresos", 2]},
            "productos_distintos": {"$size": "$productos_distintos"},
        }},
        {"$sort": {"ingresos": -1}},
    ]
    return serialize(list(pedidos.aggregate(pipeline)))


@router.get("/mejores-clientes")
def mejores_clientes(limit: int = Query(10, ge=1, le=50)):
    """$group por usuario -> $lookup usuarios -> $project"""
    pipeline = [
        {"$match": {"estado": {"$in": ESTADOS_VENTA}}},
        {"$group": {
            "_id": "$usuario_id",
            "pedidos": {"$sum": 1},
            "gastado": {"$sum": "$total"},
            "ultima_compra": {"$max": "$fecha"},
        }},
        {"$sort": {"gastado": -1}},
        {"$limit": limit},
        {"$lookup": {"from": "usuarios", "localField": "_id", "foreignField": "_id", "as": "usuario"}},
        {"$unwind": "$usuario"},
        {"$project": {
            "_id": 0, "usuario_id": "$_id",
            "nombre": {"$concat": ["$usuario.nombre", " ", "$usuario.apellido"]},
            "email": "$usuario.email",
            "pedidos": 1,
            "gastado": {"$round": ["$gastado", 2]},
            "ultima_compra": 1,
        }},
    ]
    return serialize(list(pedidos.aggregate(pipeline)))


@router.get("/resumen-estados")
def resumen_estados():
    """Conteo y monto por estado del pedido ($group simple)."""
    pipeline = [
        {"$group": {"_id": "$estado", "pedidos": {"$sum": 1}, "monto": {"$sum": "$total"}}},
        {"$project": {"_id": 0, "estado": "$_id", "pedidos": 1, "monto": {"$round": ["$monto", 2]}}},
        {"$sort": {"pedidos": -1}},
    ]
    return serialize(list(pedidos.aggregate(pipeline)))
