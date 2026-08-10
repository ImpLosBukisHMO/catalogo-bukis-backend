from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel, UsuariosModel


def _create_user(email: str, staff: bool = False) -> UsuariosModel:
    user = UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="555-1234567",
        password="testpass123",
        staff=staff,
    )
    if staff:
        user.worker_role = UsuariosModel.WorkerRole.TOTAL
        user.save(update_fields=["worker_role"])
    return user


def _create_product(
    nombre: str,
    *,
    disponible: bool = True,
    estado: str = ProductosModel.EstadoProducto.ACTIVE,
    worker: UsuariosModel | None = None,
) -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion=f"{nombre} desc",
        precio=Decimal("100.00"),
        peso=Decimal("1.00"),
        medidas="10x10x10",
        disponible=disponible,
        estado=estado,
        worker=worker,
    )


def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)


def _create_variant(
    producto: ProductosModel,
    color: ColorModel,
    *,
    stock: int = 5,
    activo: bool = True,
) -> ProductoVariantesModel:
    return ProductoVariantesModel.objects.create(
        producto=producto,
        color=color,
        stock=stock,
        activo=activo,
    )


class ProductAvailabilityCurrentBehaviorTest(TestCase):
    def test_disponible_false_product_appears_in_listing(self):
        client = APIClient()
        producto = _create_product("Hidden Today", disponible=False)
        _create_variant(producto, _create_color("Rojo availability", "#FF0000"), stock=3)

        response = client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(producto.id, [item["id"] for item in response.data["results"]])

    def test_disponible_true_product_appears(self):
        client = APIClient()
        producto = _create_product("Visible Today", disponible=True)
        _create_variant(producto, _create_color("Azul availability", "#0000FF"), stock=3)

        response = client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(producto.id, [item["id"] for item in response.data["results"]])

    def test_disponible_false_returns_404_on_detail(self):
        client = APIClient()
        producto = _create_product("Hidden Detail", disponible=False)
        _create_variant(producto, _create_color("Verde availability", "#00FF00"), stock=3)

        response = client.get(f"/api/productos/{producto.id}/")

        self.assertEqual(response.status_code, 404, response.data)

    def test_worker_can_edit_disponible_false_product(self):
        client = APIClient()
        worker = _create_user("worker-availability@test.com", staff=True)
        client.force_authenticate(user=worker)
        producto = _create_product(
            "Worker Hidden",
            disponible=False,
            estado=ProductosModel.EstadoProducto.DRAFT,
            worker=worker,
        )
        _create_variant(producto, _create_color("Negro availability", "#111111"), stock=3)

        response = client.patch(
            f"/api/worker/productos/{producto.id}/",
            {"nombre": "Worker Hidden Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Worker Hidden Updated")
