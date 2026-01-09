from rest_framework import generics
from api.models import ProductosModel
from api.serializers import ProductoDetalleSerializer

class ProductoDetalle(generics.RetrieveAPIView):
    queryset = ProductosModel.objects.all()
    serializer_class = ProductoDetalleSerializer
    lookup_field = "id"
