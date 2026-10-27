"""Carga datos ficticios pero realistas: ~120 productos, 100 usuarios, 180 pedidos.
Uso: python -m scripts.seed          (borra y recarga las tres colecciones)
Los pedidos se generan sobre los últimos 12 meses para que los reportes tengan datos."""
import random
from datetime import datetime, timedelta, timezone
from faker import Faker
from app.db import db, productos, usuarios, pedidos

fake = Faker("es_MX")
random.seed(42)
Faker.seed(42)

# ---------- Catálogo tipo almacén por departamentos ----------
CATALOGO = {
    "Ropa Dama":      (["Blusa", "Vestido", "Pantalón", "Falda", "Blazer", "Jeans"],     (14.99, 89.99), ["XS", "S", "M", "L", "XL"]),
    "Ropa Caballero": (["Camisa", "Polo", "Pantalón", "Chaqueta", "Jeans", "Suéter"],    (16.99, 99.99), ["S", "M", "L", "XL", "XXL"]),
    "Calzado":        (["Tenis", "Botines", "Sandalias", "Mocasines", "Tacones"],        (24.99, 129.99), ["36", "37", "38", "39", "40", "41", "42"]),
    "Hogar":          (["Juego de sábanas", "Edredón", "Toalla", "Cortina", "Almohada"], (9.99, 149.99), ["Individual", "Matrimonial", "Queen", "King"]),
    "Electrónica":    (["Audífonos", "Bocina", "Smartwatch", "Cargador", "Tablet"],     (19.99, 399.99), ["Única"]),
    "Perfumería":     (["Perfume", "Colonia", "Set de fragancias", "Crema corporal"],    (12.99, 119.99), ["50 ml", "100 ml"]),
    "Juguetes":       (["Peluche", "Rompecabezas", "Set de bloques", "Muñeca", "Carro"], (7.99, 79.99), ["Única"]),
    "Deportes":       (["Licra", "Camiseta dry-fit", "Short", "Mochila", "Botella"],     (9.99, 69.99), ["S", "M", "L", "XL"]),
}
MARCAS = ["Nova", "Aurelia", "Kairo", "Monte Verde", "Lumen", "Casa Blanca", "Zenith", "Pulso", "Ámbar", "Tessa"]
COLORES = ["Negro", "Blanco", "Azul", "Rojo", "Beige", "Gris", "Verde", "Rosa", "Café"]
ADJETIVOS = ["Clásico", "Premium", "Urbano", "Essential", "Sport", "Elegance", "Comfort", "Vintage"]
ETIQUETAS = ["nuevo", "oferta", "temporada", "exclusivo", "bestseller", "eco", "regalo"]

DEPARTAMENTOS = {
    "San Salvador": ["San Salvador", "Soyapango", "Mejicanos", "Santa Tecla", "Antiguo Cuscatlán", "Apopa"],
    "La Libertad": ["Santa Tecla", "Colón", "Zaragoza", "Quezaltepeque"],
    "Santa Ana": ["Santa Ana", "Chalchuapa", "Metapán"],
    "San Miguel": ["San Miguel", "Chinameca"],
    "Sonsonate": ["Sonsonate", "Izalco", "Acajutla"],
    "La Paz": ["Zacatecoluca", "Olocuilta"],
    "Usulután": ["Usulután", "Santiago de María"],
    "Ahuachapán": ["Ahuachapán", "Atiquizaya"],
}
COMENTARIOS = [
    "Excelente calidad, tal como se ve en la foto.", "Buen producto pero la talla queda un poco pequeña.",
    "Llegó rápido y bien empacado.", "El color es un poco distinto al de la imagen.",
    "Muy cómodo, lo volvería a comprar.", "Relación precio-calidad aceptable.",
    "Superó mis expectativas.", "El material se siente algo delgado.", "Perfecto para regalo.",
    "No era lo que esperaba, pero cumple.",
]

AHORA = datetime.now(timezone.utc)


def fecha_aleatoria(dias_atras_max=365):
    return AHORA - timedelta(days=random.randint(0, dias_atras_max), hours=random.randint(0, 23), minutes=random.randint(0, 59))


def generar_productos(n=120):
    docs, sku_num = [], 1000
    for _ in range(n):
        categoria = random.choice(list(CATALOGO))
        tipos, (pmin, pmax), tallas = CATALOGO[categoria]
        marca = random.choice(MARCAS)
        nombre = f"{random.choice(tipos)} {random.choice(ADJETIVOS)} {marca}"
        variaciones = []
        for talla in random.sample(tallas, k=min(len(tallas), random.randint(1, 3))):
            for color in random.sample(COLORES, k=random.randint(1, 2)):
                sku_num += 1
                variaciones.append({"sku": f"SKU-{sku_num}", "talla": talla, "color": color,
                                    "stock": random.choice([0, 3, 5, 8, 12, 20, 35, 50])})
        docs.append({
            "nombre": nombre, "marca": marca, "categoria": categoria,
            "descripcion": fake.sentence(nb_words=12),
            "precio": round(random.uniform(pmin, pmax), 2),
            "etiquetas": random.sample(ETIQUETAS, k=random.randint(0, 3)),
            "variaciones": variaciones,
            "opiniones": [], "rating_promedio": None,
            "activo": random.random() > 0.05,
            "creado_en": fecha_aleatoria(540),
        })
    return docs


