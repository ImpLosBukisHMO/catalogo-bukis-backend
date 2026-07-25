from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import ColorModel, ProductoVariantesModel, ProductosModel


def _create_product(nombre: str, *, disponible: bool = True) -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion=f"{nombre} desc",
        precio=Decimal("100.00"),
        peso=Decimal("1.00"),
        medidas="10x10x10",
        disponible=disponible,
        estado=ProductosModel.EstadoProducto.ACTIVE,
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


class PublicCatalogPaginationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_productos_endpoint_returns_paginated_shape(self):
        for index in range(25):
            _create_product(f"Producto {index:02d}")

        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data.keys()), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 25)
        self.assertIsNone(response.data["previous"])
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("page=2", response.data["next"])

    def test_producto_variantes_endpoint_returns_paginated_shape(self):
        color = _create_color("Base", "#120000")
        for index in range(25):
            producto = _create_product(f"Variant Product {index:02d}")
            _create_variant(producto, color)

        response = self.client.get("/api/producto-variantes/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data.keys()), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 25)
        self.assertIsNone(response.data["previous"])
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("page=2", response.data["next"])

    def test_existing_filters_continue_working_on_paginated_endpoints(self):
        red = _create_color("Rojo Filtro", "#AA0001")
        blue = _create_color("Azul Filtro", "#0000AA")
        visible = _create_product("Visible filtrado")
        hidden = _create_product("Oculto filtrado", disponible=False)
        red_variant = _create_variant(visible, red, stock=3, activo=True)
        _create_variant(visible, blue, stock=0, activo=False)
        _create_variant(hidden, red, stock=3, activo=True)

        product_response = self.client.get(
            "/api/productos/",
            {"disponible": "true", "color": red.id},
        )
        variant_response = self.client.get(
            "/api/producto-variantes/",
            {"producto": visible.id, "activo": "true"},
        )

        self.assertEqual(product_response.status_code, 200, product_response.data)
        self.assertEqual([item["id"] for item in product_response.data["results"]], [visible.id])

        self.assertEqual(variant_response.status_code, 200, variant_response.data)
        self.assertEqual([item["id"] for item in variant_response.data["results"]], [red_variant.id])

    def test_page_size_respects_max_limit(self):
        for index in range(150):
            _create_product(f"Max page {index:03d}")

        response = self.client.get("/api/productos/", {"page_size": 999})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 150)
        self.assertEqual(len(response.data["results"]), 100)

    def test_empty_response_returns_empty_results(self):
        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 0)
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
        self.assertEqual(response.data["results"], [])

    def test_frontend_contract_fields_remain_compatible(self):
        producto = _create_product("Contrato frontend")

        response = self.client.get("/api/productos/", {"page": 1, "page_size": 1})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["previous"])
        self.assertEqual(len(response.data["results"]), 1)
        payload = response.data["results"][0]
        self.assertEqual(payload["id"], producto.id)
        self.assertEqual(payload["nombre"], producto.nombre)
        self.assertIn("categoria", payload)
