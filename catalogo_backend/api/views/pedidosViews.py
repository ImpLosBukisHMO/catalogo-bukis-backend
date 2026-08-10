import logging

from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..serializers import (
    PedidosSerializer,
    PedidoProductosSerializer,
    ClientePedidoSerializer,
    ClientePedidoListSerializer,
)
from api.serializer.client import MiPedidoComprobanteUpdateSerializer
from api.models import PedidosModel, PedidoProductosModel
from api.utils.comprobantes import build_comprobante_response
from api.utils.emails import send_comprobante_pago_worker_email
# pyrefly: ignore [missing-import]
from api.permissions import IsWorker


logger = logging.getLogger(__name__)


# ---PEDIDOS VIEWS--- #
class PedidosListCreate(generics.ListCreateAPIView):
    """
    Endpoint interno para uso exclusivo de workers/admin.
    Protegido contra IDOR: requiere autenticación y rol de staff.
    Los clientes deben usar /api/mis-pedidos/ para acceder a sus propios pedidos.
    """
    queryset = PedidosModel.objects.all()
    serializer_class = PedidosSerializer
    permission_classes = [IsAuthenticated, IsWorker]

    def post(self, request, *args, **kwargs):
        serializer = PedidosSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Pedido creado exitosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        pedidos = PedidosModel.objects.all()
        serializer = PedidosSerializer(pedidos, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class PedidosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint interno para uso exclusivo de workers/admin.
    Protegido contra IDOR: requiere autenticación y rol de staff.
    Los clientes deben usar /api/mis-pedidos/ para acceder a sus propios pedidos.
    """
    queryset = PedidosModel.objects.all()
    serializer_class = PedidosSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    # Actualizar pedido por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'mensaje': 'Pedido eliminado con éxito.'}, status=status.HTTP_204_NO_CONTENT)


# --- PEDIDOS PRODUCTOS VIEWS --- #
class PedidoProductosListCreate(generics.ListCreateAPIView): 
    """
    Endpoint interno para uso exclusivo de workers/admin.
    Protegido contra IDOR: requiere autenticación y rol de staff.
    """
    queryset = PedidoProductosModel.objects.all()
    serializer_class = PedidoProductosSerializer
    permission_classes = [IsAuthenticated, IsWorker]

    def post(self, request, *args, **kwargs):
        serializer = PedidoProductosSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Producto añadido al pedido existosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidoProductosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint interno para uso exclusivo de workers/admin.
    Protegido contra IDOR: requiere autenticación y rol de staff.
    """
    queryset = PedidoProductosModel.objects.all()
    serializer_class = PedidoProductosSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    
    # Actualizar proucto por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'mensaje': 'Producto eliminado del pedido con éxito.'}, status=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------
# Vistas para el cliente: sus propios pedidos
# -------------------------------------------------------
class MisPedidosListView(generics.ListAPIView):
    """GET /api/mis-pedidos/ — lista los pedidos del usuario autenticado."""
    serializer_class = ClientePedidoListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            PedidosModel.objects
            .filter(cliente=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )


class MiPedidoDetalleView(generics.RetrieveAPIView):
    """GET /api/mis-pedidos/<id>/ — detalle de un pedido del usuario autenticado."""
    serializer_class = ClientePedidoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return (
            PedidosModel.objects
            .filter(cliente=self.request.user)
            .prefetch_related("items")
        )


class MiPedidoComprobanteUpdateView(generics.GenericAPIView):
    serializer_class = MiPedidoComprobanteUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    @staticmethod
    def _get_pedido(*, id, user):
        try:
            return (
                PedidosModel.objects
                .filter(cliente=user)
                .prefetch_related("items")
                .get(pk=id)
            )
        except PedidosModel.DoesNotExist:
            return None

    def get(self, request, id, *args, **kwargs):
        if request.user.is_staff:
            return Response(
                {"error": "No tienes permiso para ver este pedido."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pedido = self._get_pedido(id=id, user=request.user)
        if pedido is None:
            return Response({"error": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if not pedido.comprobante_pago:
            return Response({"error": "El pedido no tiene comprobante."}, status=status.HTTP_404_NOT_FOUND)

        return build_comprobante_response(pedido.comprobante_pago)

    def patch(self, request, id, *args, **kwargs):
        if request.user.is_staff:
            return Response(
                {"error": "No tienes permiso para modificar este pedido."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pedido = self._get_pedido(id=id, user=request.user)
        if pedido is None:
            return Response({"error": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pedido.estado != PedidosModel.EstadoPedido.APROBADO:
            return Response(
                {"error": "Solo puedes subir comprobante cuando el pedido está aprobado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(instance=pedido, data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_name = pedido.comprobante_pago.name if pedido.comprobante_pago else None
        uploaded_file = serializer.validated_data["comprobante_pago"]

        pedido.comprobante_pago.save(uploaded_file.name, uploaded_file, save=False)
        pedido.updated_at = timezone.now()
        pedido.save(update_fields=["comprobante_pago", "updated_at"])

        if previous_name and previous_name != pedido.comprobante_pago.name:
            try:
                pedido.comprobante_pago.storage.delete(previous_name)
            except Exception:
                logger.warning(
                    "Failed to delete previous comprobante file",
                    extra={"pedido_id": pedido.id, "file_name": previous_name},
                )

        try:
            send_comprobante_pago_worker_email(pedido)
        except Exception:
            logger.exception(
                "Failed to send comprobante upload notification",
                extra={"pedido_id": pedido.id},
            )

        pedido.refresh_from_db()
        return Response(ClientePedidoSerializer(pedido).data, status=status.HTTP_200_OK)
