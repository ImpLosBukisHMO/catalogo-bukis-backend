from rest_framework import generics
from rest_framework.exceptions import ValidationError
from api.models import ProductosModel
from api.serializers import ProductosSerializer


class ProductosListCreate(generics.ListCreateAPIView):
    serializer_class = ProductosSerializer

    def get_queryset(self):
        qs = ProductosModel.objects.all().order_by("-id")

        # Filtros opcionales por query params
        categoria_id = self.request.query_params.get("categoria_id")
        if categoria_id is not None and str(categoria_id).strip() != "":
            try:
                categoria_id_int = int(categoria_id)
            except ValueError:
                raise ValidationError({"categoria_id": "Debe ser un entero."})
            qs = qs.filter(categoria_id=categoria_id_int)

        item = self.request.query_params.get("item")
        if item:
            qs = qs.filter(item=item)

        return qs


class ProductosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductosModel.objects.all()
    serializer_class = ProductosSerializer
    lookup_field = "id"
