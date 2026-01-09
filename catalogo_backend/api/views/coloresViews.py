from rest_framework import generics
from ..models import ColorModel
from ..serializers import ColorSerializer


class ColoresListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/colores/  -> lista de colores
    POST /api/colores/  -> crear color
    """
    queryset = ColorModel.objects.all()
    serializer_class = ColorSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        activo = self.request.query_params.get("activo")
        if activo is not None:
            activo_norm = activo.lower() in ("true", "1", "yes")
            qs = qs.filter(activo=activo_norm)

        return qs.order_by("nombre")
    
class ColoresDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/colores/<id>/ -> ver color
    PATCH  /api/colores/<id>/ -> editar color
    DELETE /api/colores/<id>/ -> eliminar color
    """
    lookup_field = "id"
    lookup_url_kwarg = "id"
    queryset = ColorModel.objects.all()
    serializer_class = ColorSerializer
