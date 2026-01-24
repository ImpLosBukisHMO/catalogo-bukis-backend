from django.db import transaction
from django.utils import timezone
import uuid

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from api.models import (
    CarritoModel, CarritoItemModel,
    ProductoVariantesModel, ProductosImagenesModel,
    PedidosModel, PedidoProductosModel
)
from api.serializers import (
    CarritoReadSerializer,
    CarritoItemCreateSerializer,
    CarritoItemUpdateSerializer,
)

def _get_or_create_active_cart(user):
    cart, _ = CarritoModel.objects.get_or_create(
        cliente=user,
        estado="ACTIVE",
        defaults={}
    )
    return cart

@api_view(["GET"])
@permission_classes([AllowAny])
def carrito_actual(request):
    if request.user.is_anonymous:
        return Response({"id": None, "items": [], "subtotal": 0, "estado": "GUEST"}, status=status.HTTP_200_OK)

    cart = _get_or_create_active_cart(request.user)
    data = CarritoReadSerializer(cart).data
    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def carrito_add_item(request):
    s = CarritoItemCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    variante_id = s.validated_data["variante_id"]
    cantidad = s.validated_data["cantidad"]

    cart = _get_or_create_active_cart(request.user)

    variante = (
        ProductoVariantesModel.objects
        .select_related("producto", "color")
        .get(id=variante_id, activo=True)
    )

    # opcional: validar stock
    if variante.stock < cantidad:
        return Response(
            {"detail": "No hay stock suficiente para esa variante."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # upsert por uniq_carrito_variante
    item, created = CarritoItemModel.objects.get_or_create(
        carrito=cart,
        variante=variante,
        defaults={"cantidad": cantidad}
    )
    if not created:
        item.cantidad = item.cantidad + cantidad
        item.save(update_fields=["cantidad", "updated_at"])

    return Response({"ok": True, "item_id": item.id}, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def carrito_update_item(request, item_id: int):
    s = CarritoItemUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    cantidad = s.validated_data["cantidad"]

    cart = _get_or_create_active_cart(request.user)
    item = (
        CarritoItemModel.objects
        .select_related("variante__producto")
        .get(id=item_id, carrito=cart)
    )

    # opcional: validar stock
    if item.variante.stock < cantidad:
        return Response(
            {"detail": "No hay stock suficiente para esa variante."},
            status=status.HTTP_400_BAD_REQUEST
        )

    item.cantidad = cantidad
    item.save(update_fields=["cantidad", "updated_at"])
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def carrito_delete_item(request, item_id: int):
    cart = _get_or_create_active_cart(request.user)
    CarritoItemModel.objects.filter(id=item_id, carrito=cart).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def carrito_checkout(request):
    """
    Crea PedidoModel + PedidoProductosModel con snapshots.
    Deja el carrito en CHECKED_OUT y crea uno nuevo ACTIVE automáticamente en la siguiente consulta.
    """
    cart = _get_or_create_active_cart(request.user)

    items = (
        CarritoItemModel.objects
        .select_related("variante__producto", "variante__color")
        .filter(carrito=cart)
        .order_by("id")
    )

    if not items.exists():
        return Response({"detail": "El carrito está vacío."}, status=status.HTTP_400_BAD_REQUEST)

    nota_cliente = request.data.get("nota_cliente")
    direccion_id = request.data.get("direccion_id")  # opcional

    with transaction.atomic():
        pedido = PedidosModel.objects.create(
            cliente=request.user,
            clave=str(uuid.uuid4()),           # luego si quieres lo hacemos más legible
            public_id=uuid.uuid4(),            # por ahora
            estado="PENDING",
            direccion_id=direccion_id,
            nota_cliente=nota_cliente,
            subtotal_snapshot=0,
            precio_total=0,
        )

        subtotal = 0

        for it in items:
            v = it.variante
            p = v.producto
            c = v.color

            precio_unit = p.precio
            subtotal_linea = precio_unit * it.cantidad

            # imagen principal snapshot
            img = (
                ProductosImagenesModel.objects
                .filter(variante=v, es_principal=True)
                .order_by("orden", "id")
                .first()
            )
            if not img:
                img = (
                    ProductosImagenesModel.objects
                    .filter(variante=v)
                    .order_by("orden", "id")
                    .first()
                )
            imagen_snapshot = ""
            if img:
                imagen_snapshot = img.imagen.url if hasattr(img.imagen, "url") else str(img.imagen)
            else:
                imagen_snapshot = p.imagen.url if hasattr(p.imagen, "url") else str(p.imagen)

            PedidoProductosModel.objects.create(
                pedido=pedido,
                variante=v,
                cantidad=it.cantidad,

                producto_nombre_snapshot=p.nombre,
                producto_item_snapshot=p.item,
                descripcion_snapshot=p.descripcion or "",

                color_nombre_snapshot=c.nombre,
                color_hex_snapshot=c.hex,

                precio_unitario_snapshot=precio_unit,
                subtotal_linea_snapshot=subtotal_linea,
                imagen_principal_snapshot=imagen_snapshot,

                # legacy (opcional)
                producto=p,
                color=c.nombre,
                precio_unitario_producto=precio_unit,
            )

            subtotal += subtotal_linea

            # opcional: descontar stock inmediatamente (si tu negocio lo requiere)
            v.stock = max(0, v.stock - it.cantidad)
            v.save(update_fields=["stock", "updated_at"])

        pedido.subtotal_snapshot = subtotal
        pedido.precio_total = subtotal
        pedido.save(update_fields=["subtotal_snapshot", "precio_total", "updated_at"])

        # cerrar carrito y limpiar items
        cart.estado = "CHECKED_OUT"
        cart.save(update_fields=["estado", "updated_at"])
        items.delete()

    return Response(
        {"ok": True, "pedido_id": pedido.id, "public_id": str(pedido.public_id)},
        status=status.HTTP_201_CREATED
    )

@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def carrito_item_detail(request, item_id: int):
    cart = _get_or_create_active_cart(request.user)

    if request.method == "DELETE":
        CarritoItemModel.objects.filter(id=item_id, carrito=cart).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    s = CarritoItemUpdateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    cantidad = s.validated_data["cantidad"]

    item = (
        CarritoItemModel.objects
        .select_related("variante__producto")
        .get(id=item_id, carrito=cart)
    )

    if item.variante.stock < cantidad:
        return Response(
            {"detail": "No hay stock suficiente para esa variante."},
            status=status.HTTP_400_BAD_REQUEST
        )

    item.cantidad = cantidad
    item.save(update_fields=["cantidad", "updated_at"])
    return Response({"ok": True}, status=status.HTTP_200_OK)
