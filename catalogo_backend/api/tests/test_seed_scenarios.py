"""
Test de integración para validar los 8 escenarios de seed (issue #11).

Cada escenario verifica un caso de borde en la lógica de precios/disponibilidad:
  S1: Múltiples variantes en stock
  S2: Precio de variante distinto al producto
  S3: Precio explícito = 0.00
  S4: Todas las variantes sin stock
  S5: Producto sin variantes
  S6: Producto disponible=False (kill-switch)
  S7: Al menos una variante activo=False
  S8: Dos productos compartiendo el mismo item

Para correr solo estos tests:
    python manage.py test api.tests.test_seed_scenarios -v 2
"""

from io import StringIO
from decimal import Decimal

from django.test import TestCase
from django.core.management import call_command

from api.models import (
    ProductosModel,
    ProductoVariantesModel,
    ColorModel,
    CategoriasModel,
)


class SeedScenariosTest(TestCase):
    """
    Corre 'seed_staging' contra una DB de test vacía y verifica
    que los 8 escenarios se comporten según lo especificado.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stdout = StringIO()
        cls.stderr = StringIO()
        call_command("seed_staging", stdout=cls.stdout, stderr=cls.stderr)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_seed_product(self, name_contains: str):
        """Busca un producto cuyo nombre contenga el string dado."""
        qs = ProductosModel.objects.filter(nombre__contains=name_contains)
        self.assertEqual(
            qs.count(), 1,
            f"Se esperaba exactamente 1 producto con nombre que contenga '{name_contains}'. "
            f"Encontrados: {list(qs.values_list('nombre', flat=True))}"
        )
        return qs.first()

    def _assert_variant_count(self, producto, expected: int):
        count = producto.producto_colores.count()
        self.assertEqual(count, expected,
                         f"{producto.nombre}: esperaba {expected} variantes, hay {count}")

    def _assert_all_variants(self, producto, field: str, expected_value):
        """Chequea que TODAS las variantes de un producto tengan un campo con un valor."""
        for v in producto.producto_colores.all():
            actual = getattr(v, field)
            self.assertEqual(actual, expected_value,
                             f"{producto.nombre} – variante {v.color.nombre}: "
                             f"{field}={actual}, esperaba {expected_value}")

    def _assert_at_least_one_variant(self, producto, field: str, expected_value):
        """Chequea que AL MENOS UNA variante tenga el campo con el valor dado."""
        values = [getattr(v, field) for v in producto.producto_colores.all()]
        self.assertIn(expected_value, values,
                      f"{producto.nombre}: ninguna variante tiene {field}={expected_value}. "
                      f"Valores: {values}")

    def _assert_none_variant(self, producto, field: str, forbidden_value):
        """Chequea que NINGUNA variante tenga el campo con el valor dado."""
        for v in producto.producto_colores.all():
            actual = getattr(v, field)
            self.assertNotEqual(actual, forbidden_value,
                                f"{producto.nombre} – variante {v.color.nombre}: "
                                f"{field} no debería ser {forbidden_value}")

    def _is_variant_disponible(self, v):
        """Calcula disponibilidad lógica (mismo criterio que el serializer)."""
        return v.activo and v.stock > 0

    # ------------------------------------------------------------------
    # S1: Múltiples variantes en stock
    # ------------------------------------------------------------------
    def test_s1_multiple_variants_in_stock(self):
        """S1: Producto con 3 variantes, todas con stock > 0."""
        p = self._get_seed_product("S1")
        self.assertTrue(p.disponible)
        self._assert_variant_count(p, 3)
        # Todas deben estar disponibles (activo=True y stock>0)
        for v in p.producto_colores.all():
            self.assertTrue(self._is_variant_disponible(v),
                           f"{p.nombre}: variante {v.color.nombre} debería estar disponible")
        # Todas deben tener activo=True
        self._assert_all_variants(p, "activo", True)
        # Todas deben tener stock > 0
        for v in p.producto_colores.all():
            self.assertGreater(v.stock, 0,
                               f"{p.nombre}: variante {v.color.nombre} debería tener stock > 0")

    # ------------------------------------------------------------------
    # S2: Precio de variante distinto al producto
    # ------------------------------------------------------------------
    def test_s2_variant_price_override(self):
        """S2: Al menos una variante tiene precio explícito distinto al producto."""
        p = self._get_seed_product("S2")
        self.assertTrue(p.disponible)
        self._assert_variant_count(p, 2)
        # Hay al menos una variante con precio distinto al del producto
        producto_precio = p.precio
        variantes_distintas = [
            v for v in p.producto_colores.all()
            if v.precio is not None and v.precio != producto_precio
        ]
        self.assertGreaterEqual(len(variantes_distintas), 1,
                                f"{p.nombre}: debería haber al menos 1 variante con precio != {producto_precio}")
        # Esa variante con override debe devolver ese precio en precio_efectivo
        for v in variantes_distintas:
            self.assertEqual(v.precio_efectivo, v.precio,
                             f"{p.nombre}: variante con override debería devolver precio={v.precio}")

    # ------------------------------------------------------------------
    # S3: Precio explícito = 0.00
    # ------------------------------------------------------------------
    def test_s3_variant_price_zero_explicit(self):
        """S3: Variante con precio explícito = 0.00 (no null)."""
        p = self._get_seed_product("S3")
        self.assertTrue(p.disponible)
        self._assert_variant_count(p, 1)
        v = p.producto_colores.first()
        self.assertIsNotNone(v.precio)
        self.assertEqual(v.precio, Decimal("0.00"),
                         f"{p.nombre}: variante debería tener precio=0.00")
        self.assertEqual(v.precio_efectivo, Decimal("0.00"),
                         f"{p.nombre}: precio_efectivo debería ser 0.00")
        # Aunque precio sea 0, debe estar disponible (stock > 0)
        self.assertTrue(self._is_variant_disponible(v))
        self.assertGreater(v.stock, 0)

    # ------------------------------------------------------------------
    # S4: Todas las variantes sin stock
    # ------------------------------------------------------------------
    def test_s4_all_variants_stock_zero(self):
        """S4: Todas las variantes tienen stock=0, por lo tanto disponible=False."""
        p = self._get_seed_product("S4")
        self.assertTrue(p.disponible)  # El producto sigue disponible
        self._assert_variant_count(p, 2)
        # Todas las variantes deben tener stock=0
        self._assert_all_variants(p, "stock", 0)
        # Todas las variantes deben estar no disponibles (stock=0)
        for v in p.producto_colores.all():
            self.assertFalse(self._is_variant_disponible(v),
                            f"{p.nombre}: variante {v.color.nombre} con stock=0 debería ser no disponible")

    # ------------------------------------------------------------------
    # S5: Producto sin variantes
    # ------------------------------------------------------------------
    def test_s5_product_no_variants(self):
        """S5: Producto sin variantes."""
        p = self._get_seed_product("S5")
        self.assertTrue(p.disponible)
        self._assert_variant_count(p, 0)

    # ------------------------------------------------------------------
    # S6: Producto disponible=False
    # ------------------------------------------------------------------
    def test_s6_product_disponible_false(self):
        """S6: Producto con disponible=False no debe aparecer en listados."""
        p = self._get_seed_product("S6")
        self.assertFalse(p.disponible)
        # La variante puede tener stock, pero el producto está oculto
        self._assert_variant_count(p, 1)
        v = p.producto_colores.first()
        self.assertGreater(v.stock, 0)
        self.assertTrue(v.activo)
        # Verificar que no aparece en el queryset público
        self.assertNotIn(p, ProductosModel.objects.filter(disponible=True))

    # ------------------------------------------------------------------
    # S7: Al menos una variante activo=False
    # ------------------------------------------------------------------
    def test_s7_at_least_one_variant_inactive(self):
        """S7: Al menos una variante con activo=False, por lo tanto disponible=False."""
        p = self._get_seed_product("S7")
        self.assertTrue(p.disponible)
        self._assert_variant_count(p, 3)
        # Al menos una variante inactiva
        self._assert_at_least_one_variant(p, "activo", False)
        # Esa variante inactiva debe tener disponible=False
        inactivas = [v for v in p.producto_colores.all() if not v.activo]
        for v in inactivas:
            self.assertFalse(self._is_variant_disponible(v),
                             f"{p.nombre}: variante {v.color.nombre} (inactiva) debería ser no disponible")
        # Al menos una variante activa (para confirmar que el producto no está muerto)
        self._assert_at_least_one_variant(p, "activo", True)
        activas = [v for v in p.producto_colores.all() if v.activo]
        for v in activas:
            self.assertTrue(self._is_variant_disponible(v),
                            f"{p.nombre}: variante {v.color.nombre} (activa) debería ser disponible")

    # ------------------------------------------------------------------
    # S8: Dos productos con el mismo item
    # ------------------------------------------------------------------
    def test_s8_cross_product_same_item(self):
        """S8: Dos productos diferentes comparten el mismo valor de item."""
        # Hay dos productos S8
        productos_s8 = ProductosModel.objects.filter(nombre__contains="S8")
        self.assertEqual(productos_s8.count(), 2,
                         f"Se esperaban 2 productos S8, encontrados: {productos_s8.count()}")

        # Ambos deben tener el mismo item en su única variante
        items = []
        for p in productos_s8:
            self.assertEqual(p.producto_colores.count(), 1,
                             f"{p.nombre}: debería tener exactamente 1 variante")
            v = p.producto_colores.first()
            items.append(v.item)

        self.assertEqual(items[0], items[1],
                         f"S8: ambos productos deberían compartir el mismo item. Items: {items}")
        self.assertNotEqual(items[0], "",
                            f"S8: el item compartido no debería ser vacío")

    # ------------------------------------------------------------------
    # Validación de categoría y colores
    # ------------------------------------------------------------------
    def test_seed_category_created(self):
        """La categoría de seed debe existir."""
        cat = CategoriasModel.objects.filter(nombre="[SEED] Staging").first()
        self.assertIsNotNone(cat)

    def test_seed_colors_created(self):
        """Los colores de seed deben existir."""
        seed_colors = ColorModel.objects.filter(nombre__startswith="[SEED]")
        self.assertGreaterEqual(seed_colors.count(), 2)  # Negro y Blanco

    # ------------------------------------------------------------------
    # Verificación de idempotencia
    # ------------------------------------------------------------------
    def test_seed_is_idempotent(self):
        """Correr el seed dos veces no debe crear duplicados."""
        count_antes = ProductosModel.objects.filter(nombre__startswith="[SEED]").count()
        self.assertGreater(count_antes, 0, "No hay productos de seed antes de segunda corrida")

        # Segunda corrida
        call_command("seed_staging", stdout=StringIO(), stderr=StringIO())

        count_despues = ProductosModel.objects.filter(nombre__startswith="[SEED]").count()
        self.assertEqual(count_antes, count_despues,
                         f"El seed no es idempotente: antes={count_antes}, después={count_despues}")

    # ------------------------------------------------------------------
    # Verificación de --clear
    # ------------------------------------------------------------------
    def test_seed_clear_removes_data(self):
        """Correr con --clear debe eliminar y re-crear los datos de seed."""
        # Verificar que hay datos
        count_antes = ProductosModel.objects.filter(nombre__startswith="[SEED]").count()
        self.assertGreater(count_antes, 0, "No hay productos de seed para limpiar")

        # Limpiar (nota: el comando también re-seedea después de limpiar)
        call_command("seed_staging", "--clear", stdout=StringIO(), stderr=StringIO())

        count_despues = ProductosModel.objects.filter(nombre__startswith="[SEED]").count()
        # El comando re-crea los datos después de limpiar, así que debería haber productos
        self.assertGreater(count_despues, 0,
                           f"--clear debería re-crear los productos de seed, pero hay {count_despues}")
        # Verificar que son exactamente los 9 escenarios
        self.assertEqual(count_despues, 9,
                         f"--clear debería re-crear exactamente 9 productos, hay {count_despues}")

    # ------------------------------------------------------------------
    # Verificación de precios efectivos
    # ------------------------------------------------------------------
    def test_all_seed_products_have_correct_precio_efectivo(self):
        """Verificar que todos los productos de seed calculan precio_efectivo correctamente."""
        seed_products = ProductosModel.objects.filter(nombre__startswith="[SEED]")
        self.assertGreater(seed_products.count(), 0, "No hay productos de seed")

        for p in seed_products:
            for v in p.producto_colores.all():
                if v.precio is not None:
                    expected = v.precio
                else:
                    expected = p.precio
                self.assertEqual(v.precio_efectivo, expected,
                                 f"{p.nombre} – {v.color.nombre}: "
                                 f"precio_efectivo={v.precio_efectivo}, esperado={expected}")

    # ------------------------------------------------------------------
    # Verificación de disponibilidad lógica
    # ------------------------------------------------------------------
    def test_disponible_logic(self):
        """
        Reglas de disponibilidad a nivel de variante (igual que el serializer):
        - Variante.activo=False => variante no disponible
        - Variante.stock=0 => variante no disponible
        - Variante.activo=True + stock>0 => variante disponible
        
        Nota: Producto.disponible=False se maneja a nivel de producto,
        no afecta directamente la disponibilidad de la variante en el modelo.
        """
        seed_products = ProductosModel.objects.filter(nombre__startswith="[SEED]")

        for p in seed_products:
            for v in p.producto_colores.all():
                if not v.activo:
                    self.assertFalse(self._is_variant_disponible(v),
                                     f"{p.nombre}: variante inactiva debería ser no disponible")
                elif v.stock <= 0:
                    self.assertFalse(self._is_variant_disponible(v),
                                     f"{p.nombre}: variante sin stock debería ser no disponible")
                else:
                    self.assertTrue(self._is_variant_disponible(v),
                                     f"{p.nombre}: variante activa con stock debería ser disponible")


class DemoSeedTest(TestCase):
    """
    Verifica que --demo crea 20 productos genéricos con [DEMO] prefix,
    múltiples categorías, variantes, y que la limpieza funciona.
    """

    def test_demo_creates_20_products_with_variants(self):
        """--demo debe crear exactamente 20 productos con variantes."""
        stdout = StringIO()
        call_command("seed_staging", "--demo", stdout=stdout, stderr=StringIO())

        demo_products = ProductosModel.objects.filter(nombre__startswith="[DEMO]")
        self.assertEqual(demo_products.count(), 20,
                         f"Se esperaban 20 productos demo, hay {demo_products.count()}")

        # Verificar que todos tienen al menos 1 variante
        for p in demo_products:
            self.assertGreaterEqual(
                p.producto_colores.count(), 1,
                f"{p.nombre}: debería tener al menos 1 variante"
            )

        # Verificar que hay exactamente 5 categorías demo
        from api.models import CategoriasModel
        demo_cats = CategoriasModel.objects.filter(nombre__startswith="[DEMO] ")
        self.assertEqual(demo_cats.count(), 5,
                         f"Se esperaban 5 categorías demo, hay {demo_cats.count()}")

    def test_demo_is_idempotent(self):
        """Correr --demo dos veces no debe duplicar productos."""
        call_command("seed_staging", "--demo", stdout=StringIO(), stderr=StringIO())

        count_before = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        self.assertGreater(count_before, 0)

        # Segunda corrida — debe saltar por idempotencia
        call_command("seed_staging", "--demo", stdout=StringIO(), stderr=StringIO())

        count_after = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        self.assertEqual(count_before, count_after,
                         f"Demo seed no es idempotente: antes={count_before}, después={count_after}")

    def test_demo_clear_removes_and_recreates(self):
        """--demo --clear debe eliminar y re-crear los productos demo."""
        call_command("seed_staging", "--demo", stdout=StringIO(), stderr=StringIO())

        count_before = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        self.assertGreater(count_before, 0)

        # Limpiar y re-seedear
        call_command("seed_staging", "--demo", "--clear", stdout=StringIO(), stderr=StringIO())

        count_after = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        self.assertEqual(count_after, 20,
                         f"--demo --clear debería re-crear 20 productos, hay {count_after}")

    def test_demo_dry_run_does_not_persist(self):
        """--demo --dry-run no debe guardar nada."""
        # Limpiar primero para asegurar estado conocido
        ProductosModel.objects.filter(nombre__startswith="[DEMO]").delete()

        call_command("seed_staging", "--demo", "--dry-run", stdout=StringIO(), stderr=StringIO())

        remaining = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        self.assertEqual(remaining, 0,
                         f"Dry run no debería persistir productos, pero hay {remaining}")

    def test_demo_does_not_break_test_scenarios(self):
        """--demo y seed normal deben coexistir sin afectarse."""
        # Seed normal
        call_command("seed_staging", stdout=StringIO(), stderr=StringIO())

        # Seed demo
        call_command("seed_staging", "--demo", stdout=StringIO(), stderr=StringIO())

        demo_count = ProductosModel.objects.filter(nombre__startswith="[DEMO]").count()
        seed_count = ProductosModel.objects.filter(nombre__startswith="[SEED]").count()

        self.assertGreater(demo_count, 0, "Deberían existir productos demo")
        self.assertGreater(seed_count, 0, "Deberían existir productos seed")
        self.assertEqual(demo_count, 20)
        self.assertEqual(seed_count, 9)
