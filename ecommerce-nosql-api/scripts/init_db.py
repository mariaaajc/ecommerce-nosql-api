"""Crea las colecciones con reglas de validación $jsonSchema e índices.
Uso: python -m scripts.init_db
Es idempotente: si la colección ya existe, actualiza el validador con collMod."""
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import CollectionInvalid
from app.db import db

SCHEMA_PRODUCTOS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["nombre", "marca", "categoria", "precio", "variaciones", "activo", "creado_en"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "nombre": {"bsonType": "string", "minLength": 2, "maxLength": 120},
            "marca": {"bsonType": "string"},
            "categoria": {"bsonType": "string"},
            "descripcion": {"bsonType": ["string", "null"]},
            "precio": {"bsonType": ["double", "int"], "minimum": 0.01},
            "etiquetas": {"bsonType": "array", "items": {"bsonType": "string"}},
            "activo": {"bsonType": "bool"},
            "rating_promedio": {"bsonType": ["double", "int", "null"], "minimum": 1, "maximum": 5},
            "creado_en": {"bsonType": "date"},
            "variaciones": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["sku", "talla", "color", "stock"],
                    "additionalProperties": False,
                    "properties": {
                        "sku": {"bsonType": "string", "minLength": 3},
                        "talla": {"bsonType": "string"},
                        "color": {"bsonType": "string"},
                        "stock": {"bsonType": "int", "minimum": 0},
                    },
                },
            },
            "opiniones": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["usuario_id", "calificacion", "comentario", "fecha"],
                    "properties": {
                        "usuario_id": {"bsonType": "objectId"},
                        "usuario_nombre": {"bsonType": "string"},
                        "calificacion": {"bsonType": "int", "minimum": 1, "maximum": 5},
                        "comentario": {"bsonType": "string", "maxLength": 500},
                        "fecha": {"bsonType": "date"},
                    },
                },
            },
        },
    }
}

SCHEMA_USUARIOS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["nombre", "apellido", "email", "direcciones", "registrado_en"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "nombre": {"bsonType": "string"},
            "apellido": {"bsonType": "string"},
            "email": {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
            "telefono": {"bsonType": ["string", "null"]},
            "registrado_en": {"bsonType": "date"},
            "direcciones": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["alias", "departamento", "municipio", "detalle", "principal"],
                    "properties": {
                        "alias": {"bsonType": "string"},
                        "departamento": {"bsonType": "string"},
                        "municipio": {"bsonType": "string"},
                        "detalle": {"bsonType": "string"},
                        "principal": {"bsonType": "bool"},
                    },
                },
            },
        },
    }
}

SCHEMA_PEDIDOS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["usuario_id", "fecha", "estado", "metodo_pago", "direccion_envio",
                     "items", "subtotal", "envio", "total", "historial_estados"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "usuario_id": {"bsonType": "objectId"},
            "fecha": {"bsonType": "date"},
            "estado": {"enum": ["pendiente", "pagado", "enviado", "entregado", "cancelado"]},
            "metodo_pago": {"enum": ["tarjeta", "efectivo", "transferencia"]},
            "direccion_envio": {"bsonType": "object"},
            "subtotal": {"bsonType": ["double", "int"], "minimum": 0},
            "envio": {"bsonType": ["double", "int"], "minimum": 0},
            "total": {"bsonType": ["double", "int"], "minimum": 0},
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["producto_id", "sku", "nombre", "precio_unitario", "cantidad", "subtotal"],
                    "properties": {
                        "producto_id": {"bsonType": "objectId"},
                        "sku": {"bsonType": "string"},
                        "nombre": {"bsonType": "string"},
                        "talla": {"bsonType": "string"},
                        "color": {"bsonType": "string"},
                        "precio_unitario": {"bsonType": ["double", "int"], "minimum": 0},
                        "cantidad": {"bsonType": "int", "minimum": 1},
                        "subtotal": {"bsonType": ["double", "int"], "minimum": 0},
                    },
                },
            },
            "historial_estados": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["estado", "fecha"],
                    "properties": {"estado": {"bsonType": "string"}, "fecha": {"bsonType": "date"}},
                },
            },
        },
    }
}

SCHEMAS = {"productos": SCHEMA_PRODUCTOS, "usuarios": SCHEMA_USUARIOS, "pedidos": SCHEMA_PEDIDOS}


def crear_o_actualizar(nombre, schema):
    try:
        db.create_collection(nombre, validator=schema, validationLevel="strict", validationAction="error")
        print(f"[init_db] colección '{nombre}' creada con $jsonSchema")
    except CollectionInvalid:
        db.command("collMod", nombre, validator=schema, validationLevel="strict", validationAction="error")
        print(f"[init_db] colección '{nombre}' ya existía; validador actualizado")


def crear_indices():
    p, u, o = db["productos"], db["usuarios"], db["pedidos"]
    p.create_index([("variaciones.sku", ASCENDING)], unique=True, name="ux_sku")
    p.create_index([("categoria", ASCENDING), ("precio", ASCENDING)], name="ix_categoria_precio")
    p.create_index([("marca", ASCENDING)], name="ix_marca")
    p.create_index([("etiquetas", ASCENDING)], name="ix_etiquetas")
    p.create_index([("nombre", TEXT), ("descripcion", TEXT)], name="tx_nombre_desc", default_language="spanish")
    u.create_index([("email", ASCENDING)], unique=True, name="ux_email")
    u.create_index([("direcciones.departamento", ASCENDING)], name="ix_departamento")
    o.create_index([("usuario_id", ASCENDING), ("fecha", DESCENDING)], name="ix_usuario_fecha")
    o.create_index([("estado", ASCENDING), ("fecha", DESCENDING)], name="ix_estado_fecha")
    o.create_index([("items.sku", ASCENDING)], name="ix_items_sku")
    print("[init_db] índices creados")


if __name__ == "__main__":
    for nombre, schema in SCHEMAS.items():
        crear_o_actualizar(nombre, schema)
    crear_indices()
    print("[init_db] listo")
