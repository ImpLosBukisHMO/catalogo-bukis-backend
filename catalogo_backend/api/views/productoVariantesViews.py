from rest_framework import generics
from ..models import ProductoVariantesModel
from ..serializers import ProductoVariantesSerializer


class ProductoVariantesListCreateView(generics.ListCreateAPIView):
    queryset = ProductoVariantesModel.objects.all().order_by("-id")
    serializer_class = ProductoVariantesSerializer

class ProductoVariantesDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductoVariantesModel.objects.all()
    serializer_class = ProductoVariantesSerializer
    lookup_field = "id"
