from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel, UsuariosModel


def _create_worker(email: str = "worker-update@test.com") -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Update",
        correo=email,
        telefono="555-0000001",
        password="testpass123",
        staff=True,
    )


def _create_product(worker: UsuariosModel, nombre: str = "Producto Update") -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion="desc",
        precio=Decimal("100.00"),
        peso=Decimal("1.00"),
        medidas="10x10x10",
        disponible=True,
        worker=worker,
        estado=ProductosModel.EstadoProducto.DRAFT,
    )


def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)


class WorkerVariantUpdateTest(TestCase):
    """Tests para el endpoint privado PATCH /api/worker/variants/<id>/"""

    def setUp(self):
        self.worker = _create_worker()
        self.other_worker = _create_worker("worker-other@test.com")
        self.producto = _create_product(self.worker)
        self.color = _create_color("Naranja Update", "#FF8800")
        self.variante = ProductoVariantesModel.objects.create(
            producto=self.producto,
            color=self.color,
            item="UPD-SKU-001",
            codigo_barras="",
            stock=10,
            activo=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.worker)
        self.url = f"/api/worker/variants/{self.variante.id}/"

    # ------------------------------------------------------------------
    # 1️⃣ PATCH exitoso — actualizar stock, activo, item y codigo_barras
    # ------------------------------------------------------------------
    def test_worker_updates_own_variant(self):
        payload = {
            "stock": 5,
            "activo": False,
            "item": "UPD-SKU-002",
            "codigo_barras": "M012754G3523A4",
        }
        resp = self.client.patch(self.url, payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        data = resp.json()

        # Verificar respuesta
        self.assertEqual(data["stock"], 5)
        self.assertFalse(data["activo"])
        self.assertEqual(data["item"], "UPD-SKU-002")
        self.assertEqual(data["codigo_barras"], "M012754G3523A4")

        # Verificar en la base de datos
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.stock, 5)
        self.assertFalse(self.variante.activo)
        self.assertEqual(self.variante.item, "UPD-SKU-002")
        self.assertEqual(self.variante.codigo_barras, "M012754G3523A4")

    # ------------------------------------------------------------------
    # 2️⃣ Intento de editar variante de otro worker → 404 (no encontrada)
    # ------------------------------------------------------------------
    def test_worker_cannot_edit_variant_of_other_worker(self):
        client = APIClient()
        client.force_authenticate(user=self.other_worker)

        resp = client.patch(self.url, {"stock": 1}, format="json")

        # La vista filtra por producto__worker=request.user, así que la
        # variante simplemente "no existe" para el otro worker → 404.
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    # ------------------------------------------------------------------
    # 3️⃣ Edición solo de codigo_barras (campo aislado)
    # ------------------------------------------------------------------
    def test_worker_can_update_only_codigo_barras(self):
        resp = self.client.patch(self.url, {"codigo_barras": "ONLYCODE999"}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.json()["codigo_barras"], "ONLYCODE999")

        self.variante.refresh_from_db()
        self.assertEqual(self.variante.codigo_barras, "ONLYCODE999")

    # ------------------------------------------------------------------
    # 4️⃣ GET de variante propia funciona
    # ------------------------------------------------------------------
    def test_worker_can_get_own_variant(self):
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)


class PublicVariantEndpointReadOnlyTest(TestCase):
    """Confirma que el endpoint público sigue siendo solo lectura."""

    def setUp(self):
        self.worker = _create_worker("worker-public@test.com")
        self.producto = _create_product(self.worker, "Producto Público")
        self.producto.estado = ProductosModel.EstadoProducto.ACTIVE
        self.producto.save()
        self.color = _create_color("Público Gris", "#999999")
        self.variante = ProductoVariantesModel.objects.create(
            producto=self.producto,
            color=self.color,
            item="PUB-SKU-001",
            codigo_barras="7501234567890",
            stock=5,
            activo=True,
        )
        self.url = f"/api/producto-variantes/{self.variante.id}/"

    def test_public_get_works(self):
        client = APIClient()  # sin auth
        resp = client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_public_patch_returns_405(self):
        client = APIClient()  # sin auth
        resp = client.patch(self.url, {"stock": 0}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)