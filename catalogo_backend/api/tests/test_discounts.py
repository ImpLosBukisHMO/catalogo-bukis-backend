"""
Tests de integración para la implementación de descuentos.

Cubre:
- ProductosModel.descuento_activo con/sin descuento especial y general.
- ProductoVariantesModel.precio_efectivo con descuento aplicado.
- Snapshot de descuento_porcentaje_snapshot en checkout.
- Exposición de descuentos en el serializer del worker.
"""
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import (
    CarritoItemModel,
    CarritoModel,
    CategoriasModel,
    ColorModel,
    DescuentosModel,
    PedidoProductosModel,
    ProductoVariantesModel,
    ProductosModel,
    UsuariosModel,
)
from api.serializer.worker import WorkerVariantSerializer


# =========================
# Helpers
# =========================

def _create_user(email: str, staff: bool = False) -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="Descuento",
        correo=email,
        telefono="555-0000000",
        password="testpass123",
        staff=staff,
    )


def _create_discount(
    nombre: str = "Descuento test",
    porcentaje: Decimal = Decimal("10.00"),
    activo: bool = True,
    tipo: str = DescuentosModel.DescuentoType.GENERAL,
    offset_days_start: int = -1,
    offset_days_end: int = 1,
) -> DescuentosModel:
    now = timezone.now()
    return DescuentosModel.objects.create(
        nombre=nombre,
        tipo=tipo,
        porcentaje=porcentaje,
        activo=activo,
        fecha_inicio=now + timedelta(days=offset_days_start),
        fecha_fin=now + timedelta(days=offset_days_end),
    )


def _create_category(nombre: str = "Cat descuento", descuento=None) -> CategoriasModel:
    return CategoriasModel.objects.create(nombre=nombre, descuento_general=descuento)


def _create_product(
    nombre: str,
    precio: Decimal = Decimal("100.00"),
    categoria=None,
    descuento_especial=None,
) -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=nombre,
        imagen="img/products/default.jpg",
        descripcion=f"{nombre} desc",
        precio=precio,
        peso="1.00",
        medidas="10x10x10",
        disponible=True,
        estado=ProductosModel.EstadoProducto.ACTIVE,
        categoria=categoria,
        descuento_especial=descuento_especial,
    )


def _create_color(nombre: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=nombre, hex=hex_value)


def _create_variant(
    producto: ProductosModel,
    color: ColorModel,
    stock: int = 5,
    precio=None,
) -> ProductoVariantesModel:
    kwargs = {"producto": producto, "color": color, "stock": stock, "activo": True}
    if precio is not None:
        kwargs["precio"] = precio
    return ProductoVariantesModel.objects.create(**kwargs)


# =========================
# Tests: ProductosModel.descuento_activo
# =========================

class DescuentoActivoPropertyTest(TestCase):
    """Verifica que descuento_activo devuelva el porcentaje correcto segun la jerarquia."""

    def test_descuento_activo_is_none_without_any_discount(self):
        producto = _create_product("Sin descuento")
        self.assertIsNone(producto.descuento_activo)

    def test_descuento_activo_is_none_when_categoria_is_none(self):
        """Un producto sin categoria no debe fallar: descuento_activo = None."""
        producto = _create_product("Sin categoria")
        producto.categoria = None
        producto.save(update_fields=["categoria"])
        self.assertIsNone(producto.descuento_activo)

    def test_descuento_activo_returns_especial_porcentaje(self):
        descuento = _create_discount(
            nombre="Especial 20%",
            porcentaje=Decimal("20.00"),
            tipo=DescuentosModel.DescuentoType.ESPECIAL,
        )
        producto = _create_product("Con especial", descuento_especial=descuento)
        self.assertEqual(producto.descuento_activo, Decimal("20.00"))

    def test_descuento_activo_returns_general_porcentaje_via_categoria(self):
        descuento = _create_discount(nombre="General cat 15%", porcentaje=Decimal("15.00"))
        categoria = _create_category(descuento=descuento)
        producto = _create_product("Con cat descuento", categoria=categoria)
        self.assertEqual(producto.descuento_activo, Decimal("15.00"))

    def test_descuento_activo_especial_takes_priority_over_general(self):
        especial = _create_discount(
            nombre="Especial prio 30%",
            porcentaje=Decimal("30.00"),
            tipo=DescuentosModel.DescuentoType.ESPECIAL,
        )
        general = _create_discount(nombre="General 10%", porcentaje=Decimal("10.00"))
        categoria = _create_category(descuento=general)
        producto = _create_product("Prio especial", categoria=categoria, descuento_especial=especial)
        self.assertEqual(producto.descuento_activo, Decimal("30.00"))

    def test_descuento_activo_is_none_when_discount_is_inactive(self):
        descuento = _create_discount(nombre="Inactivo", porcentaje=Decimal("20.00"), activo=False)
        producto = _create_product("Inactivo descuento", descuento_especial=descuento)
        self.assertIsNone(producto.descuento_activo)

    def test_descuento_activo_is_none_when_discount_is_expired(self):
        now = timezone.now()
        descuento = DescuentosModel.objects.create(
            nombre="Expirado",
            porcentaje=Decimal("25.00"),
            activo=True,
            tipo=DescuentosModel.DescuentoType.ESPECIAL,
            fecha_inicio=now - timedelta(days=10),
            fecha_fin=now - timedelta(days=1),
        )
        producto = _create_product("Expirado descuento", descuento_especial=descuento)
        self.assertIsNone(producto.descuento_activo)


