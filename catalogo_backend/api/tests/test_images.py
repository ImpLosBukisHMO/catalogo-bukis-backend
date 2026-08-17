import os
import shutil
import tempfile

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.test.utils import override_settings

from rest_framework.test import APIClient

from api.models import (
    CarritoItemModel,
    CarritoModel,
    ColorModel,
    PedidoProductosModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    ProductosModel,
    UsuariosModel,
)
from api.serializer.worker import WorkerVariantSerializer as WorkerVariantApiSerializer
from api.serializers import (
    CarritoItemReadSerializer,
    FavoritoVarianteSerializer,
    ProductoDetalleSerializer,
    ProductosSerializer,
)
from api.utils.imagenes import get_public_product_gallery_images, get_variante_imagen


def _media_url(path: str) -> str:
    return f"{settings.MEDIA_URL}{path}"


def _create_user(
    email: str,
    staff: bool = False,
    *,
    worker_role: str | None = None,
    can_edit_products: bool = False,
) -> UsuariosModel:
    user = UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="555-1234567",
        password="testpass123",
        staff=staff,
    )
    update_fields = []
    if worker_role is not None:
        user.worker_role = worker_role
        update_fields.append("worker_role")
    elif staff:
        user.worker_role = UsuariosModel.WorkerRole.TOTAL
        update_fields.append("worker_role")

    if can_edit_products:
        user.can_edit_products = True
        update_fields.append("can_edit_products")

    if update_fields:
        user.save(update_fields=update_fields)
    return user


def _create_media_file(path: str) -> None:
    if not path:
        return
    absolute_path = os.path.join(settings.MEDIA_ROOT, path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "wb") as file_obj:
        file_obj.write(b"test-image")


def _create_product(
    nombre: str,
    imagen: str = "img/products/default.jpg",
    *,
    create_file: bool = True,
    worker: UsuariosModel | None = None,
) -> ProductosModel:
    if imagen and create_file:
        _create_media_file(imagen)
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen=imagen,
        descripcion=f"{nombre} desc",
        precio="100.00",
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
        estado=ProductosModel.EstadoProducto.ACTIVE,
        worker=worker,
    )


def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)


def _create_variant(producto: ProductosModel, color: ColorModel, stock: int = 5) -> ProductoVariantesModel:
    return ProductoVariantesModel.objects.create(
        producto=producto,
        color=color,
        stock=stock,
        activo=True,
    )

def _attach_image(
    producto: ProductosModel,
    *,
    variante: ProductoVariantesModel | None = None,
    path: str,
    es_principal: bool = False,
    orden: int = 0,
    create_file: bool = True,
) -> ProductosImagenesModel:
    if path and create_file:
        _create_media_file(path)
    return ProductosImagenesModel.objects.create(
        producto=producto,
        variante=variante,
        imagen=path,
        es_principal=es_principal,
        orden=orden,
    )


class ImageStorageTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.temp_media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)
        super().tearDown()


