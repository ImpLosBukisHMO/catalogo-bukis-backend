from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.exceptions import ValidationError
from django.db.models import Prefetch, Q, Sum

from api.models import ProductoVariantesModel, ProductosImagenesModel, ProductosModel
from api.pagination import PublicCatalogPagination
from api.serializers import ProductosSerializer, ProductoDetalleSerializer


def _with_public_image_prefetch(queryset):
    return queryset.select_related(
        "categoria__descuento_general",
        "descuento_especial",
    ).prefetch_related(
        Prefetch(
            "producto_colores",
            queryset=(
                ProductoVariantesModel.objects.filter(activo=True)
                .select_related("producto")
                .prefetch_related(
                    Prefetch(
                        "imagenes",
                        queryset=ProductosImagenesModel.objects.order_by("orden", "id"),
                        to_attr="_cached_variante_imagenes",
                    )
                )
                .order_by("color__nombre", "id")
            ),
            to_attr="_cached_display_variantes",
        ),
        Prefetch(
            "imagenes",
            queryset=(
                ProductosImagenesModel.objects.filter(variante__isnull=True)
                .order_by("orden", "id")
            ),
            to_attr="_cached_prod_imagenes",
        ),
    )


class ProductosListCreate(generics.ListCreateAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = PublicCatalogPagination
    http_method_names = ["get", "head", "options"]

    def _parse_int(self, value, field_name):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError({field_name: "Debe ser un entero."})

    def _parse_bool(self, value, field_name):
        if value is None:
            return None
        v = str(value).strip().lower()
        if v == "":
            return None
        if v in ("true", "1", "t", "yes", "y", "si", "sí"):
            return True
        if v in ("false", "0", "f", "no", "n"):
            return False
        raise ValidationError({field_name: "Debe ser booleano (true/false)."})

    def get_queryset(self):
        qs = _with_public_image_prefetch(
            ProductosModel.objects
            .filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            )
            .order_by("-id")
        )

        categoria_id = self.request.query_params.get("categoria_id")
        if categoria_id is not None and str(categoria_id).strip() != "":
            categoria_id_int = self._parse_int(categoria_id, "categoria_id")
            qs = qs.filter(categoria_id=categoria_id_int)

        item = self.request.query_params.get("item")
        if item:
            qs = qs.filter(producto_colores__item=item)

        color = self.request.query_params.get("color")
        color_id = None
        if color is not None and str(color).strip() != "":
            color_id = self._parse_int(color, "color")
            qs = qs.filter(producto_colores__color_id=color_id)

        disponible = self._parse_bool(self.request.query_params.get("disponible"), "disponible")

        # Definición de "variante disponible"
        # activo True y stock > 0
        if disponible is True:
            qs = qs.filter(
                producto_colores__activo=True,
                producto_colores__stock__gt=0,
            )

        elif disponible is False:
            if color_id is not None:
                # Con color: traemos productos que tienen ese color
                # pero esa variante NO está disponible
                qs = qs.exclude(
                    producto_colores__color_id=color_id,
                    producto_colores__activo=True,
                    producto_colores__stock__gt=0,
                )
            else:
                # Sin color: productos que NO tienen ninguna variante disponible
                # (incluye productos sin variantes)
                qs = qs.exclude(
                    producto_colores__activo=True,
                    producto_colores__stock__gt=0,
                )

        return qs.distinct()


class ProductosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "id"
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            )
        )

    def get_serializer_class(self):
        return ProductoDetalleSerializer


from rest_framework.views import APIView
from rest_framework.response import Response

class ProductosNovedadesList(generics.ListAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            ).order_by("-created_at")[:10]
        )


class ProductosMasVistosList(generics.ListAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            ).order_by("-vistas")[:10]
        )


class ProductosMenosVistosList(generics.ListAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            ).order_by("vistas")[:10]
        )


class ProductosMasVendidosList(generics.ListAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        # Annotate each product with the sum of quantities from related order items
        # where the order is not canceled.
        from api.models import PedidosModel
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            ).annotate(
                total_vendidos=Sum('producto_colores__pedido_items__cantidad', filter=~Q(producto_colores__pedido_items__pedido__estado=PedidosModel.EstadoPedido.CANCELADO))
            ).order_by("-total_vendidos")[:10]
        )


class ProductosMenosVendidosList(generics.ListAPIView):
    serializer_class = ProductosSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        # Annotate each product with the sum of quantities from related order items
        # where the order is not canceled.
        from api.models import PedidosModel
        return _with_public_image_prefetch(
            ProductosModel.objects.filter(
                disponible=True,
                estado=ProductosModel.EstadoProducto.ACTIVE,
            ).annotate(
                total_vendidos=Sum('producto_colores__pedido_items__cantidad', filter=~Q(producto_colores__pedido_items__pedido__estado=PedidosModel.EstadoPedido.CANCELADO))
            ).order_by("total_vendidos")[:10]
        )


class ReportarVistaProducto(APIView):
    permission_classes = [AllowAny]

    def post(self, request, id):
        try:
            producto = ProductosModel.objects.get(id=id)
            producto.vistas += 1
            producto.save(update_fields=['vistas'])
            return Response({"message": "Vista registrada."})
        except ProductosModel.DoesNotExist:
            return Response({"error": "Producto no encontrado."}, status=404)
