"""
Management command: seed_staging

Seeds the staging database with 8 test scenarios from issue #11
or real demo products with generated images.

Idempotent — running twice does not duplicate records.
All seed records use a [SEED] or [DEMO] prefix in their names for easy identification.

Usage:
    python manage.py seed_staging
    python manage.py seed_staging --dry-run
    python manage.py seed_staging --clear
    python manage.py seed_staging --real-data
    python manage.py seed_staging --real-data --generate-images
    python manage.py seed_staging --demo
    python manage.py seed_staging --demo --dry-run
"""

import os
import uuid
import urllib.request
from io import BytesIO

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from django.db.models import Q
from PIL import Image, ImageDraw, ImageFont

from api.models import (
    CategoriasModel,
    ColorModel,
    ProductosModel,
    ProductoVariantesModel,
)

# ----------------------------------------------------------------
# Placeholder image path — used as fallback
# ----------------------------------------------------------------
PLACEHOLDER_IMAGE = "seed/placeholder.jpg"

# ----------------------------------------------------------------
# Image generation settings
# ----------------------------------------------------------------
IMAGE_WIDTH = 600
IMAGE_HEIGHT = 400
IMAGE_QUALITY = 85

# Color palette for real products
PRODUCT_COLORS = {
    "Taza": (139, 90, 43),       # Brown
    "Morral": (70, 130, 180),    # Steel blue
    "Playera": (255, 99, 71),    # Tomato
    "Sudadera": (106, 90, 205),  # Slate blue
    "Llavero": (192, 192, 192),  # Silver
    "Pin": (255, 215, 0),        # Gold
    "Libreta": (60, 179, 113),   # Medium sea green
    "Pluma": (30, 144, 255),     # Dodger blue
}

# Seed scenario colors
SEED_COLORS = {
    1: (34, 139, 34),   # Green
    2: (220, 20, 60),   # Crimson
    3: (255, 140, 0),   # Dark orange
    4: (128, 0, 128),   # Purple
    5: (0, 128, 128),   # Teal
    6: (128, 128, 0),   # Olive
    7: (70, 130, 180),  # Steel blue
    8: (210, 105, 30),  # Chocolate
}

# ----------------------------------------------------------------
# Shared seed helpers
# ----------------------------------------------------------------
SEED_PREFIX = "[SEED]"
CATEGORY_NAME = f"{SEED_PREFIX} Staging"
COLOR_NAMES = ["Rojo", "Azul", "Verde", "Negro", "Blanco", "Gris", "Rosa"]
COLOR_HEX_MAP = {
    "Rojo": "#FF0000",
    "Azul": "#0000FF",
    "Verde": "#00FF00",
    "Negro": "#000000",
    "Blanco": "#FFFFFF",
    "Gris": "#808080",
    "Rosa": "#FFC0CB",
}

# ----------------------------------------------------------------
# Each scenario is a dict with:
#   id          — human-readable scenario number
#   name        — scenario description (for output)
#   nombre      — product name (must be unique across seed records)
#   precio      — base price
#   disponible  — product-level kill-switch
#   variants    — list of variant dicts (empty list = no variants)
#
# Variant dict keys: color_name, item, precio, stock, activo
# ----------------------------------------------------------------
SCENARIOS = [
    # ---- S1: Available product with multiple in-stock variants ----
    {
        "id": 1,
        "name": "Multiple in-stock variants",
        "nombre": f"{SEED_PREFIX} S1 - Variantes en stock",
        "precio": 100.00,
        "disponible": True,
        "variants": [
            {"color_name": "Rojo", "item": "S1-R", "precio": None, "stock": 10, "activo": True},
            {"color_name": "Azul", "item": "S1-A", "precio": None, "stock": 5, "activo": True},
            {"color_name": "Negro", "item": "S1-N", "precio": None, "stock": 3, "activo": True},
        ],
    },
    # ---- S2: Variant price override different from base price ----
    {
        "id": 2,
        "name": "Variant price override ≠ base price",
        "nombre": f"{SEED_PREFIX} S2 - Precio variante distinto",
        "precio": 80.00,
        "disponible": True,
        "variants": [
            {"color_name": "Rojo", "item": "S2-R", "precio": 120.00, "stock": 7, "activo": True},
            {"color_name": "Azul", "item": "S2-A", "precio": None, "stock": 5, "activo": True},
        ],
    },
    # ---- S3: Variant price = 0.00 (explicit zero) ----
    {
        "id": 3,
        "name": "Variant price = 0.00 (explicit zero)",
        "nombre": f"{SEED_PREFIX} S3 - Precio variante cero",
        "precio": 50.00,
        "disponible": True,
        "variants": [
            {"color_name": "Verde", "item": "S3-V", "precio": 0.00, "stock": 2, "activo": True},
        ],
    },
    # ---- S4: All variants stock = 0 ----
    {
        "id": 4,
        "name": "All variants stock = 0",
        "nombre": f"{SEED_PREFIX} S4 - Todo sin stock",
        "precio": 60.00,
        "disponible": True,
        "variants": [
            {"color_name": "Rojo", "item": "S4-R", "precio": None, "stock": 0, "activo": True},
            {"color_name": "Azul", "item": "S4-A", "precio": None, "stock": 0, "activo": True},
        ],
    },
    # ---- S5: Product with no variants at all ----
    {
        "id": 5,
        "name": "Product with no variants",
        "nombre": f"{SEED_PREFIX} S5 - Sin variantes",
        "precio": 70.00,
        "disponible": True,
        "variants": [],
    },
    # ---- S6: Product disponible=False (hidden by kill-switch) ----
    {
        "id": 6,
        "name": "Product disponible=False (hidden)",
        "nombre": f"{SEED_PREFIX} S6 - Producto oculto",
        "precio": 90.00,
        "disponible": False,
        "variants": [
            {"color_name": "Negro", "item": "S6-N", "precio": None, "stock": 10, "activo": True},
        ],
    },
    # ---- S7: At least one variant activo=False ----
    {
        "id": 7,
        "name": "At least one variant activo=False",
        "nombre": f"{SEED_PREFIX} S7 - Variante inactiva",
        "precio": 110.00,
        "disponible": True,
        "variants": [
            {"color_name": "Rojo", "item": "S7-R", "precio": None, "stock": 4, "activo": True},
            {"color_name": "Azul", "item": "S7-A", "precio": None, "stock": 2, "activo": False},
            {"color_name": "Verde", "item": "S7-V", "precio": None, "stock": 6, "activo": True},
        ],
    },
    # ---- S8: Two variants with same non-empty item, cross-product ----
    {
        "id": 8,
        "name": "Cross-product same item value",
        "nombre": f"{SEED_PREFIX} S8a - Item compartido A",
        "precio": 130.00,
        "disponible": True,
        "variants": [
            {"color_name": "Blanco", "item": "SHARED-001", "precio": None, "stock": 8, "activo": True},
        ],
    },
    {
        "id": 8,
        "name": "Cross-product same item value",
        "nombre": f"{SEED_PREFIX} S8b - Item compartido B",
        "precio": 140.00,
        "disponible": True,
        "variants": [
            {"color_name": "Blanco", "item": "SHARED-001", "precio": None, "stock": 3, "activo": True},
        ],
    },
]