def generar_usuarios(n=100):
    docs, emails = [], set()
    while len(docs) < n:
        nombre, apellido = fake.first_name(), fake.last_name()
        email = f"{nombre}.{apellido}{random.randint(1, 999)}@{fake.free_email_domain()}".lower()
        email = email.replace(" ", "").replace("ñ", "n").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if email in emails:
            continue
        emails.add(email)
        direcciones = []
        for i in range(random.randint(1, 2)):
            depto = random.choice(list(DEPARTAMENTOS))
            direcciones.append({
                "alias": "Casa" if i == 0 else "Oficina",
                "departamento": depto,
                "municipio": random.choice(DEPARTAMENTOS[depto]),
                "detalle": f"{fake.street_name()} #{random.randint(1, 250)}, {fake.secondary_address()}",
                "principal": i == 0,
            })
        docs.append({
            "nombre": nombre, "apellido": apellido, "email": email,
            "telefono": f"{random.choice(['6', '7'])}{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "direcciones": direcciones,
            "registrado_en": fecha_aleatoria(720),
        })
    return docs


def generar_pedidos(prods, users, n=180):
    """Genera pedidos con snapshot de precio y descuenta stock de las variaciones elegidas."""
    docs = []
    estados_pesos = [("pendiente", 8), ("pagado", 20), ("enviado", 22), ("entregado", 42), ("cancelado", 8)]
    for _ in range(n):
        user = random.choice(users)
        fecha = fecha_aleatoria(365)
        items, usados = [], set()
        for _ in range(random.randint(1, 4)):
            prod = random.choice([p for p in prods if p["activo"]])
            var = random.choice(prod["variaciones"])
            if var["sku"] in usados:
                continue
            usados.add(var["sku"])
            cant = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
            # Precio histórico: puede diferir del actual para demostrar el snapshot
            precio_hist = round(prod["precio"] * random.choice([1, 1, 1, 0.9, 0.85, 1.05]), 2)
            items.append({
                "producto_id": prod["_id"], "sku": var["sku"], "nombre": prod["nombre"],
                "talla": var["talla"], "color": var["color"],
                "precio_unitario": precio_hist, "cantidad": cant, "subtotal": round(precio_hist * cant, 2),
            })
        subtotal = round(sum(i["subtotal"] for i in items), 2)
        envio = 0.0 if subtotal >= 50 else 3.99
        estado = random.choices([e for e, _ in estados_pesos], weights=[w for _, w in estados_pesos])[0]
        # Historial coherente con el estado final
        cadena = {"pendiente": ["pendiente"], "pagado": ["pendiente", "pagado"],
                  "enviado": ["pendiente", "pagado", "enviado"],
                  "entregado": ["pendiente", "pagado", "enviado", "entregado"],
                  "cancelado": ["pendiente", "cancelado"]}[estado]
        historial = [{"estado": e, "fecha": fecha + timedelta(days=i)} for i, e in enumerate(cadena)]
        docs.append({
            "usuario_id": user["_id"], "fecha": fecha, "estado": estado,
            "metodo_pago": random.choice(["tarjeta", "tarjeta", "efectivo", "transferencia"]),
            "direccion_envio": user["direcciones"][0],
            "items": items, "subtotal": subtotal, "envio": envio, "total": round(subtotal + envio, 2),
            "historial_estados": historial,
        })
    return docs


def generar_opiniones(prods, users):
    """Embebe 0-5 opiniones por producto y calcula rating_promedio."""
    for p in prods:
        opinadores = random.sample(users, k=random.randint(0, 5))
        p["opiniones"] = [{
            "usuario_id": u["_id"], "usuario_nombre": f"{u['nombre']} {u['apellido']}",
            "calificacion": random.choices([1, 2, 3, 4, 5], weights=[5, 8, 17, 35, 35])[0],
            "comentario": random.choice(COMENTARIOS), "fecha": fecha_aleatoria(300),
        } for u in opinadores]
        if p["opiniones"]:
            p["rating_promedio"] = round(sum(o["calificacion"] for o in p["opiniones"]) / len(p["opiniones"]), 2)


def run():
    productos.delete_many({}); usuarios.delete_many({}); pedidos.delete_many({})
    prods = generar_productos()
    res = productos.insert_many(prods)
    for d, _id in zip(prods, res.inserted_ids):
        d["_id"] = _id
    users = generar_usuarios()
    res = usuarios.insert_many(users)
    for d, _id in zip(users, res.inserted_ids):
        d["_id"] = _id
    generar_opiniones(prods, users)
    for p in prods:
        productos.update_one({"_id": p["_id"]}, {"$set": {"opiniones": p["opiniones"], "rating_promedio": p["rating_promedio"]}})
    peds = generar_pedidos(prods, users)
    pedidos.insert_many(peds)
    print(f"[seed] productos={productos.count_documents({})} usuarios={usuarios.count_documents({})} pedidos={pedidos.count_documents({})}")


if __name__ == "__main__":
    run()
