"""Conexión única a MongoDB compartida por toda la API."""
from pymongo import MongoClient
from app.config import MONGO_URI, MONGO_DB

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

productos = db["productos"]
usuarios = db["usuarios"]
pedidos = db["pedidos"]