# ----------------------------------------------------------------
# Real demo products (without [SEED] prefix)
# These are products that look good in the catalog UI
# ----------------------------------------------------------------
REAL_PRODUCTS = [
    {
        "id": 101,
        "nombre": "Taza Clásica Bukis",
        "precio": 89.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Taza cerámica 350ml con diseño exclusivo.",
        "peso": 0.35,
        "medidas": "10x8x9 cm",
        "capacidad": "350ml",
        "disponible": True,
        "variants": [
            {"color_name": "Rojo", "item": "TCB-R", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Azul", "item": "TCB-A", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Negro", "item": "TCB-N", "precio": None, "stock": 10, "activo": True},
        ],
    },
    {
        "id": 102,
        "nombre": "Taza Mágica Bukis",
        "precio": 129.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Taza que cambia de color con el calor.",
        "peso": 0.35,
        "medidas": "10x8x9 cm",
        "capacidad": "350ml",
        "disponible": True,
        "variants": [
            {"color_name": "Blanco", "item": "TMB-B", "precio": None, "stock": 8, "activo": True},
        ],
    },
    {
        "id": 103,
        "nombre": "Morral Escolar",
        "precio": 349.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Morral espacioso con compartimento para laptop.",
        "peso": 0.8,
        "medidas": "40x30x15 cm",
        "capacidad": "20L",
        "disponible": True,
        "variants": [
            {"color_name": "Azul", "item": "ME-A", "precio": None, "stock": 18, "activo": True},
            {"color_name": "Gris", "item": "ME-G", "precio": None, "stock": 10, "activo": True},
            {"color_name": "Negro", "item": "ME-N", "precio": None, "stock": 25, "activo": True},
        ],
    },
    {
        "id": 104,
        "nombre": "Morral Deportivo",
        "precio": 279.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Morral para gimnasio con compartimento para zapatos.",
        "peso": 0.6,
        "medidas": "50x25x20 cm",
        "capacidad": "25L",
        "disponible": True,
        "variants": [
            {"color_name": "Azul", "item": "MD-A", "precio": None, "stock": 5, "activo": True},
            {"color_name": "Negro", "item": "MD-N", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Rojo", "item": "MD-R", "precio": None, "stock": 8, "activo": True},
        ],
    },
    {
        "id": 105,
        "nombre": "Playera Unisex",
        "precio": 199.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Playera 100% algodón con logo Bukis.",
        "peso": 0.2,
        "medidas": "S-XXL",
        "capacidad": None,
        "disponible": True,
        "variants": [
            {"color_name": "Blanco", "item": "PU-B", "precio": None, "stock": 28, "activo": True},
            {"color_name": "Gris", "item": "PU-G", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Negro", "item": "PU-N", "precio": None, "stock": 25, "activo": True},
            {"color_name": "Rojo", "item": "PU-R", "precio": None, "stock": 10, "activo": True},
        ],
    },
    {
        "id": 106,
        "nombre": "Sudadera Con Capucha",
        "precio": 449.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Sudadera premium con capucha y bolsillo canguro.",
        "peso": 0.5,
        "medidas": "S-XXL",
        "capacidad": None,
        "disponible": True,
        "variants": [
            {"color_name": "Azul", "item": "SC-A", "precio": None, "stock": 8, "activo": True},
            {"color_name": "Gris", "item": "SC-G", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Negro", "item": "SC-N", "precio": None, "stock": 20, "activo": True},
        ],
    },
    {
        "id": 107,
        "nombre": "Llavero Metálico",
        "precio": 59.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Llavero metálico con logo grabado.",
        "peso": 0.05,
        "medidas": "5x3x0.5 cm",
        "capacidad": None,
        "disponible": True,
        "variants": [
            {"color_name": "Gris", "item": "LM-G", "precio": None, "stock": 40, "activo": True},
            {"color_name": "Negro", "item": "LM-N", "precio": None, "stock": 50, "activo": True},
        ],
    },
    {
        "id": 108,
        "nombre": "Pin Esmaltado",
        "precio": 79.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Pin esmaltado con diseño exclusivo Bukis.",
        "peso": 0.02,
        "medidas": "3x3 cm",
        "capacidad": None,
        "disponible": True,
        "variants": [
            {"color_name": "Azul", "item": "PE-A", "precio": None, "stock": 35, "activo": True},
            {"color_name": "Rojo", "item": "PE-R", "precio": None, "stock": 34, "activo": True},
            {"color_name": "Rosa", "item": "PE-RO", "precio": None, "stock": 20, "activo": True},
        ],
    },
    {
        "id": 109,
        "nombre": "Libreta A5",
        "precio": 119.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Libreta A5 con hojas de puntos y portada rígida.",
        "peso": 0.3,
        "medidas": "21x14.8x1 cm",
        "capacidad": "80 hojas",
        "disponible": True,
        "variants": [
            {"color_name": "Negro", "item": "LA-N", "precio": None, "stock": 22, "activo": True},
            {"color_name": "Rosa", "item": "LA-RO", "precio": None, "stock": 10, "activo": True},
        ],
    },
    {
        "id": 110,
        "nombre": "Pluma Grabada",
        "precio": 49.00,
        "imagen": "img/products/placeholder.jpg",
        "descripcion": "Pluma metálica con grabado personalizado.",
        "peso": 0.03,
        "medidas": "14x1 cm",
        "capacidad": None,
        "disponible": True,
        "variants": [
            {"color_name": "Azul", "item": "PG-A", "precio": None, "stock": 45, "activo": True},
            {"color_name": "Negro", "item": "PG-N", "precio": None, "stock": 60, "activo": True},
            {"color_name": "Rojo", "item": "PG-R", "precio": None, "stock": 3, "activo": True},
        ],
    },
]

# ----------------------------------------------------------------
# Demo products (--demo flag)
# Generic non-Bukis products with picsum.photos images.
# 20 products across 5 categories — good for testing category filtering.
# ----------------------------------------------------------------
DEMO_PREFIX = "[DEMO]"

DEMO_CATEGORIES = [
    f"{DEMO_PREFIX} Ropa",
    f"{DEMO_PREFIX} Accesorios",
    f"{DEMO_PREFIX} Hogar",
    f"{DEMO_PREFIX} Oficina",
    f"{DEMO_PREFIX} Tecnología",
]

DEMO_COLOR_NAMES = [
    "Negro", "Blanco", "Gris", "Azul", "Rojo",
    "Verde", "Rosa", "Amarillo", "Naranja", "Morado",
    "Marrón", "Beige",
]
DEMO_COLOR_HEX = {
    "Negro": "#000000", "Blanco": "#FFFFFF", "Gris": "#808080",
    "Azul": "#0000FF", "Rojo": "#FF0000", "Verde": "#00FF00",
    "Rosa": "#FFC0CB", "Amarillo": "#FFFF00", "Naranja": "#FFA500",
    "Morado": "#800080", "Marrón": "#8B4513", "Beige": "#F5F5DC",
}

# Each demo product references a category index and variants with color names.
# Image URLs used as seeds for picsum download (unique per product).
DEMO_PRODUCTS = [
    # ---- Ropa (cat 0) ----
    {
        "id": 201,
        "cat": 0,
        "nombre": f"{DEMO_PREFIX} Camiseta Básica Algodón",
        "precio": 159.00,
        "descripcion": "Camiseta 100% algodón peinado, corte regular. Ideal para uso diario.",
        "peso": 0.20, "medidas": "S-XXL", "capacidad": None, "disponible": True,
        "picsum_seed": 1001,
        "variants": [
            {"color_name": "Negro", "item": "D01-N", "precio": None, "stock": 30, "activo": True},
            {"color_name": "Blanco", "item": "D01-B", "precio": None, "stock": 25, "activo": True},
            {"color_name": "Gris", "item": "D01-G", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Azul", "item": "D01-A", "precio": None, "stock": 15, "activo": True},
        ],
    },
    {
        "id": 202,
        "cat": 0,
        "nombre": f"{DEMO_PREFIX} Camisa Casual Manga Larga",
        "precio": 349.00,
        "descripcion": "Camisa de algodón con botones, estilo casual elegante.",
        "peso": 0.30, "medidas": "S-XXL", "capacidad": None, "disponible": True,
        "picsum_seed": 1002,
        "variants": [
            {"color_name": "Blanco", "item": "D02-B", "precio": None, "stock": 18, "activo": True},
            {"color_name": "Azul", "item": "D02-A", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Gris", "item": "D02-G", "precio": None, "stock": 12, "activo": True},
        ],
    },
    {
        "id": 203,
        "cat": 0,
        "nombre": f"{DEMO_PREFIX} Chaqueta Ligera Impermeable",
        "precio": 599.00,
        "descripcion": "Chaqueta cortavientos con capucha, repelente al agua. Plegable.",
        "peso": 0.45, "medidas": "S-XL", "capacidad": None, "disponible": True,
        "picsum_seed": 1003,
        "variants": [
            {"color_name": "Negro", "item": "D03-N", "precio": None, "stock": 10, "activo": True},
            {"color_name": "Azul", "item": "D03-A", "precio": None, "stock": 8, "activo": True},
            {"color_name": "Rojo", "item": "D03-R", "precio": None, "stock": 5, "activo": True},
        ],
    },
    {
        "id": 204,
        "cat": 0,
        "nombre": f"{DEMO_PREFIX} Pantalón Cargo Algodón",
        "precio": 449.00,
        "descripcion": "Pantalón tipo cargo con múltiples bolsillos, algodón resistente.",
        "peso": 0.55, "medidas": "28-38", "capacidad": None, "disponible": True,
        "picsum_seed": 1004,
        "variants": [
            {"color_name": "Beige", "item": "D04-BE", "precio": None, "stock": 12, "activo": True},
            {"color_name": "Negro", "item": "D04-N", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Verde", "item": "D04-V", "precio": None, "stock": 8, "activo": True},
        ],
    },
    {
        "id": 205,
        "cat": 0,
        "nombre": f"{DEMO_PREFIX} Gorra Clásica Bordada",
        "precio": 149.00,
        "descripcion": "Gorra de 6 paneles con bordado frontal y ajuste trasero.",
        "peso": 0.10, "medidas": "Única ajustable", "capacidad": None, "disponible": True,
        "picsum_seed": 1005,
        "variants": [
            {"color_name": "Negro", "item": "D05-N", "precio": None, "stock": 35, "activo": True},
            {"color_name": "Azul", "item": "D05-A", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Rojo", "item": "D05-R", "precio": None, "stock": 15, "activo": True},
        ],
    },
    # ---- Accesorios (cat 1) ----
    {
        "id": 206,
        "cat": 1,
        "nombre": f"{DEMO_PREFIX} Reloj Minimalista",
        "precio": 899.00,
        "descripcion": "Reloj analógico con correa de cuero y esfera limpia.",
        "peso": 0.08, "medidas": "Correa 20mm, caja 40mm", "capacidad": None, "disponible": True,
        "picsum_seed": 1006,
        "variants": [
            {"color_name": "Negro", "item": "D06-N", "precio": None, "stock": 10, "activo": True},
            {"color_name": "Marrón", "item": "D06-M", "precio": None, "stock": 8, "activo": True},
        ],
    },
    {
        "id": 207,
        "cat": 1,
        "nombre": f"{DEMO_PREFIX} Mochila Urbana 20L",
        "precio": 499.00,
        "descripcion": "Mochila con compartimento acolchado para laptop hasta 15.6\".",
        "peso": 0.70, "medidas": "42x30x15 cm", "capacidad": "20L", "disponible": True,
        "picsum_seed": 1007,
        "variants": [
            {"color_name": "Negro", "item": "D07-N", "precio": None, "stock": 22, "activo": True},
            {"color_name": "Gris", "item": "D07-G", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Azul", "item": "D07-A", "precio": None, "stock": 10, "activo": True},
        ],
    },
    {
        "id": 208,
        "cat": 1,
        "nombre": f"{DEMO_PREFIX} Gafas de Sol Polarizadas",
        "precio": 329.00,
        "descripcion": "Gafas con protección UV400 y lentes polarizados.",
        "peso": 0.04, "medidas": "Puente 18mm, lente 52mm", "capacidad": None, "disponible": True,
        "picsum_seed": 1008,
        "variants": [
            {"color_name": "Negro", "item": "D08-N", "precio": None, "stock": 28, "activo": True},
            {"color_name": "Marrón", "item": "D08-M", "precio": None, "stock": 15, "activo": True},
        ],
    },
    {
        "id": 209,
        "cat": 1,
        "nombre": f"{DEMO_PREFIX} Billetera Cuero Genuino",
        "precio": 279.00,
        "descripcion": "Billetera bifold de cuero genuino con múltiples compartimentos.",
        "peso": 0.08, "medidas": "11x9x1.5 cm", "capacidad": None, "disponible": True,
        "picsum_seed": 1009,
        "variants": [
            {"color_name": "Marrón", "item": "D09-M", "precio": None, "stock": 18, "activo": True},
            {"color_name": "Negro", "item": "D09-N", "precio": None, "stock": 25, "activo": True},
        ],
    },
    # ---- Hogar (cat 2) ----
    {
        "id": 210,
        "cat": 2,
        "nombre": f"{DEMO_PREFIX} Taza Cerámica 350ml",
        "precio": 99.00,
        "descripcion": "Taza de cerámica esmaltada apta para microondas y lavavajillas.",
        "peso": 0.35, "medidas": "10x8x9 cm", "capacidad": "350ml", "disponible": True,
        "picsum_seed": 1010,
        "variants": [
            {"color_name": "Blanco", "item": "D10-B", "precio": None, "stock": 30, "activo": True},
            {"color_name": "Negro", "item": "D10-N", "precio": None, "stock": 25, "activo": True},
            {"color_name": "Rojo", "item": "D10-R", "precio": None, "stock": 15, "activo": True},
        ],
    },
    {
        "id": 211,
        "cat": 2,
        "nombre": f"{DEMO_PREFIX} Vela Aromática de Soja",
        "precio": 189.00,
        "descripcion": "Vela de cera de soja con esencia natural. 40 horas de duración.",
        "peso": 0.40, "medidas": "8x8x10 cm", "capacidad": "200g", "disponible": True,
        "picsum_seed": 1011,
        "variants": [
            {"color_name": "Blanco", "item": "D11-B", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Beige", "item": "D11-BE", "precio": None, "stock": 15, "activo": True},
        ],
    },
    {
        "id": 212,
        "cat": 2,
        "nombre": f"{DEMO_PREFIX} Juego de Posavasos 6pz",
        "precio": 129.00,
        "descripcion": "Set de 6 posavasos de cerámica absorbente con base de corcho.",
        "peso": 0.50, "medidas": "10x10 cm c/u", "capacidad": None, "disponible": True,
        "picsum_seed": 1012,
        "variants": [
            {"color_name": "Gris", "item": "D12-G", "precio": None, "stock": 12, "activo": True},
            {"color_name": "Marrón", "item": "D12-M", "precio": None, "stock": 8, "activo": True},
        ],
    },
    # ---- Oficina (cat 3) ----
    {
        "id": 213,
        "cat": 3,
        "nombre": f"{DEMO_PREFIX} Cuaderno A5 Punteado",
        "precio": 139.00,
        "descripcion": "Cuaderno A5 de tapa dura con hojas punteadas de 100g/m².",
        "peso": 0.30, "medidas": "21x14.8x1.5 cm", "capacidad": "160 páginas", "disponible": True,
        "picsum_seed": 1013,
        "variants": [
            {"color_name": "Negro", "item": "D13-N", "precio": None, "stock": 20, "activo": True},
            {"color_name": "Azul", "item": "D13-A", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Verde", "item": "D13-V", "precio": None, "stock": 12, "activo": True},
        ],
    },
    {
        "id": 214,
        "cat": 3,
        "nombre": f"{DEMO_PREFIX} Bolígrafo Rodillo Premium",
        "precio": 79.00,
        "descripcion": "Bolígrafo con punta de rodillo de 0.7mm, tinta de gel negra.",
        "peso": 0.02, "medidas": "14x1 cm", "capacidad": None, "disponible": True,
        "picsum_seed": 1014,
        "variants": [
            {"color_name": "Negro", "item": "D14-N", "precio": None, "stock": 50, "activo": True},
            {"color_name": "Azul", "item": "D14-A", "precio": None, "stock": 40, "activo": True},
            {"color_name": "Rojo", "item": "D14-R", "precio": None, "stock": 30, "activo": True},
        ],
    },
    {
        "id": 215,
        "cat": 3,
        "nombre": f"{DEMO_PREFIX} Organizador Escritorio Bambú",
        "precio": 249.00,
        "descripcion": "Organizador de bambú natural con compartimentos para bolígrafos y accesorios.",
        "peso": 0.60, "medidas": "20x12x12 cm", "capacidad": None, "disponible": True,
        "picsum_seed": 1015,
        "variants": [
            {"color_name": "Marrón", "item": "D15-M", "precio": None, "stock": 10, "activo": True},
            {"color_name": "Beige", "item": "D15-BE", "precio": None, "stock": 8, "activo": True},
        ],
    },
    # ---- Tecnología (cat 4) ----
    {
        "id": 216,
        "cat": 4,
        "nombre": f"{DEMO_PREFIX} Funda Silicona iPhone",
        "precio": 199.00,
        "descripcion": "Funda de silicona líquida con interior de microfibra. Antihuellas.",
        "peso": 0.03, "medidas": "Varía por modelo", "capacidad": None, "disponible": True,
        "picsum_seed": 1016,
        "variants": [
            {"color_name": "Negro", "item": "D16-N", "precio": None, "stock": 40, "activo": True},
            {"color_name": "Azul", "item": "D16-A", "precio": None, "stock": 30, "activo": True},
            {"color_name": "Rojo", "item": "D16-R", "precio": None, "stock": 20, "activo": True},
        ],
    },
    {
        "id": 217,
        "cat": 4,
        "nombre": f"{DEMO_PREFIX} Power Bank 10000mAh",
        "precio": 349.00,
        "descripcion": "Batería portátil con USB-C y carga rápida 18W. LED indicador.",
        "peso": 0.22, "medidas": "10x6.5x1.5 cm", "capacidad": "10000mAh", "disponible": True,
        "picsum_seed": 1017,
        "variants": [
            {"color_name": "Negro", "item": "D17-N", "precio": None, "stock": 25, "activo": True},
            {"color_name": "Blanco", "item": "D17-B", "precio": None, "stock": 20, "activo": True},
        ],
    },
    {
        "id": 218,
        "cat": 4,
        "nombre": f"{DEMO_PREFIX} Audífonos Bluetooth",
        "precio": 499.00,
        "descripcion": "Audífonos in-ear inalámbricos con cancelación de ruido y estuche de carga.",
        "peso": 0.05, "medidas": "Estuche 6x4.5x2.5 cm", "capacidad": None, "disponible": True,
        "picsum_seed": 1018,
        "variants": [
            {"color_name": "Negro", "item": "D18-N", "precio": None, "stock": 15, "activo": True},
            {"color_name": "Blanco", "item": "D18-B", "precio": None, "stock": 18, "activo": True},
        ],
    },
    {
        "id": 219,
        "cat": 4,
        "nombre": f"{DEMO_PREFIX} Cable USB-C Trenzado 2m",
        "precio": 129.00,
        "descripcion": "Cable USB-C a USB-C trenzado de nylon, carga rápida 60W y transferencia de datos.",
        "peso": 0.08, "medidas": "200 cm", "capacidad": None, "disponible": True,
        "picsum_seed": 1019,
        "variants": [
            {"color_name": "Negro", "item": "D19-N", "precio": None, "stock": 60, "activo": True},
            {"color_name": "Gris", "item": "D19-G", "precio": None, "stock": 40, "activo": True},
        ],
    },
    {
        "id": 220,
        "cat": 4,
        "nombre": f"{DEMO_PREFIX} Soporte Ajustable Celular",
        "precio": 179.00,
        "descripcion": "Soporte de aluminio ajustable para celular y tablet. Base antideslizante.",
        "peso": 0.35, "medidas": "12x8x15 cm (plegado)", "capacidad": None, "disponible": True,
        "picsum_seed": 1020,
        "variants": [
            {"color_name": "Negro", "item": "D20-N", "precio": None, "stock": 22, "activo": True},
            {"color_name": "Gris", "item": "D20-G", "precio": None, "stock": 18, "activo": True},
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Seed staging database with 8 test scenarios (issue #11). "
        "Idempotent — records tagged with [SEED] or [DEMO] prefix."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute what would be created without saving anything.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all [SEED]- and [DEMO]-prefixed records before seeding.",
        )
        parser.add_argument(
            "--real-data",
            action="store_true",
            help="Seed real demo products instead of test scenarios.",
        )
        parser.add_argument(
            "--generate-images",
            action="store_true",
            help="Generate product images for seeded products.",
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Seed 20 generic demo products with picsum.photos images for UI testing.",
        )
    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------
    def _get_product_color(self, product_name: str, scenario_id: int = None):
        """Get a color for a product based on its name or scenario ID."""
        # Check product name keywords
        for keyword, color in PRODUCT_COLORS.items():
            if keyword in product_name:
                return color
        # Check scenario colors
        if scenario_id and scenario_id in SEED_COLORS:
            return SEED_COLORS[scenario_id]
        # Default color
        return (100, 100, 100)

    def _generate_product_image(self, product_name: str, scenario_id: int = None) -> str:
        """
        Generate a product image and return the path.
        Returns None if generation fails.
        """
        try:
            # Create image
            base_color = self._get_product_color(product_name, scenario_id)
            img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), base_color)
            draw = ImageDraw.Draw(img)

            # Add gradient overlay
            for i in range(IMAGE_HEIGHT):
                alpha = int(255 * (1 - i / IMAGE_HEIGHT) * 0.3)
                overlay = Image.new('RGBA', (IMAGE_WIDTH, 1), (255, 255, 255, alpha))
                img.paste(Image.blend(
                    Image.new('RGBA', (IMAGE_WIDTH, 1), (*base_color, 255)),
                    overlay, 0.5
                ), (0, i))

            # Add text
            draw = ImageDraw.Draw(img)
            
            # Add product name
            text = product_name[:20] if len(product_name) > 20 else product_name
            
            # Try to use a font, fallback to default
            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except:
                font_large = ImageFont.load_default()
                font_small = font_large

            # Draw product name
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (IMAGE_WIDTH - text_width) / 2
            y = (IMAGE_HEIGHT - text_height) / 2 - 20
            
            # Shadow
            draw.text((x+2, y+2), text, font=font_large, fill=(0, 0, 0, 128))
            # Main text
            draw.text((x, y), text, font=font_large, fill=(255, 255, 255))

            # Add "Bukis" label
            label_text = "Bukis Store"
            bbox = draw.textbbox((0, 0), label_text, font=font_small)
            label_width = bbox[2] - bbox[0]
            draw.text(
                ((IMAGE_WIDTH - label_width) / 2, y + 60),
                label_text,
                font=font_small,
                fill=(255, 255, 255, 180)
            )

            # Save to media directory
            media_root = settings.MEDIA_ROOT
            image_dir = os.path.join(media_root, 'img', 'products')
            os.makedirs(image_dir, exist_ok=True)

            # Generate filename
            safe_name = product_name.replace('[SEED]', '').strip().replace(' ', '_').replace('-', '_')[:30]
            filename = f"seed_{safe_name}_{scenario_id or 'real'}.jpg"
            filepath = os.path.join(image_dir, filename)

            # Save image
            img.save(filepath, 'JPEG', quality=IMAGE_QUALITY)

            # Return relative path
            return f"img/products/{filename}"

        except Exception as e:
            self.stdout.write(f"  ⚠️  Image generation failed for {product_name}: {e}")
            return None

    def _generate_images_for_products(self, products):
        """Generate images for all seed products."""
        self.stdout.write("\n🎨 Generating product images...")
        
        for product in products:
            try:
                # Check if image exists and is not a placeholder
                if product.imagen:
                    imagen_path = str(product.imagen)
                    if 'seed' not in imagen_path and 'placeholder' not in imagen_path:
                        # Skip if already has a real image
                        continue
            except:
                # If file doesn't exist, continue to generate
                pass

            image_path = self._generate_product_image(
                product.nombre,
                getattr(product, 'id', None)
            )
            
            if image_path:
                product.imagen = image_path
                product.save(update_fields=['imagen'])
                self.stdout.write(f"  ✅ Image generated: {product.nombre}")
            else:
                self.stdout.write(f"  ⚠️  Using placeholder for: {product.nombre}")

    # ------------------------------------------------------------------
    # Demo: download image from picsum.photos
    # ------------------------------------------------------------------
    def _download_demo_image(self, product_name: str, seed: int) -> str | None:
        """
        Download a product image from picsum.photos and save it to the
        Django ImageField path. Returns the relative path, or None on failure.
        """
        url = f"https://picsum.photos/seed/{seed}/400/400"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DjangoSeed/1.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                image_data = response.read()

            media_root = settings.MEDIA_ROOT
            image_dir = os.path.join(media_root, "img", "products")
            os.makedirs(image_dir, exist_ok=True)

            # Sanitize product name for filename
            safe_name = product_name.replace("[DEMO]", "").strip().replace(" ", "_")[:40]
            filename = f"demo_{safe_name}_{seed}.jpg"
            filepath = os.path.join(image_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_data)

            return f"img/products/{filename}"

        except Exception as e:
            self.stdout.write(f"  ⚠️  Image download failed for {product_name}: {e}")
            return None

    # ------------------------------------------------------------------
    # Demo: bootstrap dependencies (categories + colors)
    # ------------------------------------------------------------------
    def _bootstrap_demo_dependencies(self, dry_run):
        """Ensure demo categories and colors exist. Return (cats, color_map)."""
        if dry_run:
            return [None] * len(DEMO_CATEGORIES), {name: None for name in DEMO_COLOR_NAMES}

        cats = []
        for cat_name in DEMO_CATEGORIES:
            c, created = CategoriasModel.objects.get_or_create(nombre=cat_name)
            if created:
                self.stdout.write(f"  Categoría demo creada: {c.nombre}")
            cats.append(c)

        color_map: dict[str, ColorModel] = {}
        for name in DEMO_COLOR_NAMES:
            hex_value = DEMO_COLOR_HEX[name]
            # Try to find by hex first (since hex is UNIQUE)
            try:
                c = ColorModel.objects.get(hex=hex_value)
            except ColorModel.DoesNotExist:
                # Create with standard name (not [DEMO] prefixed — these are reusable)
                c, created = ColorModel.objects.get_or_create(
                    nombre=name,
                    defaults={"hex": hex_value},
                )
                if created:
                    self.stdout.write(f"  Color demo creado: {c}")
            else:
                self.stdout.write(f"  Color reutilizado: {c}")
            color_map[name] = c

        return cats, color_map

    # ------------------------------------------------------------------
    # Demo: seed a single demo product
    # ------------------------------------------------------------------
    def _seed_demo_product(
        self,
        scenario: dict,
        categories: list,
        color_map: dict[str, ColorModel],
        dry_run: bool,
    ) -> tuple[ProductosModel | None, list[ProductoVariantesModel], bool]:
        """
        Create (or retrieve) one demo product with its variants and image.

        Returns (product, variants, created).
        """
        nombre = scenario["nombre"]
        desc = scenario["descripcion"]
        cat_idx = scenario.get("cat", 0)
        seed = scenario.get("picsum_seed", 0)

        if dry_run:
            return None, [], True

        # Download image first (so we can use it as the default imagen)
        imagen_path = None
        if not dry_run and seed:
            imagen_path = self._download_demo_image(nombre, seed)

        product, created = ProductosModel.objects.get_or_create(
            nombre=nombre,
            defaults={
                "imagen": imagen_path or PLACEHOLDER_IMAGE,
                "descripcion": desc,
                "precio": scenario["precio"],
                "peso": scenario.get("peso", 1.00),
                "medidas": scenario.get("medidas", "N/A"),
                "capacidad": scenario.get("capacidad", None),
                "disponible": scenario["disponible"],
            },
        )

        # Assign category
        if created and categories and cat_idx < len(categories) and categories[cat_idx]:
            product.categorias.add(categories[cat_idx])

        variants: list[ProductoVariantesModel] = []
        for vdef in scenario.get("variants", []):
            color = color_map[vdef["color_name"]]
            variant, v_created = ProductoVariantesModel.objects.get_or_create(
                producto=product,
                color=color,
                defaults={
                    "item": vdef["item"],
                    "precio": vdef["precio"],
                    "stock": vdef["stock"],
                    "activo": vdef.get("activo", True),
                },
            )
            if not v_created:
                needs_update = False
                if variant.item != vdef["item"]:
                    variant.item = vdef["item"]
                    needs_update = True
                if variant.precio != vdef["precio"]:
                    variant.precio = vdef["precio"]
                    needs_update = True
                if variant.stock != vdef["stock"]:
                    variant.stock = vdef["stock"]
                    needs_update = True
                if variant.activo != vdef.get("activo", True):
                    variant.activo = vdef.get("activo", True)
                    needs_update = True
                if needs_update:
                    variant.save(update_fields=["item", "precio", "stock", "activo"])
            variants.append(variant)

        return product, variants, created

    # ------------------------------------------------------------------
    # Bootstrap: shared dependencies (category + colors)
    # ------------------------------------------------------------------
    def _bootstrap_dependencies(self, dry_run):
        """Ensure shared seed category and colors exist. Return (cat, color_map)."""
        if dry_run:
            return None, {name: None for name in COLOR_NAMES}

        cat, _ = CategoriasModel.objects.get_or_create(nombre=CATEGORY_NAME)
        self.stdout.write(f"  Categoría: {cat.nombre}")

        color_map: dict[str, ColorModel] = {}
        for name in COLOR_NAMES:
            hex_value = COLOR_HEX_MAP[name]
            # Try to find by hex first (since hex is UNIQUE)
            try:
                c = ColorModel.objects.get(hex=hex_value)
            except ColorModel.DoesNotExist:
                # If not found by hex, create with our seed name
                c, created = ColorModel.objects.get_or_create(
                    nombre=f"{SEED_PREFIX} {name}",
                    defaults={"hex": hex_value},
                )
                if created:
                    self.stdout.write(f"  Color creado: {c}")
            else:
                self.stdout.write(f"  Color reutilizado (hex existente): {c}")
            color_map[name] = c
        return cat, color_map

    # ------------------------------------------------------------------
    # Seed a single product + its variants
    # ------------------------------------------------------------------
    def _seed_product(
        self,
        scenario: dict,
        category,
        color_map: dict[str, ColorModel],
        dry_run: bool,
    ) -> tuple[ProductosModel | None, list[ProductoVariantesModel], bool]:
        """
        Create (or retrieve) one seed product and its variants.

        Returns (product, variants, created).
        """
        nombre = scenario["nombre"]
        desc = scenario.get("descripcion", f"Seed scenario {scenario.get('id', 'N/A')}: {scenario.get('name', nombre)}")

        if dry_run:
            return None, [], True

        product, created = ProductosModel.objects.get_or_create(
            nombre=nombre,
            defaults={
                "imagen": scenario.get("imagen", PLACEHOLDER_IMAGE),
                "descripcion": desc,
                "precio": scenario["precio"],
                "peso": scenario.get("peso", 1.00),
                "medidas": scenario.get("medidas", "10x10x10 cm (seed)"),
                "capacidad": scenario.get("capacidad", None),
                "disponible": scenario["disponible"],
            },
        )

        if created and category:
            product.categorias.add(category)

        variants: list[ProductoVariantesModel] = []
        for vdef in scenario.get("variants", []):
            color = color_map[vdef["color_name"]]
            variant, v_created = ProductoVariantesModel.objects.get_or_create(
                producto=product,
                color=color,
                defaults={
                    "item": vdef["item"],
                    "precio": vdef["precio"],
                    "stock": vdef["stock"],
                    "activo": vdef.get("activo", True),
                },
            )
            # If the variant already existed, ensure its fields are still correct
            # (update in case a prior partial run left inconsistent data)
            if not v_created:
                needs_update = False
                if variant.item != vdef["item"]:
                    variant.item = vdef["item"]
                    needs_update = True
                if variant.precio != vdef["precio"]:
                    variant.precio = vdef["precio"]
                    needs_update = True
                if variant.stock != vdef["stock"]:
                    variant.stock = vdef["stock"]
                    needs_update = True
                if variant.activo != vdef.get("activo", True):
                    variant.activo = vdef.get("activo", True)
                    needs_update = True
                if needs_update:
                    variant.save(update_fields=["item", "precio", "stock", "activo"])
            variants.append(variant)

        return product, variants, created

    # ------------------------------------------------------------------
    # Clear: remove all [SEED] and [DEMO] tagged records
    # ------------------------------------------------------------------
    def _clear_all_seed_data(self):
        """Delete all products, variants, colors, and categories tagged with [SEED] or [DEMO]."""

        # 1. Products (cascades to variants via FK on_delete=CASCADE)
        # Match both [SEED] and [DEMO] prefixes
        products = ProductosModel.objects.filter(
            Q(nombre__startswith=SEED_PREFIX) | Q(nombre__startswith=DEMO_PREFIX)
        )
        count_p = products.count()
        products.delete()
        self.stdout.write(f"  Deleted {count_p} seed/demo products (variants cascade-deleted).")

        # 2. Seed colors — only delete if no remaining variants reference them
        # (protected because demo products may have reused the same colors)
        try:
            seed_colors = ColorModel.objects.filter(nombre__startswith=f"{SEED_PREFIX} ")
            count_c = seed_colors.count()
            if count_c:
                seed_colors.delete()
                self.stdout.write(f"  Deleted {count_c} seed colors.")
        except Exception:
            self.stdout.write(f"  ⚠️  Could not delete seed colors (still referenced). Skipping.")

        # 3. Seed category
        cat = CategoriasModel.objects.filter(nombre=CATEGORY_NAME).first()
        if cat:
            cat.delete()
            self.stdout.write(f"  Deleted seed category: {CATEGORY_NAME}")

        # 4. Demo categories
        demo_cats = CategoriasModel.objects.filter(nombre__startswith=f"{DEMO_PREFIX} ")
        count_dc = demo_cats.count()
        demo_cats.delete()
        if count_dc:
            self.stdout.write(f"  Deleted {count_dc} demo categories.")

    def _clear_seed_data(self):
        """Backward-compatible wrapper. Calls _clear_all_seed_data()."""
        self._clear_all_seed_data()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        clear = options["clear"]
        real_data = options["real_data"]
        demo = options.get("demo", False)

        self.stdout.write(self.style.MIGRATE_HEADING("=== Staging Seed Command ==="))

        if demo:
            self.stdout.write(self.style.WARNING("Mode: DEMO (20 generic products with picsum images)\n"))
        elif real_data:
            self.stdout.write(self.style.WARNING("Mode: REAL DATA (demo products)\n"))
        else:
            self.stdout.write(self.style.WARNING("Mode: TEST SCENARIOS (issue #11)\n"))

        # --clear
        if clear:
            if dry_run:
                existing = ProductosModel.objects.filter(
                    Q(nombre__startswith=SEED_PREFIX) | Q(nombre__startswith=DEMO_PREFIX)
                ).count()
                self.stdout.write(
                    f"\n🧹 [DRY RUN] Would delete {existing} seed/demo products "
                    f"and their dependencies.\n"
                )
            else:
                self.stdout.write("\n🧹 Clearing existing seed/demo data...")
                self._clear_all_seed_data()
                self.stdout.write(self.style.SUCCESS("Clear complete.\n"))

        # Check for pre-existing records (idempotency guard)
        if not dry_run:
            if demo:
                existing_count = ProductosModel.objects.filter(
                    nombre__startswith=DEMO_PREFIX
                ).count()
                if existing_count > 0 and not clear:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Demo records already exist ({existing_count} products). "
                            "Use --clear to remove them first. Skipping."
                        )
                    )
                    return
            elif not real_data:
                existing_count = ProductosModel.objects.filter(
                    nombre__startswith=SEED_PREFIX
                ).count()
                if existing_count > 0 and not clear:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Seed records already exist ({existing_count} products). "
                            "Use --clear to remove them first. Skipping."
                        )
                    )
                    return

        # Select data source and bootstrap
        if demo:
            products_to_seed = DEMO_PRODUCTS
            mode_label = "DEMO"

            self.stdout.write("\n📦 Bootstrapping demo dependencies...")
            cats, color_map = self._bootstrap_demo_dependencies(dry_run)
            self.stdout.write(f"  Categories: {len(cats)}")
            self.stdout.write(f"  Colors: {len(color_map)}\n")

            self.stdout.write(f"\n🌱 Seeding {len(products_to_seed)} {mode_label} products...\n")

            summary_rows: list[dict] = []

            for scenario in products_to_seed:
                product, variants, created = self._seed_demo_product(
                    scenario, cats, color_map, dry_run
                )

                n_variants = len(variants)
                active_variants = (
                    sum(1 for v in variants if v.activo) if not dry_run else 0
                )
                status = "would create" if dry_run else ("CREATED" if created else "already exists")

                summary_rows.append({
                    "id": scenario["id"],
                    "name": scenario["nombre"],
                    "product": scenario["nombre"],
                    "variants": n_variants,
                    "active": active_variants if not dry_run else "-",
                    "status": status,
                })

                if dry_run:
                    self.stdout.write(
                        f"  [{status}] {scenario['nombre']} "
                        f"({n_variants} variant(s))"
                    )
                else:
                    self.stdout.write(
                        f"  [{status}] {scenario['nombre']:<42} "
                        f"| variants={n_variants} | active={active_variants}"
                    )

        else:
            products_to_seed = REAL_PRODUCTS if real_data else SCENARIOS
            mode_label = "REAL" if real_data else "TEST"

            # Bootstrap shared resources
            self.stdout.write("\n📦 Bootstrapping shared dependencies...")
            cat, color_map = self._bootstrap_dependencies(dry_run)

            # Seed each product
            self.stdout.write(f"\n🌱 Seeding {len(products_to_seed)} {mode_label} products...\n")

            summary_rows: list[dict] = []

            for scenario in products_to_seed:
                product, variants, created = self._seed_product(
                    scenario, cat, color_map, dry_run
                )

                n_variants = len(variants)
                active_variants = (
                    sum(1 for v in variants if v.activo) if not dry_run else 0
                )
                status = "would create" if dry_run else ("CREATED" if created else "already exists")

                summary_rows.append({
                    "id": scenario.get("id", "-"),
                    "name": scenario.get("name", scenario["nombre"]),
                    "product": scenario["nombre"],
                    "variants": n_variants,
                    "active": active_variants if not dry_run else "-",
                    "status": status,
                })

                if dry_run:
                    self.stdout.write(
                        f"  [{status}] {scenario['nombre']} "
                        f"({n_variants} variant(s))"
                    )
                else:
                    label = scenario.get("name", scenario["nombre"])
                    self.stdout.write(
                        f"  [{status}] {label:<40} "
                        f"| variants={n_variants} | active={active_variants}"
                    )

        # Summary table
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.MIGRATE_HEADING("SEED SUMMARY"))
        self.stdout.write("=" * 70)

        total_products = 0
        total_variants = 0
        for row in summary_rows:
            total_products += 1
            total_variants += row["variants"]
            name = row["name"]
            self.stdout.write(
                f"  {row['id']:<4} {name[:42]:<42} "
                f"variants={row['variants']:<3} [{row['status']}]"
            )

        self.stdout.write("-" * 70)
        suffix = " (DRY RUN — nothing saved)" if dry_run else ""
        self.stdout.write(
            f"  Total: {total_products} products, {total_variants} variants{suffix}"
        )
        self.stdout.write("=" * 70)

        # Generate images if requested (not for demo — demo already downloads images)
        if not dry_run and not demo and options.get("generate_images"):
            self.stdout.write("\n")
            seeded_products = ProductosModel.objects.filter(
                nombre__startswith=SEED_PREFIX if not real_data else ""
            ).filter(nombre__in=[s["nombre"] for s in products_to_seed])
            self._generate_images_for_products(seeded_products)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("\nDry run complete. Run without --dry-run to persist.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Seed complete. {total_products} products, "
                    f"{total_variants} variants seeded."
                )
            )
