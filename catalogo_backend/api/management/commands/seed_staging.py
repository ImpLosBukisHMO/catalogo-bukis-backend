"""
Management command: seed_staging

Seeds the staging database with 8 test scenarios from issue #11.
Each scenario corresponds to a specific product-variant combination
that must be validated by the frontend.

Idempotent — running twice does not duplicate records.
All seed records use a [SEED] prefix in their names for easy identification.

Usage:
    python manage.py seed_staging
    python manage.py seed_staging --dry-run
    python manage.py seed_staging --clear
"""

from django.core.management.base import BaseCommand

from api.models import (
    CategoriasModel,
    ColorModel,
    ProductosModel,
    ProductoVariantesModel,
)

# ----------------------------------------------------------------
# Placeholder image path — required by model but no real file is
# needed for data-validation seed records.
# ----------------------------------------------------------------
PLACEHOLDER_IMAGE = "seed/placeholder.jpg"

# ----------------------------------------------------------------
# Shared seed helpers
# ----------------------------------------------------------------
SEED_PREFIX = "[SEED]"
CATEGORY_NAME = f"{SEED_PREFIX} Staging"
COLOR_NAMES = ["Rojo", "Azul", "Verde", "Negro", "Blanco"]
COLOR_HEX_MAP = {
    "Rojo": "#FF0000",
    "Azul": "#0000FF",
    "Verde": "#00FF00",
    "Negro": "#000000",
    "Blanco": "#FFFFFF",
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
        desc = f"Seed scenario {scenario['id']}: {scenario['name']}"

        if dry_run:
            return None, [], True

        product, created = ProductosModel.objects.get_or_create(
            nombre=nombre,
            defaults={
                "imagen": PLACEHOLDER_IMAGE,
                "descripcion": desc,
                "precio": scenario["precio"],
                "peso": 1.00,
                "medidas": "10x10x10 cm (seed)",
                "capacidad": None,
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

        self.stdout.write(self.style.MIGRATE_HEADING("=== Staging Seed Command ==="))

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
        if not dry_run:
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

        # Bootstrap shared resources
        self.stdout.write("\n📦 Bootstrapping shared dependencies...")
        cat, color_map = self._bootstrap_dependencies(dry_run)

        # Seed each scenario
        self.stdout.write(f"\n🌱 Seeding {len(SCENARIOS)} scenario products...\n")

        summary_rows: list[dict] = []

        for scenario in SCENARIOS:
            product, variants, created = self._seed_product(
                scenario, cat, color_map, dry_run
            )

            n_variants = len(variants)
            active_variants = (
                sum(1 for v in variants if v.activo) if not dry_run else 0
            )
            status = "would create" if dry_run else ("CREATED" if created else "already exists")

            summary_rows.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "product": scenario["nombre"],
                "variants": n_variants,
                "active": active_variants if not dry_run else "-",
                "status": status,
            })

            if dry_run:
                self.stdout.write(
                    f"  [{status}] S{scenario['id']}: {scenario['nombre']} "
                    f"({n_variants} variant(s))"
                )
            else:
                self.stdout.write(
                    f"  [{status}] S{scenario['id']:>2} | {scenario['name']:<40} "
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
                f"  S{row['id']:<3} {row['name']:<42} "
                f"variants={row['variants']:<3} [{row['status']}]"
            )

        self.stdout.write("-" * 70)
        mode_label = " (DRY RUN — nothing saved)" if dry_run else ""
        self.stdout.write(
            f"  Total: {total_products} products, {total_variants} variants{mode_label}"
        )
        self.stdout.write("=" * 70)

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
