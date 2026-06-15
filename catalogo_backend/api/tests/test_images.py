from django.conf import settings
from django.test import TestCase

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
)
from api.utils.imagenes import get_variante_imagen

def _media_url(path: str) -> str:
    return f"{settings.MEDIA_URL}{path}"

def _create_user(email: str, staff: bool = False) -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="555-1234567",
        password="testpass123",
        staff=staff,
    )

def _create_product(nombre: str, imagen: str = "img/products/default.jpg") -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen=imagen,
        descripcion=f"{nombre} desc",
        precio="100.00",
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
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
) -> ProductosImagenesModel:
    return ProductosImagenesModel.objects.create(
        producto=producto,
        variante=variante,
        imagen=path,
        es_principal=es_principal,
        orden=orden,
    )

class ImageConsumerCurrentBehaviorTest(TestCase):
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

class VarianteImageHelperTest(TestCase):
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

class VarianteOrderingTest(TestCase):
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
        self.assertEqual([item["color"]["nombre"] for item in response.data], ["Arena", "Turquesa"])

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
