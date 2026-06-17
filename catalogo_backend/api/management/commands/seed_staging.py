"""
Management command: seed_staging

Seeds the staging database with 8 test scenarios from issue #11
or real demo products with generated images.

Idempotent — running twice does not duplicate records.
All seed records use a [SEED] prefix in their names for easy identification.

Usage:
    python manage.py seed_staging
    python manage.py seed_staging --dry-run
    python manage.py seed_staging --clear
    python manage.py seed_staging --real-data
    python manage.py seed_staging --real-data --generate-images
"""

import os
from io import BytesIO

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
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


class Command(BaseCommand):
    help = (
        "Seed staging database with 8 test scenarios (issue #11). "
        "Idempotent — records tagged with [SEED] prefix."
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
            help="Remove all [SEED]-prefixed records before seeding.",
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
    # Clear: remove all [SEED]-prefixed records
    # ------------------------------------------------------------------
    def _clear_seed_data(self):
        """Delete all products, variants, colors, and category tagged with [SEED]."""

        # 1. Products (cascades to variants via FK on_delete=CASCADE)
        products = ProductosModel.objects.filter(nombre__startswith=SEED_PREFIX)
        count_p = products.count()
        products.delete()
        self.stdout.write(f"  Deleted {count_p} seed products (variants cascade-deleted).")

        # 2. Seed colors (safe now — no variants reference them)
        colors = ColorModel.objects.filter(nombre__startswith=f"{SEED_PREFIX} ")
        count_c = colors.count()
        colors.delete()
        self.stdout.write(f"  Deleted {count_c} seed colors.")

        # 3. Seed category
        cat = CategoriasModel.objects.filter(nombre=CATEGORY_NAME).first()
        if cat:
            cat.delete()
            self.stdout.write(f"  Deleted seed category: {CATEGORY_NAME}")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        clear = options["clear"]
        real_data = options["real_data"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Staging Seed Command ==="))

        if real_data:
            self.stdout.write(self.style.WARNING("Mode: REAL DATA (demo products)\n"))
        else:
            self.stdout.write(self.style.WARNING("Mode: TEST SCENARIOS (issue #11)\n"))

        # --clear
        if clear:
            if dry_run:
                existing = ProductosModel.objects.filter(nombre__startswith=SEED_PREFIX).count()
                self.stdout.write(
                    f"\n🧹 [DRY RUN] Would delete {existing} seed products "
                    f"and their dependencies.\n"
                )
            else:
                self.stdout.write("\n🧹 Clearing existing seed data...")
                self._clear_seed_data()
                self.stdout.write(self.style.SUCCESS("Clear complete.\n"))

        # Check for pre-existing seed records (idempotency guard)
        if not dry_run and not real_data:
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

        # Select data source
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
            self.stdout.write(
                f"  {row['id']:<4} {row['name']:<42} "
                f"variants={row['variants']:<3} [{row['status']}]"
            )

        self.stdout.write("-" * 70)
        mode_label = " (DRY RUN — nothing saved)" if dry_run else ""
        self.stdout.write(
            f"  Total: {total_products} products, {total_variants} variants{mode_label}"
        )
        self.stdout.write("=" * 70)

        # Generate images if requested
        if not dry_run and options["generate_images"]:
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
