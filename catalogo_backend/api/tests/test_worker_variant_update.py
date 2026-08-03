from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel, UsuariosModel


def _create_worker(email: str = "worker-update@test.com") -> UsuariosModel:
    worker = UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Update",
        correo=email,
        telefono="555-0000001",
        password="testpass123",
        staff=True,
    )
    worker.worker_role = UsuariosModel.WorkerRole.TOTAL
    worker.save(update_fields=["worker_role"])
    return worker


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

        # Verify response
        self.assertEqual(data["stock"], 5)
        self.assertFalse(data["activo"])
        self.assertEqual(data["item"], "UPD-SKU-002")
        self.assertEqual(data["codigo_barras"], "M012754G3523A4")

        # Verify from DB
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.stock, 5)
        self.assertFalse(self.variante.activo)
        self.assertEqual(self.variante.item, "UPD-SKU-002")
        self.assertEqual(self.variante.codigo_barras, "M012754G3523A4")

    def test_worker_cannot_edit_variant_of_other_worker(self):
        client = APIClient()
        client.force_authenticate(user=self.other_worker)
        resp = client.patch(self.url, {"stock": 1}, format="json")
        self.assertIn(resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_worker_can_update_only_codigo_barras(self):
        resp = self.client.patch(self.url, {"codigo_barras": "ONLYCODE999"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.json()["codigo_barras"], "ONLYCODE999")
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.codigo_barras, "ONLYCODE999")

    def test_worker_can_get_own_variant(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
    
    def test_worker_cannot_update_sku_to_duplicate_variant(self):
        color = _create_color("Azul 2", "#0032D6")
        variant = ProductoVariantesModel.objects.create(
            producto = self.producto,
            color = color,
            item = "SKU2345BL",
            codigo_barras = "",
            stock = 2,
            activo = True
        )
        update_payload = {"item": "SKU2345BL"}
        res = self.client.patch(self.url, update_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn("item", res.data)
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.item, "UPD-SKU-001")

    def test_worker_update_other_fields_with_same_sku(self):
        update_payload = {
            "item": "UPD-SKU-001",
            "stock": 120
        }
        res = self.client.patch(self.url, update_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.item, "UPD-SKU-001")
        self.assertEqual(self.variante.stock, 120)
    
    def test_worker_multiple_variants_with_blank_sku(self):
        # Current variant
        res_1 = self.client.patch(self.url, {"item": ""}, format="json")
        self.assertEqual(res_1.status_code, status.HTTP_200_OK, res_1.data)

        # Another variant with blank SKU.
        v2_color = _create_color("Rojo 2", "#EC1B1B")
        v2 = ProductoVariantesModel.objects.create(
            producto = self.producto,
            color = v2_color,
            item = "",
            codigo_barras = "",
            stock = 20,
            activo = True
        )
        v2_url = f"/api/worker/variants/{v2.id}/"
        res_2 = self.client.patch(v2_url, {"item": ""}, format="json")
        
        # Collision avoided: UniqueConstraint allows blank fields.
        self.assertEqual(res_2.status_code, status.HTTP_200_OK, res_2.data)
        self.variante.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(self.variante.item, "")
        self.assertEqual(v2.item, "")


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