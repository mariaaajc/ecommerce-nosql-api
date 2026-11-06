# Tienda NoSQL API — Catálogo e Historial de Pedidos

Proyecto final · Bases de Datos II (No Relacionales) · UEES
Stack: **Python 3.12 · FastAPI · MongoDB (Atlas o Docker) · PyMongo**

Caso de negocio: catálogo de e-commerce tipo almacén por departamentos con productos
(variaciones y opiniones embebidas), usuarios (direcciones embebidas) y pedidos
(referencia al usuario + ítems embebidos como snapshot de precio).

## Estructura

```
ecommerce-nosql-api/
├── app/
│   ├── main.py            # FastAPI, registra routers, /health
│   ├── config.py          # variables de entorno
│   ├── db.py              # conexión MongoClient
│   ├── schemas.py         # modelos Pydantic (validación de entrada)
│   ├── utils.py           # ObjectId <-> str, paginación
│   └── routers/
│       ├── productos.py   # CRUD + filtro multicriterio + opiniones + stock
│       ├── usuarios.py    # perfil + direcciones + pedidos del usuario
│       ├── pedidos.py     # lógica de negocio: stock atómico, snapshot, estados
│       └── reportes.py    # aggregation pipelines
├── scripts/
│   ├── init_db.py         # colecciones con $jsonSchema + índices
│   └── seed.py            # datos ficticios (120 productos, 100 usuarios, 180 pedidos)
├── docs/
│   ├── DISENO.md          # justificación del modelo NoSQL
│   └── postman_collection.json
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Opción A — Levantar con MongoDB Atlas (sin instalar nada local)

1. Crear un cluster gratuito (M0) en https://cloud.mongodb.com, un usuario de base de datos
   y permitir acceso desde cualquier IP (`0.0.0.0/0`) en *Network Access*.
2. Copiar la cadena de conexión (*Connect → Drivers → Python*).
3. En este repo:

```bash
cp .env.example .env          # editar MONGO_URI con la cadena de Atlas
pip install -r requirements.txt
python -m scripts.init_db     # crea colecciones con validación + índices
python -m scripts.seed        # carga datos de prueba
uvicorn app.main:app --reload
```

4. Abrir http://localhost:8000/docs (Swagger) — en Codespaces usar la URL que expone el puerto 8000.

## Opción B — Levantar todo con Docker

```bash
docker compose up --build
```

Levanta MongoDB 7 + la API; `init_db` y `seed` corren automáticamente. Swagger en http://localhost:8000/docs.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/productos` | Crear producto con variaciones |
| GET | `/productos` | Filtro multicriterio: `q, categoria, marca, precio_min/max, talla, color, en_stock, etiqueta, rating_min` + `sort, order, page, limit` |
| GET | `/productos/{id}` | Detalle con opiniones embebidas |
| PATCH | `/productos/{id}` | Actualizar campos |
| POST | `/productos/{id}/opiniones` | `$push` de opinión + recálculo de `rating_promedio` |
| PATCH | `/productos/{id}/variaciones/{sku}/stock` | `$inc` atómico sobre una variación (operador posicional `$`) |
| POST | `/usuarios` | Crear usuario con direcciones |
| GET | `/usuarios` | Buscar/paginar (`q`, `departamento`) |
| GET | `/usuarios/{id}` | Detalle |
| GET | `/usuarios/{id}/pedidos` | Pedidos referenciados del usuario |
| POST | `/usuarios/{id}/direcciones` | `$push` de dirección |
| POST | `/pedidos` | **Lógica de negocio**: valida stock por variación, descuenta atómicamente, guarda snapshot de precios |
| GET | `/pedidos` | Filtros: `estado, usuario_id, metodo_pago, total_min, fecha_desde/hasta, sku` + paginación |
| GET | `/pedidos/{id}` | Detalle |
| PATCH | `/pedidos/{id}/estado` | Máquina de estados; cancelar devuelve stock |
| GET | `/reportes/ventas-mensuales` | `$match → $group ($year/$month) → $project → $sort` |
| GET | `/reportes/top-productos` | `$unwind → $group → $sort → $limit → $lookup productos` |
| GET | `/reportes/ventas-por-categoria` | `$unwind → $lookup → $group` |
| GET | `/reportes/mejores-clientes` | `$group → $lookup usuarios` |
| GET | `/reportes/resumen-estados` | `$group` por estado |
| GET | `/health` | Ping a Mongo + conteos |

## Probar rápido

```bash
curl "http://localhost:8000/productos?categoria=Calzado&en_stock=true&precio_max=80&sort=precio&order=asc"
curl "http://localhost:8000/reportes/top-productos?limit=5"
```

La colección Postman está en `docs/postman_collection.json`; Swagger/OpenAPI en `/docs` y `/openapi.json`.

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `MONGO_URI` | Cadena de conexión | `mongodb+srv://user:pass@cluster0.xxx.mongodb.net/` |
| `MONGO_DB` | Nombre de la base | `tienda_nosql` |
