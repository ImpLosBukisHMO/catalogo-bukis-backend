from rest_framework import generics
from ..models import ProductoColorModel
from ..serializers import ProductoColorSerializer


class ProductoColorListCreateView(generics.ListCreateAPIView):
    queryset = ProductoColorModel.objects.all().order_by("-id")
    serializer_class = ProductoColorSerializer


class ProductoColorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductoColorModel.objects.all()
    serializer_class = ProductoColorSerializer
    lookup_field = "id"
