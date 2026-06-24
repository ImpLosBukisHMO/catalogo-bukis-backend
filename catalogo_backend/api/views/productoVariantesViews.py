# api/views/productoVariantesViews.py
from rest_framework import generics
from api.models import ProductoVariantesModel
from api.pagination import PublicCatalogPagination
from api.serializers import ProductoVariantesSerializer

class ProductoVariantesListCreateView(generics.ListCreateAPIView):
    queryset = ProductoVariantesModel.objects.all()
    serializer_class = ProductoVariantesSerializer
    pagination_class = PublicCatalogPagination
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = ProductoVariantesModel.objects.filter(
            producto__disponible=True,
            producto__estado="active",
            activo=True,
        ).select_related("producto", "color")

        producto_id = self.request.query_params.get("producto")
        color_id = self.request.query_params.get("color")

        if producto_id:
            qs = qs.filter(producto_id=producto_id)

        if color_id:
            qs = qs.filter(color_id=color_id)

        return qs


class ProductoVariantesDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductoVariantesSerializer
    lookup_field = "id"
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return ProductoVariantesModel.objects.filter(
            producto__disponible=True,
            producto__estado="active",
            activo=True,
        ).select_related("producto", "color")
