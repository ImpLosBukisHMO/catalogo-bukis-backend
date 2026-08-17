from decimal import Decimal
from pathlib import Path

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel, UsuariosModel


def _create_worker(email: str = "worker-barcode@test.com") -> UsuariosModel:
    worker = UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Barcode",
        correo=email,
        telefono="555-1234567",
        password="testpass123",
        staff=True,
    )
    worker.worker_role = UsuariosModel.WorkerRole.TOTAL
    worker.save(update_fields=["worker_role"])
    return worker


def _create_product(worker: UsuariosModel, nombre: str = "Producto Barcode") -> ProductosModel:
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


class WorkerVariantBarcodeValidationTest(TestCase):
    def setUp(self):
        self.worker = _create_worker()
        self.producto = _create_product(self.worker)
        self.color1 = _create_color("Rojo Barcode", "#FF1000")
        self.color2 = _create_color("Azul Barcode", "#0010FF")
        self.color3 = _create_color("Verde Barcode", "#00AA10")
        self.client = APIClient()
        self.client.force_authenticate(user=self.worker)
        self.url = f"/api/worker/productos/{self.producto.id}/variantes/"

    def test_new_variant_creation_rejects_missing_barcode(self):
        response = self.client.post(
            self.url,
            {"item": "SKU-NO-BARCODE", "color": self.color1.id, "stock": 5},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            response.data["codigo_barras"][0],
            "El código de barras es obligatorio para nuevas variantes.",
        )

    def test_new_variant_creation_rejects_blank_barcode(self):
        response = self.client.post(
            self.url,
            {
                "item": "SKU-BLANK-BARCODE",
                "color": self.color2.id,
                "stock": 5,
                "codigo_barras": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            response.data["codigo_barras"][0],
            "El código de barras es obligatorio para nuevas variantes.",
        )

    def test_new_variant_creation_accepts_non_empty_barcode(self):
        response = self.client.post(
            self.url,
            {
                "item": "SKU-WITH-BARCODE",
                "color": self.color3.id,
                "stock": 5,
                "codigo_barras": "7501234567000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["codigo_barras"], "7501234567000")
        self.assertTrue(
            ProductoVariantesModel.objects.filter(
                producto=self.producto,
                color=self.color3,
                codigo_barras="7501234567000",
            ).exists()
        )


class LegacyVariantBarcodeCompatibilityTest(TestCase):
    def test_existing_blank_barcode_remains_readable(self):
        worker = _create_worker("worker-legacy-barcode@test.com")
        producto = _create_product(worker, "Producto Legacy Barcode")
        color = _create_color("Legacy Gray", "#777777")
        legacy_variant = ProductoVariantesModel.objects.create(
            producto=producto,
            color=color,
            item="LEGACY-SKU",
            codigo_barras="",
            stock=2,
        )
        client = APIClient()
        client.force_authenticate(user=worker)

        response = client.get("/api/worker/variants/")

        self.assertEqual(response.status_code, 200, response.data)
        payload = next(item for item in response.data if item["variant_id"] == legacy_variant.id)
        self.assertEqual(payload["codigo_barras"], "")


class BarcodeMigrationGraphTest(TestCase):
    def test_api_migration_graph_has_single_linear_leaf(self):
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        api_leaves = [node for node in loader.graph.leaf_nodes() if node[0] == "api"]

        self.assertEqual(api_leaves, [("api", "0038_alter_direccionesmodel_calle_and_more")])

    def test_only_one_0022_api_migration_file_exists(self):
        migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
        migration_names = sorted(path.name for path in migrations_dir.glob("0022*.py"))

        self.assertEqual(migration_names, ["0022_productosmodel_estado.py"])