class ImageConsumerCurrentBehaviorTest(ImageStorageTestCase):
    def test_public_product_serializer_falls_back_to_worker_gallery_image_when_legacy_field_empty(self):
        producto = _create_product("Public Fallback", imagen="")
        variante = _create_variant(producto, _create_color("Cobre", "#B87333"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-fallback.jpg",
            es_principal=True,
        )

        data = ProductosSerializer(producto).data

        self.assertEqual(data["imagen"], _media_url("img/products/galeria/public-fallback.jpg"))

    def test_public_product_serializer_preserves_legacy_image_when_present(self):
        producto = _create_product("Legacy Public", imagen="img/products/legacy-public.jpg")
        variante = _create_variant(producto, _create_color("Bronce", "#CD7F32"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-ignored.jpg",
            es_principal=True,
        )

        data = ProductosSerializer(producto).data

        self.assertEqual(data["imagen"], _media_url("img/products/legacy-public.jpg"))

    def test_favorito_serializer_returns_variant_principal_image(self):
        producto = _create_product("Favorito")
        variante = _create_variant(producto, _create_color("Rojo", "#FF0000"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/favorito-variante.jpg",
            es_principal=True,
        )
        data = FavoritoVarianteSerializer(variante).data
        self.assertEqual(data["imagen"], _media_url("img/products/galeria/favorito-variante.jpg"))

    def test_carrito_item_serializer_falls_back_to_product_principal_image(self):
        user = _create_user("cart-image@test.com")
        producto = _create_product("Carrito")
        variante = _create_variant(producto, _create_color("Azul", "#0000FF"))
        _attach_image(
            producto,
            path="img/products/galeria/producto-principal.jpg",
            es_principal=True,
        )
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        item = CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=1)
        data = CarritoItemReadSerializer(item).data
        self.assertEqual(data["imagen"], _media_url("img/products/galeria/producto-principal.jpg"))

    def test_worker_variant_serializer_falls_back_to_product_principal_image(self):
        producto = _create_product("Worker")
        variante = _create_variant(producto, _create_color("Verde", "#00FF00"))
        _attach_image(
            producto,
            path="img/products/galeria/worker-producto-principal.jpg",
            es_principal=True,
        )
        data = WorkerVariantApiSerializer(variante).data
        self.assertEqual(data["imagen_principal"], _media_url("img/products/galeria/worker-producto-principal.jpg"))

    def test_checkout_snapshot_uses_variant_any_image_before_product_default(self):
        client = APIClient()
        user = _create_user("checkout-image@test.com")
        client.force_authenticate(user=user)
        producto = _create_product("Checkout", imagen="img/products/product-default.jpg")
        variante = _create_variant(producto, _create_color("Negro", "#111111"), stock=3)
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/checkout-variant-any.jpg",
            es_principal=False,
        )
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=1)
        response = client.post("/api/carrito/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.imagen_principal_snapshot, _media_url("img/products/galeria/checkout-variant-any.jpg"))

    def test_checkout_snapshot_stores_empty_string_when_all_image_files_are_missing(self):
        client = APIClient()
        user = _create_user("checkout-image-missing@test.com")
        client.force_authenticate(user=user)
        producto = _create_product(
            "Checkout Missing",
            imagen="img/products/checkout-missing-legacy.jpg",
            create_file=False,
        )
        variante = _create_variant(producto, _create_color("Grafito", "#333333"), stock=3)
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/checkout-missing-variant.jpg",
            es_principal=True,
            create_file=False,
        )
        _attach_image(
            producto,
            path="img/products/galeria/checkout-missing-product.jpg",
            es_principal=True,
            create_file=False,
        )
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=1)

        response = client.post("/api/carrito/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.imagen_principal_snapshot, "")


class PublicProductImageEndpointContractTest(ImageStorageTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_product_list_uses_gallery_fallback_when_legacy_image_is_missing(self):
        producto = _create_product("Public List Fallback", imagen="")
        variante = _create_variant(producto, _create_color("Fallback List", "#BADA55"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-list-fallback.jpg",
            es_principal=True,
        )

        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        payload = next(item for item in response.data["results"] if item["id"] == producto.id)
        self.assertEqual(payload["imagen"], _media_url("img/products/galeria/public-list-fallback.jpg"))

    def test_product_detail_uses_gallery_fallback_when_legacy_image_is_missing(self):
        producto = _create_product("Public Detail Fallback", imagen="")
        variante = _create_variant(producto, _create_color("Fallback Detail", "#55DADA"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-detail-fallback.jpg",
            es_principal=True,
        )

        response = self.client.get(f"/api/productos/{producto.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["imagen"], _media_url("img/products/galeria/public-detail-fallback.jpg"))

    def test_product_list_preserves_legacy_image_when_gallery_image_also_exists(self):
        producto = _create_product("Public Legacy Wins", imagen="img/products/public-legacy-wins.jpg")
        variante = _create_variant(producto, _create_color("Legacy Wins", "#DADA55"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-legacy-ignored.jpg",
            es_principal=True,
        )

        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        payload = next(item for item in response.data["results"] if item["id"] == producto.id)
        self.assertEqual(payload["imagen"], _media_url("img/products/public-legacy-wins.jpg"))

    def test_product_list_skips_missing_gallery_files_when_valid_gallery_file_exists(self):
        producto = _create_product("Public Missing Gallery", imagen="")
        variante = _create_variant(producto, _create_color("Missing Gallery", "#445566"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-missing-gallery-1.jpg",
            es_principal=True,
            orden=0,
            create_file=False,
        )
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-missing-gallery-2.jpg",
            orden=1,
            create_file=False,
        )
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/public-valid-gallery.jpg",
            orden=2,
        )

        response = self.client.get("/api/productos/")

        self.assertEqual(response.status_code, 200, response.data)
        payload = next(item for item in response.data["results"] if item["id"] == producto.id)
        self.assertEqual(payload["imagen"], _media_url("img/products/galeria/public-valid-gallery.jpg"))

    def test_product_detail_returns_null_when_all_gallery_and_legacy_files_are_missing(self):
        producto = _create_product("All Missing", imagen="img/products/all-missing-legacy.jpg", create_file=False)
        variante = _create_variant(producto, _create_color("No Files", "#112233"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/all-missing-1.jpg",
            es_principal=True,
            create_file=False,
        )
        _attach_image(
            producto,
            path="img/products/galeria/all-missing-2.jpg",
            orden=1,
            create_file=False,
        )

        response = self.client.get(f"/api/productos/{producto.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["imagen"])

    def test_product_images_list_excludes_rows_with_missing_files(self):
        producto = _create_product("Gallery List", imagen="")
        valid_image = _attach_image(
            producto,
            path="img/products/galeria/gallery-list-valid.jpg",
            orden=1,
        )
        _attach_image(
            producto,
            path="img/products/galeria/gallery-list-missing.jpg",
            orden=0,
            create_file=False,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [valid_image.id])
        self.assertTrue(
            response.data[0]["imagen"].endswith(
                _media_url("img/products/galeria/gallery-list-valid.jpg")
            )
        )

    def test_public_product_images_list_returns_one_valid_image_for_same_variant(self):
        producto = _create_product("One Per Variant", imagen="")
        variante = _create_variant(producto, _create_color("Unica", "#101010"))
        expected = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/one-per-variant-principal.jpg",
            es_principal=True,
            orden=5,
        )
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/one-per-variant-secondary.jpg",
            orden=0,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [expected.id])

    def test_variant_scoped_images_list_returns_all_existing_images_for_same_variant(self):
        producto = _create_product("Variant Gallery", imagen="")
        variante = _create_variant(producto, _create_color("Galeria", "#121212"))
        second = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/variant-gallery-second.jpg",
            orden=1,
        )
        first = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/variant-gallery-first.jpg",
            es_principal=True,
            orden=3,
        )

        response = self.client.get(f"/api/productos-imagenes/?variante={variante.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [second.id, first.id])

    def test_variant_scoped_images_list_excludes_missing_files(self):
        producto = _create_product("Variant Gallery Missing", imagen="")
        variante = _create_variant(producto, _create_color("Faltante", "#343434"))
        expected = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/variant-gallery-valid.jpg",
            orden=1,
        )
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/variant-gallery-missing.jpg",
            es_principal=True,
            orden=0,
            create_file=False,
        )

        response = self.client.get(f"/api/productos-imagenes/?variante={variante.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [expected.id])

    def test_public_product_images_list_returns_one_valid_image_per_variant(self):
        producto = _create_product("Two Variants", imagen="")
        variante_a = _create_variant(producto, _create_color("A", "#220011"))
        variante_b = _create_variant(producto, _create_color("B", "#003322"))
        image_a = _attach_image(
            producto,
            variante=variante_a,
            path="img/products/galeria/two-variants-a.jpg",
            orden=1,
        )
        image_b = _attach_image(
            producto,
            variante=variante_b,
            path="img/products/galeria/two-variants-b.jpg",
            orden=2,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [image_a.id, image_b.id])

    def test_public_product_images_list_skips_missing_same_variant_and_keeps_valid_one(self):
        producto = _create_product("Mixed Variant", imagen="")
        variante = _create_variant(producto, _create_color("Mix", "#AB1200"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/mixed-variant-missing.jpg",
            es_principal=True,
            orden=0,
            create_file=False,
        )
        expected = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/mixed-variant-valid.jpg",
            orden=1,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [expected.id])

    def test_worker_product_images_list_keeps_public_shape_for_authenticated_worker(self):
        worker = _create_user("gallery-worker@test.com", staff=True, can_edit_products=True)
        self.client.force_authenticate(user=worker)

        producto = _create_product("Worker Gallery", imagen="")
        variante = _create_variant(producto, _create_color("Worker", "#4455AA"))
        image_a = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/worker-gallery-a.jpg",
            es_principal=True,
            orden=0,
        )
        image_b = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/worker-gallery-b.jpg",
            orden=1,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [image_a.id])

    def test_partial_worker_get_on_foreign_product_does_not_receive_management_shape(self):
        owner = _create_user(
            "gallery-owner@test.com",
            staff=True,
            worker_role=UsuariosModel.WorkerRole.TOTAL,
        )
        partial_worker = _create_user(
            "gallery-partial@test.com",
            staff=True,
            worker_role=UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=True,
        )
        self.client.force_authenticate(user=partial_worker)

        producto = _create_product("Foreign Worker Gallery", imagen="", worker=owner)
        variante = _create_variant(producto, _create_color("Foreign", "#7744AA"))
        image_a = _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/foreign-gallery-a.jpg",
            es_principal=True,
            orden=0,
        )
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/foreign-gallery-b.jpg",
            orden=1,
        )

        response = self.client.get(f"/api/productos-imagenes/?producto={producto.id}")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [image_a.id])


