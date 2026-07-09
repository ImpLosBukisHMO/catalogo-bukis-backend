from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import (
    CarritoItemModel,
    CarritoModel,
    CategoriasModel,
    ColorModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    ProductosModel,
    UsuariosModel,
)


def _create_worker(email: str = "worker-publication@test.com") -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Publication",
        correo=email,
        telefono="555-7654321",
        password="testpass123",
        staff=True,
    )


def _create_user(email: str = "shopper-publication@test.com") -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Shopper",
        apellido="Publication",
        correo=email,
        telefono="555-0000000",
        password="testpass123",
        staff=False,
    )


def _create_category(name: str = "Accesorios") -> CategoriasModel:
    return CategoriasModel.objects.create(nombre=name)


def _create_product(
    name: str,
    *,
    estado: str,
    disponible: bool = True,
    worker: UsuariosModel | None = None,
) -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=name,
        imagen="img/products/default.jpg",
        descripcion=f"{name} desc",
        precio=Decimal("100.00"),
        peso=Decimal("1.00"),
        medidas="10x10x10",
        disponible=disponible,
        estado=estado,
        worker=worker,
    )


def _create_variant(
    producto: ProductosModel,
    color_name: str = "Rojo",
    color_hex: str = "#FF0000",
    *,
    item: str = "SKU-001",
    stock: int = 5,
    activo: bool = True,
) -> ProductoVariantesModel:
    color = ColorModel.objects.create(nombre=color_name, hex=color_hex)
    return ProductoVariantesModel.objects.create(
        producto=producto,
        color=color,
        item=item,
        stock=stock,
        activo=activo,
    )


def _attach_variant_image(producto: ProductosModel, variante: ProductoVariantesModel) -> ProductosImagenesModel:
    return ProductosImagenesModel.objects.create(
        producto=producto,
        variante=variante,
        imagen="img/products/galeria/publication-variant.jpg",
        es_principal=True,
        orden=0,
    )


class ProductPublicationStateTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_worker_created_products_default_to_draft(self):
        worker = _create_worker()
        category = _create_category()
        self.client.force_authenticate(user=worker)
        image = SimpleUploadedFile(
            "product.gif",
            (
                b"GIF87a\x01\x00\x01\x00\x80\x00\x00"
                b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,"
                b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

        response = self.client.post(
            "/api/worker/productos/",
            {
                "nombre": "Nuevo producto",
                "imagen": image,
                "descripcion": "Draft first",
                "precio": "100.00",
                "peso": "1.00",
                "medidas": "10x10x10",
                "capacidad": "",
                "disponible": True,
                "estado": ProductosModel.EstadoProducto.ACTIVE,
                "categoria_id": category.id,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["estado"], ProductosModel.EstadoProducto.DRAFT)

    def test_public_catalog_only_lists_active_products(self):
        active_product = _create_product("Activo", estado=ProductosModel.EstadoProducto.ACTIVE)
        draft_product = _create_product("Draft", estado=ProductosModel.EstadoProducto.DRAFT)
        archived_product = _create_product("Archived", estado=ProductosModel.EstadoProducto.ARCHIVED)

        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        product_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(active_product.id, product_ids)
        self.assertNotIn(draft_product.id, product_ids)
        self.assertNotIn(archived_product.id, product_ids)

    def test_archived_products_are_hidden_from_public_detail_and_variant_list(self):
        archived_product = _create_product("Archived detail", estado=ProductosModel.EstadoProducto.ARCHIVED)
        variant = _create_variant(
            archived_product,
            color_name="Azul archived",
            color_hex="#0000FF",
        )

        detail_response = self.client.get(f"/api/productos/{archived_product.id}/")
        variants_response = self.client.get(f"/api/producto-variantes/?producto={archived_product.id}")

        self.assertEqual(detail_response.status_code, 404, detail_response.data)
        self.assertEqual(variants_response.status_code, 200, variants_response.data)
        self.assertNotIn(variant.id, [item["id"] for item in variants_response.data["results"]])

    def test_inactive_variants_are_hidden_from_public_list_and_detail(self):
        product = _create_product("Activo con variante inactiva", estado=ProductosModel.EstadoProducto.ACTIVE)
        inactive_variant = _create_variant(
            product,
            color_name="Gris inactivo",
            color_hex="#888888",
            item="INACTIVE-SKU",
            activo=False,
        )

        list_response = self.client.get(
            "/api/producto-variantes/",
            {"producto": product.id, "activo": "false"},
        )
        detail_response = self.client.get(f"/api/producto-variantes/{inactive_variant.id}/")

        self.assertEqual(list_response.status_code, 200, list_response.data)
        self.assertEqual(list_response.data["results"], [])
        self.assertEqual(detail_response.status_code, 404, detail_response.data)

    def test_public_detail_only_returns_active_variants(self):
        product = _create_product("Activo con mezcla de variantes", estado=ProductosModel.EstadoProducto.ACTIVE)
        active_variant = _create_variant(
            product,
            color_name="Verde activo",
            color_hex="#00AA00",
            item="ACTIVE-SKU",
            activo=True,
        )
        inactive_variant = _create_variant(
            product,
            color_name="Rojo inactivo",
            color_hex="#AA0000",
            item="INACTIVE-SKU",
            activo=False,
        )

        response = self.client.get(f"/api/productos/{product.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        returned_ids = [item["id"] for item in response.data["variantes"]]
        self.assertEqual(returned_ids, [active_variant.id])
        self.assertNotIn(inactive_variant.id, returned_ids)

    def test_public_catalog_endpoints_reject_mutations(self):
        producto = _create_product("Solo lectura", estado=ProductosModel.EstadoProducto.ACTIVE)
        variante = _create_variant(producto, color_name="Verde", color_hex="#00FF00")

        create_product_response = self.client.post(
            "/api/productos/",
            {"nombre": "Intento público"},
            format="json",
        )
        update_product_response = self.client.patch(
            f"/api/productos/{producto.id}/",
            {"nombre": "Mutado"},
            format="json",
        )
        create_variant_response = self.client.post(
            "/api/producto-variantes/",
            {"producto": producto.id, "color": variante.color_id, "item": "NEW-SKU"},
            format="json",
        )
        delete_variant_response = self.client.delete(
            f"/api/producto-variantes/{variante.id}/",
        )

        self.assertEqual(create_product_response.status_code, 405, create_product_response.data)
        self.assertEqual(update_product_response.status_code, 405, update_product_response.data)
        self.assertEqual(create_variant_response.status_code, 405, create_variant_response.data)
        self.assertEqual(delete_variant_response.status_code, 405, delete_variant_response.data)

    def test_publish_returns_clear_validation_errors(self):
        worker = _create_worker("worker-validation@test.com")
        self.client.force_authenticate(user=worker)
        producto = _create_product(
            "Incomplete draft",
            estado=ProductosModel.EstadoProducto.DRAFT,
            worker=worker,
        )

        response = self.client.patch(
            f"/api/worker/productos/{producto.id}/",
            {"estado": ProductosModel.EstadoProducto.ACTIVE},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("categoria", response.data)
        self.assertIn("variantes", response.data)
        self.assertIn("item", response.data)
        self.assertIn("stock", response.data)
        self.assertIn("imagenes", response.data)

    def test_publish_succeeds_when_product_is_ready(self):
        worker = _create_worker("worker-ready@test.com")
        self.client.force_authenticate(user=worker)
        category = _create_category("Lista")
        producto = _create_product(
            "Ready draft",
            estado=ProductosModel.EstadoProducto.DRAFT,
            worker=worker,
        )
        variante = _create_variant(
            producto,
            color_name="Negro ready",
            color_hex="#111111",
            item="READY-SKU",
            stock=8,
        )
        _attach_variant_image(producto, variante)

        response = self.client.patch(
            f"/api/worker/productos/{producto.id}/",
            {
                "estado": ProductosModel.EstadoProducto.ACTIVE,
                "categoria_id": category.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, ProductosModel.EstadoProducto.ACTIVE)
        self.assertEqual(response.data["estado"], ProductosModel.EstadoProducto.ACTIVE)

    def test_active_product_patch_still_enforces_publish_validation(self):
        worker = _create_worker("worker-active-patch@test.com")
        self.client.force_authenticate(user=worker)
        category = _create_category("Patch validation")
        producto = _create_product(
            "Already active",
            estado=ProductosModel.EstadoProducto.ACTIVE,
            worker=worker,
        )
        producto.categoria = category
        producto.save(update_fields=["categoria"])
        variante = _create_variant(
            producto,
            color_name="Negro patch",
            color_hex="#222222",
            item="PATCH-SKU",
            stock=4,
        )
        _attach_variant_image(producto, variante)

        response = self.client.patch(
            f"/api/worker/productos/{producto.id}/",
            {"disponible": False},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("disponible", response.data)
        producto.refresh_from_db()
        self.assertTrue(producto.disponible)

    def test_publish_rejects_whitespace_only_sku(self):
        worker = _create_worker("worker-whitespace-sku@test.com")
        self.client.force_authenticate(user=worker)
        category = _create_category("SKU requerido")
        producto = _create_product(
            "Whitespace SKU",
            estado=ProductosModel.EstadoProducto.DRAFT,
            worker=worker,
        )
        variante = _create_variant(
            producto,
            color_name="Blanco",
            color_hex="#FFFFFF",
            item="   ",
            stock=3,
        )
        _attach_variant_image(producto, variante)

        response = self.client.patch(
            f"/api/worker/productos/{producto.id}/",
            {
                "estado": ProductosModel.EstadoProducto.ACTIVE,
                "categoria_id": category.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("item", response.data)
        producto.refresh_from_db()
        self.assertEqual(producto.estado, ProductosModel.EstadoProducto.DRAFT)


class CartPublicationGuardsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _create_user()
        self.client.force_authenticate(user=self.user)

    def test_add_to_cart_rejects_variants_from_non_public_products(self):
        cases = [
            (ProductosModel.EstadoProducto.DRAFT, True),
            (ProductosModel.EstadoProducto.ARCHIVED, True),
            (ProductosModel.EstadoProducto.ACTIVE, False),
        ]

        for index, (estado, disponible) in enumerate(cases, start=1):
            product = _create_product(
                f"Hidden product {index}",
                estado=estado,
                disponible=disponible,
            )
            variant = _create_variant(
                product,
                color_name=f"Color hidden {index}",
                color_hex=f"#AA0{index}0{index}",
                item=f"HIDDEN-{index}",
            )

            response = self.client.post(
                "/api/carrito/items/",
                {"variante_id": variant.id, "cantidad": 1},
                format="json",
            )

            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn("no está disponible para la venta pública", response.data["detail"])

        self.assertEqual(CarritoItemModel.objects.count(), 0)

    def test_checkout_rejects_cart_items_when_product_is_no_longer_public(self):
        product = _create_product(
            "Was public",
            estado=ProductosModel.EstadoProducto.ACTIVE,
            disponible=True,
        )
        variant = _create_variant(
            product,
            color_name="Negro checkout",
            color_hex="#111111",
            item="CHECKOUT-SKU",
            stock=3,
        )
        cart = CarritoModel.objects.create(cliente=self.user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=cart, variante=variant, cantidad=1)
        product.estado = ProductosModel.EstadoProducto.ARCHIVED
        product.save(update_fields=["estado", "updated_at"])

        response = self.client.post("/api/carrito/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("ya no está disponible para la venta pública", response.data["detail"])
        self.assertEqual(CarritoItemModel.objects.filter(carrito=cart).count(), 1)
