from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser

from ..models import ProductosImagenesModel
from ..serializers import ProductosImagenesSerializer


class ProductosImagenesListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductosImagenesSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = ProductosImagenesModel.objects.all()
        producto = self.request.query_params.get("producto")
        variante = self.request.query_params.get("variante")

        if producto:
            qs = qs.filter(producto_id=producto)
        if variante:
            qs = qs.filter(variante_id=variante)

        return qs.order_by("orden", "id")


class ProductosImagenesDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductosImagenesModel.objects.all()
    serializer_class = ProductosImagenesSerializer
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = "id"
