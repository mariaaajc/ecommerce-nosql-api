# Diseño NoSQL — Tienda NoSQL API

## 1. Por qué MongoDB (y no Cassandra)

El caso de negocio es un catálogo con documentos heterogéneos (un producto de calzado tiene
tallas numéricas, una bocina tiene talla "Única") y consultas ad-hoc con muchos filtros
combinados. MongoDB encaja mejor que Cassandra porque:

- **Esquema flexible con validación**: cada colección puede tener campos opcionales y arrays
  de tamaño variable, y aun así `$jsonSchema` garantiza estructura mínima y tipos correctos.
- **Consultas ricas**: filtros sobre arrays de subdocumentos (`$elemMatch`), regex, rangos y
  lógicos en la misma consulta, sin diseñar una tabla por cada patrón de acceso.
- **Aggregation Pipeline**: los reportes de ventas mensuales y productos más vendidos se
  resuelven en la base de datos con `$group`, `$unwind`, `$lookup`.
- **Actualizaciones atómicas a nivel de documento**: `$inc` con operador posicional permite
  descontar stock de una variación específica sin condiciones de carrera.

Cassandra hubiera exigido *query-driven modeling* con una tabla desnormalizada por consulta
y no ofrece agregaciones ni filtros multicriterio sin índices secundarios costosos.

## 2. Colecciones y decisiones embeber vs. referenciar

### `productos`
```json
{
  "nombre": "Tenis Urbano Casa Blanca", "marca": "Casa Blanca", "categoria": "Calzado",
  "precio": 26.90, "etiquetas": ["oferta"], "activo": true, "rating_promedio": 4.0,
  "variaciones": [ { "sku": "SKU-1181", "talla": "38", "color": "Azul", "stock": 12 } ],
  "opiniones":   [ { "usuario_id": ObjectId, "usuario_nombre": "Ana Pérez",
                     "calificacion": 5, "comentario": "...", "fecha": ISODate } ]
}
```
| Relación | Decisión | Justificación |
|---|---|---|
| Producto → Variaciones (talla/color/stock) | **Embeber** | Relación 1:N pequeña y acotada (2–6 por producto). Siempre se consultan junto con el producto. El stock por variación se actualiza con `$inc` posicional de forma atómica. |
| Producto → Opiniones | **Embeber** | Se leen siempre en la ficha del producto; su cantidad crece lento y está acotada. Un solo `find()` trae producto + opiniones. `rating_promedio` se guarda precalculado para poder filtrar/ordenar sin recalcular. |
| Opinión → Usuario | **Referenciar + duplicar nombre** | Se guarda `usuario_id` (referencia) y `usuario_nombre` (copia) para mostrar la opinión sin `$lookup`. Patrón *extended reference*. |

### `usuarios`
| Relación | Decisión | Justificación |
|---|---|---|
| Usuario → Direcciones | **Embeber** | 1:N muy pequeña (1–3). Se consultan junto al perfil y se copian al pedido al comprar. |
| Usuario → Pedidos | **Referenciar** (desde pedidos) | Un cliente activo acumula pedidos sin límite; embeberlos haría crecer el documento hasta los 16 MB y penalizaría cada lectura del perfil. |

### `pedidos`
```json
{
  "usuario_id": ObjectId, "fecha": ISODate, "estado": "entregado", "metodo_pago": "tarjeta",
  "direccion_envio": { ...copia de la dirección... },
  "items": [ { "producto_id": ObjectId, "sku": "SKU-1181", "nombre": "Tenis Urbano Casa Blanca",
               "talla": "38", "color": "Azul", "precio_unitario": 26.90, "cantidad": 2, "subtotal": 53.80 } ],
  "subtotal": 53.80, "envio": 0.0, "total": 53.80,
  "historial_estados": [ { "estado": "pendiente", "fecha": ISODate }, ... ]
}
```
| Relación | Decisión | Justificación |
|---|---|---|
| Pedido → Usuario | **Referenciar** (`usuario_id`) | Ver arriba. El `$lookup` a `usuarios` solo se hace en reportes. |
| Pedido → Ítems | **Embeber con snapshot** | Un pedido es un evento histórico inmutable: se copia nombre, talla, color y **precio cobrado**. Si el catálogo cambia de precio, el recibo no cambia. Se conserva `producto_id` para poder unir con el catálogo actual en reportes. |
| Pedido → Dirección de envío | **Embeber (copia)** | Misma razón: si el usuario edita su dirección después, el pedido conserva a dónde se envió. |
| Pedido → Historial de estados | **Embeber** | Lista corta (máx. 4 entradas) que solo tiene sentido dentro del pedido. |

