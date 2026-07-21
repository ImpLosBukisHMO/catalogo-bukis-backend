from django.utils import timezone
from django.db.models import Q

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from api.permissions import IsWorker
from api.models import BannerOfertaModel
from api.serializer.worker import WorkerBannerOfertaSerializer
from api.serializer.client import BannerOfertaPublicSerializer


# =========================
# WORKER - BANNER DE OFERTAS
# =========================
class WorkerBannerOfertasListCreate(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsWorker]
    queryset = BannerOfertaModel.objects.all()
    serializer_class = WorkerBannerOfertaSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]


class WorkerBannerOfertasRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsWorker]
    queryset = BannerOfertaModel.objects.all()
    serializer_class = WorkerBannerOfertaSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "id"


# =========================
# PÚBLICO - BANNER DE OFERTAS
# =========================
class BannerOfertasPublicList(generics.ListAPIView):
    """Endpoint público: solo banners activos y dentro de la ventana de vigencia."""
    permission_classes = [AllowAny]
    serializer_class = BannerOfertaPublicSerializer
    pagination_class = None  # El slider necesita todos los vigentes

    def get_queryset(self):
        now = timezone.now()
        return (
            BannerOfertaModel.objects
            .filter(activo=True)
            .filter(Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=now))
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=now))
            .order_by("orden", "id")
        )