class PublicProductGalleryHelperTest(ImageStorageTestCase):
    def test_helper_returns_single_product_level_fallback_image(self):
        producto = _create_product("Product Fallback Only", imagen="")
        _attach_image(
            producto,
            path="img/products/galeria/product-fallback-secondary.jpg",
            orden=0,
        )
        expected = _attach_image(
            producto,
            path="img/products/galeria/product-fallback-principal.jpg",
            es_principal=True,
            orden=5,
        )

        selected = get_public_product_gallery_images(producto.imagenes.order_by("orden", "id"))

        self.assertEqual([image.id for image in selected], [expected.id])


class VarianteImageHelperTest(ImageStorageTestCase):
    def test_returns_variant_principal_image(self):
        producto = _create_product("Helper Principal")
        variante = _create_variant(producto, _create_color("Coral", "#FF7F50"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/helper-variant-principal.jpg",
            es_principal=True,
        )
        result = get_variante_imagen(variante)
        self.assertEqual(result, _media_url("img/products/galeria/helper-variant-principal.jpg"))
        self.assertTrue(isinstance(result, str) or result is None)

    def test_returns_variant_any_image_when_no_variant_principal_exists(self):
        producto = _create_product("Helper Any")
        variante = _create_variant(producto, _create_color("Lila", "#C8A2C8"))
        _attach_image(
            producto,
            variante=variante,
            path="img/products/galeria/helper-variant-any.jpg",
            orden=2,
        )
        result = get_variante_imagen(variante)
        self.assertEqual(result, _media_url("img/products/galeria/helper-variant-any.jpg"))
        self.assertTrue(isinstance(result, str) or result is None)

    def test_returns_product_principal_image_when_variant_has_no_images(self):
        producto = _create_product("Helper Product Principal")
        variante = _create_variant(producto, _create_color("Amarillo", "#FFFF00"))
        _attach_image(
            producto,
            path="img/products/galeria/helper-product-principal.jpg",
            es_principal=True,
        )
        result = get_variante_imagen(variante)
        self.assertEqual(result, _media_url("img/products/galeria/helper-product-principal.jpg"))
        self.assertTrue(isinstance(result, str) or result is None)

    def test_returns_product_default_image_when_no_gallery_images_exist(self):
        producto = _create_product("Helper Default", imagen="img/products/helper-default.jpg")
        variante = _create_variant(producto, _create_color("Blanco", "#FFFFFF"))
        result = get_variante_imagen(variante)
        self.assertEqual(result, _media_url("img/products/helper-default.jpg"))
        self.assertTrue(isinstance(result, str) or result is None)

    def test_returns_none_when_no_image_exists_anywhere(self):
        producto = _create_product("Helper None", imagen="")
        variante = _create_variant(producto, _create_color("Gris", "#AAAAAA"))
        result = get_variante_imagen(variante)
        self.assertIsNone(result)
        self.assertTrue(isinstance(result, str) or result is None)

class VarianteOrderingTest(ImageStorageTestCase):
    def test_producto_detalle_serializer_uses_color_name_ordering(self):
        producto = _create_product("Detalle")
        color_z = _create_color("Zafiro", "#123456")
        color_a = _create_color("Ambar", "#654321")
        _create_variant(producto, color_z)
        _create_variant(producto, color_a)
        data = ProductoDetalleSerializer(producto).data
        self.assertEqual([item["color"]["nombre"] for item in data["variantes"]], ["Ambar", "Zafiro"])

    def test_producto_variantes_endpoint_uses_model_default_ordering(self):
        client = APIClient()
        producto = _create_product("Listado")
        color_z = _create_color("Turquesa", "#40E0D0")
        color_a = _create_color("Arena", "#C2B280")
        _create_variant(producto, color_z)
        _create_variant(producto, color_a)
        response = client.get(f"/api/producto-variantes/?producto={producto.id}")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["color"]["nombre"] for item in response.data["results"]], ["Arena", "Turquesa"])

    def test_worker_variants_endpoint_uses_model_default_ordering(self):
        client = APIClient()
        worker = _create_user("worker-order@test.com", staff=True)
        client.force_authenticate(user=worker)
        producto_z = _create_product("Zeta")
        producto_a = _create_product("Alfa")
        color_azul = _create_color("Azul", "#0000AA")
        color_rojo = _create_color("Rojo", "#AA0000")
        variante_azul = _create_variant(producto_z, color_azul)
        variante_rojo = _create_variant(producto_a, color_rojo)
        response = client.get("/api/worker/variants/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["variant_id"] for item in response.data], [variante_azul.id, variante_rojo.id])


def _build_worker_variant_dataset(n: int, color_offset: int = 0):
    """
    Create N variants with mixed image scenarios covering all four fallback branches:
      - Variant with principal image (step 1)
      - Variant with any image but no principal (step 2)
      - Variant with no images but product has principal image (step 3)
      - Variant with no images and product has no gallery images (step 4 / default)
    """
    colors = []
    variants = []
    hex_digits = "0123456789ABCDEF"

    for i in range(n):
        # Generate a unique hex color.
        offset = color_offset + i
        r = (offset * 37 + 10) % 256
        g = (offset * 59 + 80) % 256
        b = (offset * 83 + 150) % 256
        hex_val = f"#{r:02X}{g:02X}{b:02X}"
        color = _create_color(f"Color-{color_offset}-{i}", hex_val)
        colors.append(color)

    for i, color in enumerate(colors):
        branch = i % 4  # 0=step1, 1=step2, 2=step3, 3=step4
        product_imagen = f"img/products/p{color_offset}-{i}-default.jpg"
        producto = _create_product(f"Prod-{color_offset}-{i}", imagen=product_imagen)
        variante = _create_variant(producto, color)

        if branch == 0:
            # Step 1: variant has a principal image.
            _attach_image(
                producto,
                variante=variante,
                path=f"img/products/galeria/v-principal-{color_offset}-{i}.jpg",
                es_principal=True,
                orden=0,
            )
        elif branch == 1:
            # Step 2: variant has an image but not principal.
            _attach_image(
                producto,
                variante=variante,
                path=f"img/products/galeria/v-any-{color_offset}-{i}.jpg",
                es_principal=False,
                orden=1,
            )
        elif branch == 2:
            # Step 3: no variant image; product has a principal image.
            _attach_image(
                producto,
                path=f"img/products/galeria/p-principal-{color_offset}-{i}.jpg",
                es_principal=True,
                orden=0,
            )
        # branch == 3: step 4 — no gallery images, only producto.imagen field.

        variants.append(variante)

    return variants


class WorkerVariantListQueryCountTest(ImageStorageTestCase):
    """
    Invariant: the total SQL query count for GET /api/worker/variants/ MUST be
    constant regardless of the number of variants returned.

    RED expectation: before the double-Prefetch is wired in WorkerVariantListView,
    the query count grows linearly with N (N+1 problem), so the counts for
    N=1, N=5, and N=20 will differ and the assertion will FAIL.
    """

    def setUp(self):
        super().setUp()
        self.worker = _create_user("worker-qcount@test.com", staff=True)

    def _get_query_count(self, client: APIClient) -> int:
        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/api/worker/variants/")
        self.assertEqual(response.status_code, 200, response.data)
        return len(ctx)

    def test_query_count_is_constant_for_n_equals_1_5_and_20(self):
        """Core invariant: count(N=1) == count(N=5) == count(N=20)."""
        client = APIClient()
        client.force_authenticate(user=self.worker)

        _build_worker_variant_dataset(1, color_offset=100)
        count_1 = self._get_query_count(client)

        _build_worker_variant_dataset(4, color_offset=200)
        count_5 = self._get_query_count(client)

        # Add 15 more to reach 20 total (cumulative DB state within the same test).
        _build_worker_variant_dataset(15, color_offset=300)
        count_20 = self._get_query_count(client)

        self.assertEqual(
            count_1,
            count_5,
            msg=(
                f"N+1 detected: query count changed from {count_1} (N=1) to "
                f"{count_5} (N=5). WorkerVariantListView must keep the count constant."
            ),
        )
        self.assertEqual(
            count_5,
            count_20,
            msg=(
                f"N+1 detected: query count changed from {count_5} (N=5) to "
                f"{count_20} (N=20). WorkerVariantListView must keep the count constant."
            ),
        )


class WorkerVariantListResponseContractTest(ImageStorageTestCase):
    def setUp(self):
        super().setUp()
        self.worker = _create_user("worker-contract@test.com", staff=True)

    def test_response_shape_and_imagen_principal_contract_remain_unchanged(self):
        client = APIClient()
        client.force_authenticate(user=self.worker)

        color_a = _create_color("Contract-A", "#AA0001")
        color_b = _create_color("Contract-B", "#AA0002")
        color_c = _create_color("Contract-C", "#AA0003")
        color_d = _create_color("Contract-D", "#AA0004")
        color_e = _create_color("Contract-E", "#AA0005")

        variant_principal_product = _create_product("Contract Variant Principal")
        variant_principal = _create_variant(variant_principal_product, color_a)
        _attach_image(
            variant_principal_product,
            variante=variant_principal,
            path="img/products/galeria/contract-variant-principal.jpg",
            es_principal=True,
            orden=0,
        )

        variant_any_product = _create_product("Contract Variant Any")
        variant_any = _create_variant(variant_any_product, color_b)
        _attach_image(
            variant_any_product,
            variante=variant_any,
            path="img/products/galeria/contract-variant-any.jpg",
            orden=1,
        )

        product_principal_product = _create_product("Contract Product Principal")
        product_principal = _create_variant(product_principal_product, color_c)
        _attach_image(
            product_principal_product,
            path="img/products/galeria/contract-product-principal.jpg",
            es_principal=True,
            orden=0,
        )

        product_default = _create_variant(
            _create_product("Contract Product Default", imagen="img/products/contract-default.jpg"),
            color_d,
        )
        no_image = _create_variant(_create_product("Contract None", imagen=""), color_e)

        variants = [
            variant_principal,
            variant_any,
            product_principal,
            product_default,
            no_image,
        ]

        response = client.get("/api/worker/variants/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), len(variants))

        expected_fields = set(WorkerVariantApiSerializer.Meta.fields)
        expected_by_id = {
            variant.id: WorkerVariantApiSerializer(variant).data
            for variant in variants
        }
        actual_by_id = {
            item["variant_id"]: item
            for item in response.data
        }

        self.assertEqual(set(actual_by_id), set(expected_by_id))

        for variant_id, expected_item in expected_by_id.items():
            actual_item = actual_by_id[variant_id]
            self.assertEqual(set(actual_item.keys()), expected_fields)
            self.assertEqual(actual_item, expected_item)
            self.assertTrue(
                isinstance(actual_item["imagen_principal"], str)
                or actual_item["imagen_principal"] is None
            )

        imagenes = [item["imagen_principal"] for item in response.data]
        self.assertIn(None, imagenes)
        self.assertIn(_media_url("img/products/contract-default.jpg"), imagenes)


class VarianteImageHelperCacheBranchTest(ImageStorageTestCase):
    """
    Unit tests for the prefetch-cache code path in get_variante_imagen().

    These tests verify that setting variante.producto._cached_prod_imagenes
    eliminates the step-3 DB query. They measure the query count with and
    without the cache attribute on the SAME variant object (no fresh fetch
    needed — step 3 is stateless across calls when no variant images exist).

    RED expectation: before the hasattr-gated branch exists in imagenes.py,
    setting _cached_prod_imagenes has no effect — step 3 always queries,
    so count_with == count_without. The assertEqual(count_without - 1, count_with)
    assertion will FAIL.
    """

    def setUp(self):
        super().setUp()
        producto = _create_product("Cache Branch Prod", imagen="img/products/cache-default.jpg")
        self.variante = _create_variant(producto, _create_color("CacheColor", "#CACACA"))
        self.producto = producto

    def _baseline_query_count(self) -> int:
        """Return query count for a normal call (no cache attribute set)."""
        # Ensure no cache attribute leaks from a previous run.
        if hasattr(self.producto, "_cached_prod_imagenes"):
            del self.producto._cached_prod_imagenes
        with CaptureQueriesContext(connection) as ctx:
            get_variante_imagen(self.variante)
        return len(ctx)

    def test_step3_reads_from_prefetch_cache_attribute(self):
        """
        When variante.producto._cached_prod_imagenes is populated with a
        principal image, get_variante_imagen() must skip the step-3 DB query.

        Proof: query count WITH cache set is exactly 1 less than baseline.
        The saved query is the step-3 'product principal image' lookup.
        """
        count_without = self._baseline_query_count()

        cached_img = ProductosImagenesModel(
            producto=self.producto,
            variante=None,
            imagen="img/products/galeria/cached-principal.jpg",
            es_principal=True,
            orden=0,
        )
        _create_media_file("img/products/galeria/cached-principal.jpg")
        self.producto._cached_prod_imagenes = [cached_img]

        with CaptureQueriesContext(connection) as ctx_with:
            result = get_variante_imagen(self.variante)
        count_with = len(ctx_with)

        self.assertEqual(
            count_without - 1,
            count_with,
            msg=(
                f"Expected cache to save exactly 1 query (step 3). "
                f"Without cache: {count_without}, with cache: {count_with}."
            ),
        )
        self.assertEqual(result, _media_url("img/products/galeria/cached-principal.jpg"))

    def test_step3_cache_populated_but_empty_falls_through_to_step4(self):
        """
        When _cached_prod_imagenes is an empty list (no product-level principal
        image), get_variante_imagen() must fall through to step 4 WITHOUT
        issuing a step-3 DB query.

        Proof: query count WITH empty cache is exactly 1 less than baseline.
        """
        count_without = self._baseline_query_count()

        self.producto._cached_prod_imagenes = []

        with CaptureQueriesContext(connection) as ctx_with:
            result = get_variante_imagen(self.variante)
        count_with = len(ctx_with)

        self.assertEqual(
            count_without - 1,
            count_with,
            msg=(
                f"Expected empty cache to save exactly 1 query (step 3). "
                f"Without cache: {count_without}, with cache: {count_with}."
            ),
        )
        # Falls through to step 4: producto.imagen field.
        self.assertEqual(result, _media_url("img/products/cache-default.jpg"))
