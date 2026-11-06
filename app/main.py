"""Punto de entrada de la API. Correr con: uvicorn app.main:app --reload"""
from fastapi import FastAPI
from app.db import client, db
from app.routers import productos, usuarios, pedidos, reportes

app = FastAPI(
    title="Tienda NoSQL API",
    description="Catálogo e historial de pedidos de e-commerce sobre MongoDB. "
                "Proyecto final — Bases de Datos II (No Relacionales), UEES.",
    version="1.0.0",
)

app.include_router(productos.router)
app.include_router(usuarios.router)
app.include_router(pedidos.router)
app.include_router(reportes.router)


@app.get("/", tags=["Salud"])
def raiz():
    return {"ok": True, "docs": "/docs"}


@app.get("/health", tags=["Salud"])
def health():
    """Verifica conexión con MongoDB y devuelve conteos por colección."""
    client.admin.command("ping")
    return {
        "mongo": "ok",
        "db": db.name,
        "colecciones": {c: db[c].estimated_document_count() for c in ["productos", "usuarios", "pedidos"]},
    }
