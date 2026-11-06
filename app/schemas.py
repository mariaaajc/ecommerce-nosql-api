"""Modelos Pydantic: validan el cuerpo de las peticiones antes de tocar la BD.
La validación definitiva la hace MongoDB con $jsonSchema (ver scripts/init_db.py)."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field

# ---------- Productos ----------
class Variacion(BaseModel):
    sku: str = Field(..., min_length=3)
    talla: str
    color: str
    stock: int = Field(..., ge=0)


class ProductoIn(BaseModel):
    nombre: str = Field(..., min_length=2)
    marca: str
    categoria: str
    precio: float = Field(..., gt=0)
    descripcion: Optional[str] = None
    etiquetas: list[str] = []
    variaciones: list[Variacion] = Field(..., min_length=1)
    activo: bool = True


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    marca: Optional[str] = None
    categoria: Optional[str] = None
    precio: Optional[float] = Field(None, gt=0)
    descripcion: Optional[str] = None
    etiquetas: Optional[list[str]] = None
    activo: Optional[bool] = None


class OpinionIn(BaseModel):
    usuario_id: str
    calificacion: int = Field(..., ge=1, le=5)
    comentario: str = Field(..., min_length=3, max_length=500)


class StockAjuste(BaseModel):
    cantidad: int = Field(..., description="Positivo para entrada, negativo para salida")


# ---------- Usuarios ----------
class Direccion(BaseModel):
    alias: str = "Casa"
    departamento: str
    municipio: str
    detalle: str
    principal: bool = False


class UsuarioIn(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    telefono: Optional[str] = None
    direcciones: list[Direccion] = []


# ---------- Pedidos ----------
class ItemPedidoIn(BaseModel):
    producto_id: str
    sku: str
    cantidad: int = Field(..., ge=1)


class PedidoIn(BaseModel):
    usuario_id: str
    items: list[ItemPedidoIn] = Field(..., min_length=1)
    metodo_pago: Literal["tarjeta", "efectivo", "transferencia"]
    direccion_alias: Optional[str] = Field(None, description="Alias de la dirección del usuario; si se omite se usa la principal")


class EstadoUpdate(BaseModel):
    estado: Literal["pagado", "enviado", "entregado", "cancelado"]
