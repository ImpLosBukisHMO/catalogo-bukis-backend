from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.permissions import IsWorker
from api.models import (
    ProductoVariantesModel,
    PedidosModel,
)
from api.serializer.worker import (
    WorkerVariantSerializer,
    WorkerPedidoSerializer,
)


# =========================
# WORKER - VARIANTS
# =========================
class WorkerVariantListView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        qs = (
            ProductoVariantesModel.objects
            .select_related(
                "producto",
                "producto__categoria",
                "color",
            )
            .order_by("producto__nombre", "color__nombre")
        )

        serializer = WorkerVariantSerializer(qs, many=True)
        return Response(serializer.data)


# =========================
# WORKER - PEDIDOS
# =========================
class WorkerPedidoListView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        qs = (
            PedidosModel.objects
            .select_related("cliente")
            .prefetch_related("items")
            .order_by("-created_at")
        )

        serializer = WorkerPedidoSerializer(qs, many=True)
        return Response(serializer.data)
