"""
Tests for conditional (producto, item) uniqueness on ProductoVariantesModel.

PR5-BE — Strict TDD cycle:
  RED  → these tests document current/target behavior before the constraint lands
  GREEN → constraint migration + serializer validate_item make them pass
"""
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel, UsuariosModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_product(nombre: str = "Producto Test") -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion="desc",
        precio=Decimal("100.00"),
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
    )


def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)


def _create_variant(
    producto: ProductosModel,
    color: ColorModel,
    item: str = "",
    stock: int = 5,
) -> ProductoVariantesModel:
    return ProductoVariantesModel.objects.create(
        producto=producto,
        color=color,
        item=item,
        stock=stock,
    )


def _create_worker(email: str = "worker@test.com") -> UsuariosModel:
    worker = UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Test",
        correo=email,
        telefono="555-0000000",
        password="testpass123",
        staff=True,
    )
    worker.worker_role = UsuariosModel.WorkerRole.TOTAL
    worker.save(update_fields=["worker_role"])
    return worker


def _create_product_for_worker(worker: UsuariosModel, nombre: str = "Producto Worker") -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion="desc",
        precio=Decimal("100.00"),
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
        worker=worker,
    )


# ---------------------------------------------------------------------------
# Task 7.1 — Current-behavior test (RED): duplicate item is accepted
# without the constraint, two variants with the same non-empty item
# under the same product can coexist.
# After migration 0020+0021, this documents historic behavior only.
# ---------------------------------------------------------------------------

class DuplicateItemCurrentBehaviorTest(TestCase):
    """
    Documents the evolution of item uniqueness behavior.

    BEFORE migration 0021: two variants with the same non-empty item under
    the same product were permitted (no constraint existed).

    AFTER migration 0021 (current state): the partial UniqueConstraint
    unique_producto_item_when_set prevents this; an IntegrityError is raised.

    This class retains the historical test renamed to reflect the CURRENT behavior,
    and adds an explicit assertion that the constraint is now enforced at DB level.
    """

    def test_duplicate_item_accepted_before_constraint(self):
        """
        HISTORICAL CONTEXT: Before migration 0021, two variants with the same
        non-empty item under the same product could be saved without error.
        Migration 0021 introduced a partial UniqueConstraint that now blocks this.

        This test verifies the constraint IS active (current behavior), which
        supersedes the original pre-constraint permissive behavior.
        """
        producto = _create_product("Producto SKU Dup")
        color1 = _create_color("Rojo SKU", "#FF0001")
        color2 = _create_color("Azul SKU", "#0000F1")

        # First variant saves fine
        v1 = _create_variant(producto, color1, item="SKU-001")
        self.assertEqual(v1.item, "SKU-001")

        # Second variant with the same item under the same product now raises
        # IntegrityError because migration 0021 added the partial UniqueConstraint.
        with self.assertRaises(IntegrityError):
            _create_variant(producto, color2, item="SKU-001")


# ---------------------------------------------------------------------------
# Task 7.5 — Target-behavior tests (turn GREEN after constraint + serializer)
# ---------------------------------------------------------------------------

class ItemUniquenessConstraintTest(TestCase):
    """Tests that must pass AFTER migration 0021 is applied."""

    def setUp(self):
        self.producto = _create_product("Producto Unique SKU")
        self.color1 = _create_color("Rojo Uniq", "#FF0002")
        self.color2 = _create_color("Azul Uniq", "#0000F2")
        self.color3 = _create_color("Verde Uniq", "#00FF02")

    def test_duplicate_item_rejected(self):
        """
        After the constraint, saving a second variant with the same
        non-empty item under the same product must raise IntegrityError.
        """
        _create_variant(self.producto, self.color1, item="SKU-DUP")
        with self.assertRaises(IntegrityError):
            _create_variant(self.producto, self.color2, item="SKU-DUP")

    def test_empty_item_not_unique(self):
        """
        Two variants with item='' under the same product must both succeed —
        the partial constraint only applies when item <> ''.
        """
        v1 = _create_variant(self.producto, self.color1, item="")
        v2 = _create_variant(self.producto, self.color2, item="")

        self.assertEqual(v1.item, "")
        self.assertEqual(v2.item, "")
        self.assertEqual(
            ProductoVariantesModel.objects.filter(producto=self.producto, item="").count(),
            2,
        )

    def test_same_item_different_product_accepted(self):
        """
        The same non-empty item value under DIFFERENT products must succeed —
        cross-product SKU reuse is allowed.
        """
        other_producto = _create_product("Otro Producto Unique")
        color4 = _create_color("Gris Uniq", "#808082")

        v1 = _create_variant(self.producto, self.color1, item="SHARED-SKU")
        v2 = _create_variant(other_producto, color4, item="SHARED-SKU")

        self.assertEqual(v1.item, "SHARED-SKU")
        self.assertEqual(v2.item, "SHARED-SKU")


