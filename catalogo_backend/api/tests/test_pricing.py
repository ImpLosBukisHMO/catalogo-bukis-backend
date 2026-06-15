from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import (
    CarritoItemModel,
    CarritoModel,
    ColorModel,
    PedidoProductosModel,
    ProductoVariantesModel,
    ProductosModel,
    UsuariosModel,
)
from api.serializer.worker import WorkerVariantSerializer as WorkerVariantApiSerializer
from api.serializers import (
    CarritoItemReadSerializer,
    CarritoReadSerializer,
    FavoritoVarianteSerializer,
)

def _create_user(email: str, staff: bool = False) -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="555-1234567",
        password="testpass123",
        staff=staff,
    )

def _create_product(
    nombre: str,
    precio: Decimal = Decimal("100.00"),
    imagen: str = "img/products/default.jpg",
) -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen=imagen,
        descripcion=f"{nombre} desc",
        precio=precio,
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
    )

def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)

def _create_variant(
    producto: ProductosModel,
    color: ColorModel,
    stock: int = 5,
    precio=None,
) -> ProductoVariantesModel:
    payload = {
        "producto": producto,
        "color": color,
        "stock": stock,
        "activo": True,
    }
    if precio is not None:
        payload["precio"] = precio
    return ProductoVariantesModel.objects.create(**payload)

class VariantPriceCurrentBehaviorTest(TestCase):
    def test_favorito_serializer_precio_is_product_price(self):
        producto = _create_product("Favorito Price", precio=Decimal("250.00"))
        variante = _create_variant(producto, _create_color("Rojo", "#FF0000"))
        data = FavoritoVarianteSerializer(variante).data
        self.assertEqual(data["precio"], "250.00")

    def test_carrito_item_serializer_precio_unitario_is_product_price(self):
        user = _create_user("cart-price@test.com")
        producto = _create_product("Cart Price", precio=Decimal("150.00"))
        variante = _create_variant(producto, _create_color("Azul", "#0000FF"))
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        item = CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=2)
        data = CarritoItemReadSerializer(item).data
        self.assertEqual(data["precio_unitario"], "150.00")

    def test_carrito_item_serializer_subtotal_linea_uses_product_price(self):
        user = _create_user("cart-subtotal@test.com")
        producto = _create_product("Cart Subtotal", precio=Decimal("75.00"))
        variante = _create_variant(producto, _create_color("Verde", "#00FF00"))
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        item = CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=3)
        data = CarritoItemReadSerializer(item).data
        self.assertEqual(Decimal(data["subtotal_linea"]), Decimal("225.00"))

    def test_carrito_read_serializer_subtotal_uses_product_price(self):
        user = _create_user("cart-total@test.com")
        producto = _create_product("Cart Total", precio=Decimal("200.00"))
        variante = _create_variant(producto, _create_color("Negro", "#000000"))
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=2)
        data = CarritoReadSerializer(carrito).data
        self.assertEqual(Decimal(data["subtotal"]), Decimal("400.00"))

    def test_worker_variant_serializer_precio_is_product_price(self):
        producto = _create_product("Worker Price", precio=Decimal("300.00"))
        variante = _create_variant(producto, _create_color("Blanco", "#FFFFFF"))
        data = WorkerVariantApiSerializer(variante).data
        self.assertEqual(data["producto"]["precio"], "300.00")

    def test_checkout_snapshot_precio_unitario_is_product_price(self):
        client = APIClient()
        user = _create_user("checkout-price@test.com")
        client.force_authenticate(user=user)
        producto = _create_product("Checkout Price", precio=Decimal("175.00"))
        variante = _create_variant(producto, _create_color("Gris", "#AAAAAA"), stock=5)
        carrito = CarritoModel.objects.create(cliente=user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=2)
        response = client.post("/api/carrito/checkout/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.precio_unitario_snapshot, Decimal("175.00"))
