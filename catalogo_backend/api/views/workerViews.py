from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.permissions import IsWorker
from api.models import ProductoVariantesModel
from api.serializer.worker import WorkerVariantSerializer


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