class WorkerFormItemValidationTest(TestCase):
    """Tests the worker API surfaces a field-level error for duplicate items."""

    def setUp(self):
        self.worker = _create_worker("worker-sku@test.com")
        self.producto = _create_product_for_worker(self.worker, "Producto Worker SKU")
        self.color1 = _create_color("Rojo Worker", "#FF0003")
        self.color2 = _create_color("Azul Worker", "#0000F3")
        self.color3 = _create_color("Verde Worker", "#00FF03")

        self.client = APIClient()
        self.client.force_authenticate(user=self.worker)

        self.url = f"/api/worker/productos/{self.producto.id}/variantes/"

    def test_worker_form_surfaces_field_error(self):
        """
        Worker POST to create a second variant with the same non-empty item
        under the same product must return HTTP 400 with 'item' in error keys.
        """
        # Create first variant successfully
        resp = self.client.post(
            self.url,
            {
                "item": "WORKER-SKU-001",
                "color": self.color1.id,
                "stock": 5,
                "codigo_barras": "7501234567890",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        # Attempt to create second variant with same item → must get 400 with 'item' key
        resp2 = self.client.post(
            self.url,
            {
                "item": "WORKER-SKU-001",
                "color": self.color2.id,
                "stock": 3,
                "codigo_barras": "7501234567891",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, 400, resp2.data)
        self.assertIn("item", resp2.data, f"Expected 'item' key in errors, got: {resp2.data}")

    def test_worker_empty_item_allowed_twice(self):
        """
        Worker can create two variants with item='' under the same product — allowed.
        The serializer must set allow_blank=True on the item field for this to work.
        """
        resp1 = self.client.post(
            self.url,
            {
                "item": "",
                "color": self.color1.id,
                "stock": 5,
                "codigo_barras": "7501234567892",
            },
            format="json",
        )
        # If this returns 400 with 'item: blank not allowed', the serializer needs
        # extra_kwargs = {'item': {'allow_blank': True, 'default': ''}}
        self.assertEqual(resp1.status_code, 201, f"Expected 201, got 400: {resp1.data}")

        resp2 = self.client.post(
            self.url,
            {
                "item": "",
                "color": self.color2.id,
                "stock": 3,
                "codigo_barras": "7501234567893",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, 201, f"Expected 201, got 400: {resp2.data}")

    def test_worker_same_item_different_product_accepted(self):
        """
        Worker can reuse a non-empty item under a different product.
        """
        other_producto = _create_product_for_worker(self.worker, "Otro Producto Worker")
        other_url = f"/api/worker/productos/{other_producto.id}/variantes/"
        color4 = _create_color("Negro Worker", "#111113")

        resp1 = self.client.post(
            self.url,
            {
                "item": "CROSS-SKU",
                "color": self.color1.id,
                "stock": 5,
                "codigo_barras": "7501234567894",
            },
            format="json",
        )
        self.assertEqual(resp1.status_code, 201, resp1.data)

        resp2 = self.client.post(
            other_url,
            {
                "item": "CROSS-SKU",
                "color": color4.id,
                "stock": 3,
                "codigo_barras": "7501234567895",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, 201, resp2.data)
