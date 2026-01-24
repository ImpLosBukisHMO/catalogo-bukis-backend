# api/views/productosImagenesViews.py
from rest_framework import generics
from api.models import ProductosImagenesModel
from api.serializers import ProductosImagenesSerializer

class ProductosImagenesListCreateView(generics.ListCreateAPIView):
    queryset = ProductosImagenesModel.objects.all()
    serializer_class = ProductosImagenesSerializer

    def get_queryset(self):
        qs = ProductosImagenesModel.objects.all().select_related("producto", "variante").order_by("orden", "id")

        producto_id = self.request.query_params.get("producto")
        variante_id = self.request.query_params.get("variante")

        if producto_id:
            qs = qs.filter(producto_id=producto_id)

        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        return qs


class ProductosImagenesDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductosImagenesModel.objects.all()
    serializer_class = ProductosImagenesSerializer
    lookup_field = "id"