# =========================
# Tests: precio_efectivo con descuentos
# =========================

class PrecioEfectivoConDescuentoTest(TestCase):

    def test_precio_efectivo_sin_descuento(self):
        producto = _create_product("Base price", precio=Decimal("200.00"))
        variante = _create_variant(producto, _create_color("Rojo D", "#FF0001"))
        self.assertEqual(variante.precio_efectivo, Decimal("200.00"))

    def test_precio_efectivo_con_descuento_especial(self):
        """10% especial sobre precio base de 200 -> 180."""
        descuento = _create_discount(nombre="E 10%", porcentaje=Decimal("10.00"), tipo=DescuentosModel.DescuentoType.ESPECIAL)
        producto = _create_product("Especial price", precio=Decimal("200.00"), descuento_especial=descuento)
        variante = _create_variant(producto, _create_color("Azul D", "#0000F1"))
        self.assertEqual(variante.precio_efectivo, Decimal("180.00"))

    def test_precio_efectivo_con_descuento_general_de_categoria(self):
        """15% general sobre precio base de 200 -> 170."""
        descuento = _create_discount(nombre="G 15%", porcentaje=Decimal("15.00"))
        categoria = _create_category(descuento=descuento)
        producto = _create_product("General price", precio=Decimal("200.00"), categoria=categoria)
        variante = _create_variant(producto, _create_color("Verde D", "#00F001"))
        self.assertEqual(variante.precio_efectivo, Decimal("170.00"))

    def test_precio_efectivo_con_override_y_descuento(self):
        """20% especial sobre precio override de 150 -> 120."""
        descuento = _create_discount(nombre="E 20%", porcentaje=Decimal("20.00"), tipo=DescuentosModel.DescuentoType.ESPECIAL)
        producto = _create_product("Override price", precio=Decimal("200.00"), descuento_especial=descuento)
        variante = _create_variant(
            producto,
            _create_color("Negro D", "#000001"),
            precio=Decimal("150.00"),
        )
        self.assertEqual(variante.precio_efectivo, Decimal("120.00"))


# =========================
# Tests: Snapshot en checkout
# =========================

class CheckoutDiscountSnapshotTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = _create_user("checkout-discount@test.com")
        self.client.force_authenticate(user=self.user)

    def test_checkout_snapshot_sin_descuento(self):
        producto = _create_product("Checkout sin descuento", precio=Decimal("100.00"))
        variante = _create_variant(producto, _create_color("Rojo snap", "#FF1001"), stock=5)
        carrito = CarritoModel.objects.create(cliente=self.user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=1)

        response = self.client.post("/api/carrito/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.descuento_porcentaje_snapshot, Decimal("0"))
        self.assertEqual(snapshot.precio_unitario_snapshot, Decimal("100.00"))

    def test_checkout_snapshot_con_descuento_especial(self):
        """Un 25% de descuento especial debe quedar en descuento_porcentaje_snapshot."""
        descuento = _create_discount(
            nombre="E 25% snap",
            porcentaje=Decimal("25.00"),
            tipo=DescuentosModel.DescuentoType.ESPECIAL,
        )
        producto = _create_product("Checkout especial snap", precio=Decimal("200.00"), descuento_especial=descuento)
        variante = _create_variant(producto, _create_color("Azul snap", "#0011FF"), stock=5)
        carrito = CarritoModel.objects.create(cliente=self.user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=2)

        response = self.client.post("/api/carrito/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.descuento_porcentaje_snapshot, Decimal("25.00"))
        self.assertEqual(snapshot.precio_unitario_snapshot, Decimal("150.00"))
        self.assertEqual(snapshot.subtotal_linea_snapshot, Decimal("300.00"))

    def test_checkout_snapshot_con_descuento_general_de_categoria(self):
        """Un 10% de descuento general de categoria debe quedar en el snapshot."""
        descuento = _create_discount(nombre="G 10% snap", porcentaje=Decimal("10.00"))
        categoria = _create_category(descuento=descuento)
        producto = _create_product("Checkout cat snap", precio=Decimal("100.00"), categoria=categoria)
        variante = _create_variant(producto, _create_color("Verde snap", "#00FF01"), stock=5)
        carrito = CarritoModel.objects.create(cliente=self.user, estado="ACTIVE")
        CarritoItemModel.objects.create(carrito=carrito, variante=variante, cantidad=3)

        response = self.client.post("/api/carrito/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        snapshot = PedidoProductosModel.objects.get(pedido_id=response.data["pedido_id"])
        self.assertEqual(snapshot.descuento_porcentaje_snapshot, Decimal("10.00"))
        self.assertEqual(snapshot.precio_unitario_snapshot, Decimal("90.00"))
        self.assertEqual(snapshot.subtotal_linea_snapshot, Decimal("270.00"))


# =========================
# Tests: Exposicion en serializer del worker
# =========================

class WorkerVariantSerializerDiscountExposureTest(TestCase):

    def test_serializer_expone_descuento_especial(self):
        descuento = _create_discount(
            nombre="Especial serializer",
            porcentaje=Decimal("20.00"),
            tipo=DescuentosModel.DescuentoType.ESPECIAL,
        )
        producto = _create_product("Serializer especial", precio=Decimal("100.00"), descuento_especial=descuento)
        variante = _create_variant(producto, _create_color("Rojo ser", "#FF2001"))

        data = WorkerVariantSerializer(variante).data

        self.assertIsNotNone(data["producto"]["descuento_especial"])
        self.assertEqual(data["producto"]["descuento_especial"]["porcentaje"], 20.0)
        self.assertTrue(data["producto"]["descuento_especial"]["es_valido"])
        # El precio efectivo refleja el descuento; se compara como Decimal
        # para tolerar la precision interna (ej. "80.0000" vs "80.00").
        self.assertEqual(Decimal(data["producto"]["precio"]), Decimal("80.00"))

    def test_serializer_expone_descuento_de_categoria(self):
        descuento = _create_discount(nombre="Cat serializer 15%", porcentaje=Decimal("15.00"))
        categoria = _create_category(descuento=descuento)
        producto = _create_product("Serializer cat", precio=Decimal("100.00"), categoria=categoria)
        variante = _create_variant(producto, _create_color("Azul ser", "#0020FF"))

        data = WorkerVariantSerializer(variante).data

        self.assertIsNotNone(data["producto"]["categoria"])
        self.assertIsNotNone(data["producto"]["categoria"]["descuento"])
        self.assertEqual(data["producto"]["categoria"]["descuento"]["porcentaje"], 15.0)
        self.assertEqual(Decimal(data["producto"]["precio"]), Decimal("85.00"))

    def test_serializer_sin_descuento_expone_nulos(self):
        producto = _create_product("Sin desc serializer", precio=Decimal("100.00"))
        variante = _create_variant(producto, _create_color("Blanco ser", "#FFFFF1"))

        data = WorkerVariantSerializer(variante).data

        self.assertIsNone(data["producto"]["descuento_especial"])
        self.assertIsNone(data["producto"]["categoria"])
        self.assertEqual(data["producto"]["precio"], "100.00")
