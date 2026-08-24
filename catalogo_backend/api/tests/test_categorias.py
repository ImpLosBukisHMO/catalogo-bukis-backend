from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from api.models import CategoriasModel, ProductosModel


class CategoriasApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cat_vacia = CategoriasModel.objects.create(nombre="Categoría Vacía")
        self.cat_con_activos = CategoriasModel.objects.create(nombre="Categoría con Activos")
        self.cat_con_inactivos = CategoriasModel.objects.create(nombre="Categoría con Inactivos")

        # Producto activo y disponible
        ProductosModel.objects.create(
            nombre="Producto Activo",
            imagen="img/products/p1.jpg",
            descripcion="Desc",
            precio="10.00",
            peso="1kg",
            medidas="10x10",
            disponible=True,
            estado=ProductosModel.EstadoProducto.ACTIVE,
            categoria=self.cat_con_activos,
        )

        # Producto borrador/inactivo
        ProductosModel.objects.create(
            nombre="Producto Borrador",
            imagen="img/products/p2.jpg",
            descripcion="Desc",
            precio="20.00",
            peso="1kg",
            medidas="10x10",
            disponible=True,
            estado=ProductosModel.EstadoProducto.DRAFT,
            categoria=self.cat_con_inactivos,
        )

    def test_list_all_categories_by_default(self):
        res = self.client.get("/api/categorias/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        datos = res.data.get("datos", [])
        nombres = [c["nombre"] for c in datos]
        self.assertIn("Categoría Vacía", nombres)
        self.assertIn("Categoría con Activos", nombres)
        self.assertIn("Categoría con Inactivos", nombres)

    def test_list_only_categories_with_active_products(self):
        res = self.client.get("/api/categorias/?con_productos=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        datos = res.data.get("datos", [])
        nombres = [c["nombre"] for c in datos]
        self.assertIn("Categoría con Activos", nombres)
        self.assertNotIn("Categoría Vacía", nombres)
        self.assertNotIn("Categoría con Inactivos", nombres)
