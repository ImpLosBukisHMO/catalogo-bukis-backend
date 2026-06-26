from django.db import transaction
from django.db.models import F
import uuid

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from api.models import (
    CarritoModel,
    CarritoItemModel,
    ProductoVariantesModel,
    PedidosModel,
    PedidoProductosModel,
)
from api.serializers import (
    CarritoReadSerializer,
    CarritoItemCreateSerializer,
    CarritoItemUpdateSerializer,
)
from api.utils.imagenes import get_variante_imagen


def _get_or_create_active_cart(user):
    # Nota: usa el valor real del choice si tu modelo lo define como "ACTIVE"
    cart, _ = CarritoModel.objects.get_or_create(
        cliente=user,
        estado="ACTIVE",
        defaults={},
    )
    return cart


def _is_public_product_variant(variante):
    producto = variante.producto
    return (
        variante.activo
        and producto.estado == producto.EstadoProducto.ACTIVE
        and producto.disponible is True
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def carrito_actual(request):
    # Permitir "carrito de invitado" para que el front no truene sin sesión
    if request.user.is_anonymous:
        return Response(
            {"id": None, "items": [], "subtotal": 0, "estado": "GUEST"},
            status=status.HTTP_200_OK,
        )

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

    with transaction.atomic():
        try:
            variante = (
                ProductoVariantesModel.objects.select_related("producto", "color")
                .select_for_update()
                .get(id=variante_id, activo=True)
            )
        except ProductoVariantesModel.DoesNotExist:
            return Response(
                {"detail": "Variante no encontrada o inactiva."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _is_public_product_variant(variante):
            return Response(
                {"detail": "La variante no está disponible para la venta pública."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if variante.stock < cantidad:
            return Response(
                {"detail": "No hay stock suficiente para esa variante."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # upsert por uniq_carrito_variante
        item, created = CarritoItemModel.objects.get_or_create(
            carrito=cart,
            variante=variante,
            defaults={"cantidad": cantidad},
        )
        if not created:
            nueva = item.cantidad + cantidad
            if variante.stock < nueva:
                return Response(
                    {"detail": "No hay stock suficiente para incrementar esa cantidad."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.cantidad = nueva
            item.save(update_fields=["cantidad", "updated_at"])

    return Response({"ok": True, "item_id": item.id}, status=status.HTTP_200_OK)


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

    try:
        item = (
            CarritoItemModel.objects.select_related("variante__producto")
            .get(id=item_id, carrito=cart)
        )
    except CarritoItemModel.DoesNotExist:
        return Response({"detail": "Item no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if item.variante.stock < cantidad:
        return Response(
            {"detail": "No hay stock suficiente para esa variante."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    item.cantidad = cantidad
    item.save(update_fields=["cantidad", "updated_at"])
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def carrito_checkout(request):
    """
    Crea PedidosModel + PedidoProductosModel con snapshots.
    Marca carrito como CONVERTIDO y limpia items.
    """
    cart = _get_or_create_active_cart(request.user)

    items = (
        CarritoItemModel.objects.select_related("variante__producto", "variante__color")
        .filter(carrito=cart)
        .order_by("id")
    )

    if not items.exists():
        return Response({"detail": "El carrito está vacío."}, status=status.HTTP_400_BAD_REQUEST)

    nota_cliente = request.data.get("nota_cliente")
    direccion_id = request.data.get("direccion_id")  # opcional

    with transaction.atomic():
        # Phase 1: Acquire row-level locks on all variants and validate stock.
        # Locks are held until the transaction commits/rolls back, preventing
        # concurrent checkouts on the same rows from interleaving the check+decrement.
        variant_ids = [it.variante_id for it in items]
        locked_variants = {
            v.pk: v
            for v in ProductoVariantesModel.objects.select_related("producto", "color")
            .select_for_update()
            .filter(pk__in=variant_ids)
        }

        for it in items:
            v = locked_variants.get(it.variante_id)
            if v is None:
                return Response(
                    {"detail": "Una variante del carrito ya no existe."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not _is_public_product_variant(v):
                return Response(
                    {"detail": f"La variante {v.id} ya no está disponible para la venta pública."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if v.stock < it.cantidad:
                return Response(
                    {"detail": f"Stock insuficiente para la variante {v.id}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Phase 2: All stock checks passed — create the order and decrement stock.
        pedido = PedidosModel.objects.create(
            cliente=request.user,
            clave=str(uuid.uuid4()),
            public_id=uuid.uuid4(),
            estado="PENDING",
            direccion_id=direccion_id,
            nota_cliente=nota_cliente,
            subtotal_snapshot=0,
            precio_total=0,
        )

        subtotal = 0

        for it in items:
            v = locked_variants[it.variante_id]
            p = v.producto
            c = v.color

            precio_unit = v.precio_efectivo
            subtotal_linea = precio_unit * it.cantidad

            imagen_snapshot = get_variante_imagen(v)

            PedidoProductosModel.objects.create(
                pedido=pedido,
                variante=v,
                cantidad=it.cantidad,
                producto_nombre_snapshot=p.nombre,
                producto_item_snapshot=v.item,
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

            # Atomic decrement using F() expression — avoids reading a stale
            # Python value back and keeps the decrement inside the locked row.
            ProductoVariantesModel.objects.filter(pk=v.pk).update(
                stock=F("stock") - it.cantidad
            )

        pedido.subtotal_snapshot = subtotal
        pedido.precio_total = subtotal
        pedido.save(update_fields=["subtotal_snapshot", "precio_total", "updated_at"])

        # cerrar carrito
        cart.estado = "CONVERTED"  # ojo: debe coincidir con tu TextChoices
        cart.save(update_fields=["estado", "updated_at"])
        items.delete()

    return Response(
        {"ok": True, "pedido_id": pedido.id, "public_id": str(pedido.public_id)},
        status=status.HTTP_201_CREATED,
    )