## 3. Validación con `$jsonSchema`

Las tres colecciones se crean con `validationLevel: strict` y `validationAction: error`
(`scripts/init_db.py`). Reglas destacadas:

- `productos.precio` ≥ 0.01, `variaciones` con `minItems: 1`, `stock` entero ≥ 0,
  `calificacion` entero 1–5, `additionalProperties: false` en el documento y en cada variación.
- `usuarios.email` con patrón de correo; `direcciones[].principal` booleano obligatorio.
- `pedidos.estado` y `metodo_pago` restringidos con `enum`; `items` con `minItems: 1`;
  `cantidad` entero ≥ 1.

Si un documento viola el esquema, MongoDB responde `WriteError` y la API lo traduce a HTTP 422.

## 4. Índices

| Colección | Índice | Motivo |
|---|---|---|
| productos | `variaciones.sku` único | Un SKU no puede repetirse entre productos |
| productos | `(categoria, precio)` | Filtro más común del catálogo con orden por precio |
| productos | `marca`, `etiquetas` | Filtros del listado (`etiquetas` es multikey) |
| productos | texto en `nombre`, `descripcion` | Búsqueda por palabra |
| usuarios | `email` único | Identidad del usuario |
| usuarios | `direcciones.departamento` | Filtro geográfico |
| pedidos | `(usuario_id, fecha desc)` | Historial de un usuario |
| pedidos | `(estado, fecha desc)` | Reportes y listados por estado |
| pedidos | `items.sku` | Buscar pedidos que contengan un SKU |

## 5. Consultas avanzadas implementadas

- **Multicriterio sobre arrays** (`GET /productos`): `$and` dinámico con `$or` + `$regex`,
  rangos `$gte/$lte`, igualdad dentro de array (`etiquetas`) y `$elemMatch` para que
  talla, color y stock se evalúen sobre la **misma** variación (evitando falsos positivos).
- **Escritura condicional atómica** (`POST /pedidos`): `updateOne` cuyo filtro exige
  `variaciones: {$elemMatch: {sku, stock: {$gte: cantidad}}}` y cuyo update hace
  `$inc: {"variaciones.$.stock": -cantidad}`. Si `matchedCount == 0`, no había stock.
- **Unicidad dentro de un array** (`POST /productos/{id}/opiniones`): filtro
  `"opiniones.usuario_id": {$ne: uid}` + `$push`.
- **Máquina de estados** (`PATCH /pedidos/{id}/estado`) con devolución de stock al cancelar.

## 6. Agregaciones

| Endpoint | Etapas | Qué responde |
|---|---|---|
| `/reportes/ventas-mensuales` | `$match` → `$group` por `$year/$month` → `$project` → `$sort` | Pedidos, unidades, ingresos y ticket promedio por mes |
| `/reportes/top-productos` | `$match` → `$unwind items` → `$group` → `$sort` → `$limit` → `$lookup productos` → `$project` | Más vendidos con categoría, marca, rating y stock actual |
| `/reportes/ventas-por-categoria` | `$unwind` → `$lookup` → `$unwind` → `$group` | Ingresos por categoría del catálogo |
| `/reportes/mejores-clientes` | `$group` por `usuario_id` → `$lookup usuarios` | Clientes por monto gastado |
| `/reportes/resumen-estados` | `$group` por estado | Embudo de pedidos |

Solo cuentan como venta los estados `pagado`, `enviado`, `entregado`.
