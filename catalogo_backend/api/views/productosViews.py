from rest_framework import generics
from rest_framework.exceptions import ValidationError
from api.models import ProductosModel
from api.serializers import ProductosSerializer, ProductoDetalleSerializer


class ProductosListCreate(generics.ListCreateAPIView):
    serializer_class = ProductosSerializer

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
        qs = (
            ProductosModel.objects
            .all()
            .order_by("-id")
            .prefetch_related("producto_colores", "producto_colores__color")
        )

        categoria_id = self.request.query_params.get("categoria_id")
        if categoria_id is not None and str(categoria_id).strip() != "":
            categoria_id_int = self._parse_int(categoria_id, "categoria_id")
            qs = qs.filter(categoria_id=categoria_id_int)

        item = self.request.query_params.get("item")
        if item:
            qs = qs.filter(item=item)

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
    queryset = ProductosModel.objects.all()
    lookup_field = "id"

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProductoDetalleSerializer
        return ProductosSerializer
