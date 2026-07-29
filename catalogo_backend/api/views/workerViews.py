import threading
# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from api.utils.emails import escape_email_text, send_bukis_email
# pyrefly: ignore [missing-import]
from django.db import transaction
# pyrefly: ignore [missing-import]
from django.db.models import Prefetch
# pyrefly: ignore [missing-import]
from rest_framework.views import APIView
# pyrefly: ignore [missing-import]
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from rest_framework.permissions import IsAuthenticated
# pyrefly: ignore [missing-import]
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
from api.utils.comprobantes import build_comprobante_response


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
            .select_related(
                "producto__categoria__descuento_general", 
                "producto__descuento_especial", 
                "color"
            )
            .prefetch_related(
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


class WorkerPedidoComprobanteDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    def get(self, request, pedido_id):
        try:
            pedido = PedidosModel.objects.get(pk=pedido_id)
        except PedidosModel.DoesNotExist:
            return Response({"error": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if not pedido.comprobante_pago:
            return Response({"error": "El pedido no tiene comprobante."}, status=status.HTTP_404_NOT_FOUND)

        return build_comprobante_response(pedido.comprobante_pago)


# =========================
# WORKER - CAMBIAR ESTADO PEDIDO
# =========================
class WorkerCambiarEstadoView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @staticmethod
    def _email_text(value, default):
        return escape_email_text(value, default)

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
        mail_subject = ""

        if serializer.validated_data.get("nota_worker"):
            pedido.nota_worker = serializer.validated_data["nota_worker"]

        if serializer.validated_data.get("denegado_razon"):
            pedido.denegado_razon = serializer.validated_data["denegado_razon"]

        pedido.save(update_fields=["estado", "nota_worker", "denegado_razon", "updated_at"])

        # Enviar correo fuera de la transacción para no bloquear la base de datos
        customer_name = f"{pedido.cliente.nombre} {pedido.cliente.apellido}"
        customer_email = pedido.cliente.correo
        folio = pedido.folio
        bank_name = self._email_text(settings.BANK_NAME, "")
        bank_account_name = self._email_text(settings.BANK_ACCOUNT_NAME, "")
        bank_account_ref = self._email_text(settings.BANK_ACCOUNT_REF, "")
        
        if pedido.estado == PedidosModel.EstadoPedido.PENDIENTE:
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "📋 Su pedido está siendo revisado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> está siendo revisado. Pronto le avisaremos si fue aprobado o denegado.</p>'
                f'<p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.APROBADO:
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "👍 Su pedido ha sido aprobado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> ha sido <span style="color: #b45309;"><b>{pedido.get_estado_display().upper()}.</b></span>'
                f' Es necesario subir la evidencia del pago de este pedido en la plataforma dentro de las siguientes <b>48 horas</b> para que no sea cancelado.</p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Información de pago:</b></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Nombre:</b> {bank_account_name}</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Referencia:</b> {bank_account_ref}</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Banco:</b> {bank_name}</p></li></ul></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.DENEGADO:
            rejection_note = self._email_text(pedido.denegado_razon, "Ninguno.")
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "❌ Su pedido ha sido denegado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> ha sido <span style="color: #b91c1c;"><b>{pedido.get_estado_display().upper()}.</b></span></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Motivo del rechazo: </b>{rejection_note}</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.LISTO:
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "🔔 Su pedido está listo | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> está <span style="color: #b45309;"><b>{pedido.get_estado_display().upper()}.</b></span></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Instrucciones: </b>Esté al pendiente para cuando se le notifique su envío.</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.ENVIADO:
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "📦 Su pedido ha sido enviado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> ha sido <span style="color: #15803d;"><b>{pedido.get_estado_display().upper()}.</b></span></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Indicaciones: </b>Su pedido debería de llegar aproximadamente en 3 días.</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.COMPLETADO:
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "✅ Su pedido ha sido completado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> ha sido <span style="color: #1d4ed8;"><b>{pedido.get_estado_display().upper()}.</b></span></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Indicaciones: </b>Por favor, notifíquenos si el pedido llegó completo y sin daño(s).</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        elif pedido.estado == PedidosModel.EstadoPedido.CANCELADO:
            rejection_note = self._email_text(pedido.denegado_razon, "Ninguno.")
            additional_notes = self._email_text(pedido.nota_worker, "Ninguna.")
            mail_subject = "‼️ Su pedido ha sido cancelado | Importaciones Los Bukis"
            mail_body = (
                f'<p style="font-size: 1.3em;">Su pedido con el folio <b>{folio}</b> ha sido <span style="color: #1d4ed8;"><b>{pedido.get_estado_display().upper()}.</b></span></p>'
                f'<ul><li><p style="font-size: 1.3em;"><b>Motivo de la cancelación: </b>{rejection_note}</p></li>'
                f'<li><p style="font-size: 1.3em;"><b>Notas adicionales: </b>{additional_notes}</p></li></ul>'
            )
        

        try:
            transaction.on_commit(
                lambda: threading.Thread(
                    target=send_bukis_email,
                    args=(customer_name, customer_email, mail_subject, mail_body)
                ).start()
            )
        except Exception as e:
            print(f"Error al enviar correo a \"{customer_email}\".\nDetalle(s):\n{e}")

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
