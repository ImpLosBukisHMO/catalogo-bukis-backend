# api/views/productoVariantesViews.py
from rest_framework import generics
from api.models import ProductoVariantesModel
from api.serializers import ProductoVariantesSerializer

class ProductoVariantesListCreateView(generics.ListCreateAPIView):
    queryset = ProductoVariantesModel.objects.all()
    serializer_class = ProductoVariantesSerializer

    def get_queryset(self):
        qs = ProductoVariantesModel.objects.all().select_related("producto", "color")

        producto_id = self.request.query_params.get("producto")
        color_id = self.request.query_params.get("color")
        activo = self.request.query_params.get("activo")  # opcional: "true/false/1/0"

        if producto_id:
            qs = qs.filter(producto_id=producto_id)

        if color_id:
            qs = qs.filter(color_id=color_id)

        if activo is not None:
            val = str(activo).strip().lower()
            if val in ("1", "true", "t", "yes", "y"):
                qs = qs.filter(activo=True)
            elif val in ("0", "false", "f", "no", "n"):
                qs = qs.filter(activo=False)

        return qs


class ProductoVariantesDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductoVariantesModel.objects.all()
    serializer_class = ProductoVariantesSerializer
    lookup_field = "id"
