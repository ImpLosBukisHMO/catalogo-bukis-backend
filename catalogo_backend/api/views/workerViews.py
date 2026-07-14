# pyrefly: ignore [missing-import]
from django.db.models import Prefetch

# pyrefly: ignore [missing-import]
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics

from api.permissions import IsWorker
from api.models import (
    ProductosModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    PedidosModel,
    DescuentosModel,
)
from api.serializer.worker import (
    WorkerDescuentosSerializer,
    WorkerVariantSerializer,
    WorkerPedidoSerializer,
    WorkerPedidoDetalleSerializer,
    WorkerCambiarEstadoSerializer,
    WorkerProductoSerializer,
    WorkerVarianteCreateSerializer,
    WorkerVarianteUpdateSerializer,
    WorkerImagenCreateSerializer,
)


# =========================
# WORKER - DESCUENTOS
# =========================
class WorkerDescuentosListCreate(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsWorker]
    queryset = DescuentosModel.objects.all()
    serializer_class = WorkerDescuentosSerializer

class WorkerDescuentosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsWorker]
    queryset = DescuentosModel.objects.all()
    serializer_class = WorkerDescuentosSerializer
    lookup_field = 'id'


class WorkerDescuentosTiposView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        tipos = [c[0] for c in DescuentosModel.DescuentoType.choices]
        return Response({"datos": tipos}, status=status.HTTP_200_OK)


# =========================
# WORKER - VARIANTS
# =========================
class WorkerVariantListView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        qs = (
            ProductoVariantesModel.objects
            .select_related("producto__categoria__descuento_general", 
                "producto__descuento_especial", "color",
                Prefetch(
                    "imagenes",
                    queryset=ProductosImagenesModel.objects.order_by("orden", "id"),
                    to_attr="_cached_variante_imagenes",
                ),
                Prefetch(
                    "producto__imagenes",
                    queryset=ProductosImagenesModel.objects
                        .filter(variante__isnull=True)
                        .order_by("orden", "id"),
                    to_attr="_cached_prod_imagenes",
                ),
            )
        )

        serializer = WorkerVariantSerializer(qs, many=True)
        return Response(serializer.data)


# =========================
# WORKER - PEDIDOS (con filtro opcional por estado)
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

        estado = request.query_params.get("estado")
        if estado:
            estado = estado.upper()
            estados_validos = PedidosModel.EstadoPedido.values
            if estado not in estados_validos:
                return Response(
                    {"error": f"Estado inválido. Opciones: {estados_validos}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(estado=estado)

        serializer = WorkerPedidoSerializer(qs, many=True)
        return Response(serializer.data)


# =========================
# WORKER - DETALLE PEDIDO
# =========================
class WorkerPedidoDetailView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request, pedido_id):
        try:
            pedido = (
                PedidosModel.objects
                .select_related("cliente")
                .prefetch_related("items")
                .get(pk=pedido_id)
            )
        except PedidosModel.DoesNotExist:
            return Response({"error": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkerPedidoDetalleSerializer(pedido)
        return Response(serializer.data)


# =========================
# WORKER - CAMBIAR ESTADO PEDIDO
# =========================
class WorkerCambiarEstadoView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def patch(self, request, pedido_id):
        try:
            pedido = PedidosModel.objects.get(pk=pedido_id)
        except PedidosModel.DoesNotExist:
            return Response({"error": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkerCambiarEstadoSerializer(
            data=request.data,
            context={"pedido": pedido},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pedido.estado = serializer.validated_data["estado"]

        if serializer.validated_data.get("nota_worker"):
            pedido.nota_worker = serializer.validated_data["nota_worker"]

        if serializer.validated_data.get("denegado_razon"):
            pedido.denegado_razon = serializer.validated_data["denegado_razon"]

        pedido.save(update_fields=["estado", "nota_worker", "denegado_razon", "updated_at"])

        return Response(WorkerPedidoSerializer(pedido).data)


# =========================
# WORKER - PRODUCTOS PROPIOS (listar y crear)
# =========================
class WorkerProductoListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request):
        qs = (
            ProductosModel.objects
            .filter(worker=request.user)
            .prefetch_related("producto_colores")
            .order_by("-created_at")
        )
        serializer = WorkerProductoSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkerProductoSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(worker=request.user, estado=ProductosModel.EstadoProducto.DRAFT)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# =========================
# WORKER - EDITAR PRODUCTO PROPIO
# =========================
class WorkerProductoUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def _get_producto_propio(self, request, producto_id):
        try:
            return ProductosModel.objects.get(pk=producto_id, worker=request.user)
        except ProductosModel.DoesNotExist:
            return None

    def get(self, request, producto_id):
        producto = self._get_producto_propio(request, producto_id)
        if not producto:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkerProductoSerializer(producto, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, producto_id):
        producto = self._get_producto_propio(request, producto_id)
        if not producto:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkerProductoSerializer(
            producto, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


# =========================
# WORKER - AGREGAR VARIANTE A PRODUCTO PROPIO
# =========================
class WorkerVarianteCreateView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def post(self, request, producto_id):
        try:
            producto = ProductosModel.objects.get(pk=producto_id, worker=request.user)
        except ProductosModel.DoesNotExist:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkerVarianteCreateSerializer(
            data=request.data,
            context={"producto": producto},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(producto=producto)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



# =========================
# WORKER - VER / EDITAR VARIANTE PROPIA
# =========================
class WorkerVarianteDetailView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def _get_variante_propia(self, request, variante_id):
        """Devuelve la variante solo si su producto pertenece al worker autenticado."""
        try:
            return ProductoVariantesModel.objects.select_related("producto", "color").get(
                pk=variante_id,
                producto__worker=request.user,
            )
        except ProductoVariantesModel.DoesNotExist:
            return None

    def get(self, request, id):
        variante = self._get_variante_propia(request, id)
        if not variante:
            return Response({"error": "Variante no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        from api.serializer.worker import WorkerVariantSerializer
        serializer = WorkerVariantSerializer(variante)
        return Response(serializer.data)

    def patch(self, request, id):
        variante = self._get_variante_propia(request, id)
        if not variante:
            return Response({"error": "Variante no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkerVarianteUpdateSerializer(
            variante, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


# =========================
# WORKER - SUBIR IMAGEN A PRODUCTO PROPIO
# =========================
class WorkerImagenCreateView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def post(self, request, producto_id):
        try:
            producto = ProductosModel.objects.get(pk=producto_id, worker=request.user)
        except ProductosModel.DoesNotExist:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkerImagenCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Validar que la variante (si se pasa) pertenece al producto
        variante = serializer.validated_data.get("variante")
        if variante and variante.producto_id != producto.id:
            return Response(
                {"error": "La variante no pertenece a este producto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(producto=producto)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

