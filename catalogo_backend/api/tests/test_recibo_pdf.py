from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.models import DireccionesModel, PedidoProductosModel, PedidosModel, UsuariosModel
from api.utils.recibos import RECIBO_ALLOWED_STATES, build_recibo_pdf_response, render_recibo_html


def create_user(*, email: str, staff: bool = False, worker_role: str = "none") -> UsuariosModel:
    user = UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="5551234567",
        password="testpass123",
        staff=staff,
    )
    if worker_role != "none":
        user.worker_role = worker_role
        user.save(update_fields=["worker_role"])
    return user


class ReciboPdfViewTests(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.owner = create_user(email="owner@test.com")
        self.other_cliente = create_user(email="other@test.com")
        self.worker_total = create_user(
            email="worker-total@test.com",
            staff=True,
            worker_role=UsuariosModel.WorkerRole.TOTAL,
        )
        self.worker_parcial = create_user(
            email="worker-parcial@test.com",
            staff=True,
            worker_role=UsuariosModel.WorkerRole.PARCIAL,
        )
        self.address = DireccionesModel.objects.create(
            usuario=self.owner,
            calle="Av. Reforma 1234",
            colonia="Centro",
            codigo_postal="83000",
            ciudad="Hermosillo",
            estado="Sonora",
            pais="México",
        )

    def auth(self, user: UsuariosModel):
        self.client_api.force_authenticate(user=user)

    def create_pedido(self, *, owner=None, estado=PedidosModel.EstadoPedido.APROBADO, direccion=None, item_name="Camisa Azul"):
        pedido = PedidosModel.objects.create(
            cliente=owner or self.owner,
            clave=f"PEDIDO-{timezone.now().timestamp()}",
            estado=estado,
            direccion=direccion,
            subtotal_snapshot=Decimal("1512.00"),
            precio_total=Decimal("1512.00"),
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        PedidoProductosModel.objects.create(
            pedido=pedido,
            cantidad=2,
            producto_nombre_snapshot=item_name,
            producto_item_snapshot="SKU-001",
            descripcion_snapshot="desc",
            color_nombre_snapshot="Azul Marino",
            color_hex_snapshot="#001122",
            precio_unitario_snapshot=Decimal("756.00"),
            descuento_porcentaje_snapshot=Decimal("0.00"),
            subtotal_linea_snapshot=Decimal("1512.00"),
            imagen_principal_snapshot="snapshot.jpg",
            variante=None,
            producto=None,
        )
        return pedido

    def test_recibo_allowed_states_constant_matches_spec(self):
        self.assertEqual(
            RECIBO_ALLOWED_STATES,
            frozenset({"APPROVED", "READY", "SHIPPED", "COMPLETED"}),
        )

    def test_owner_can_download_recibo_for_approved_order(self):
        pedido = self.create_pedido(direccion=self.address)
        self.auth(self.owner)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('inline; filename="recibo-000001.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_owner_pending_order_returns_409(self):
        pedido = self.create_pedido(estado=PedidosModel.EstadoPedido.PENDIENTE)
        self.auth(self.owner)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_owner_canceled_order_returns_409(self):
        pedido = self.create_pedido(estado=PedidosModel.EstadoPedido.CANCELADO)
        self.auth(self.owner)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_other_client_gets_404_for_order_they_do_not_own(self):
        pedido = self.create_pedido()
        self.auth(self.other_cliente)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_client_gets_401(self):
        pedido = self.create_pedido()

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_worker_is_forbidden_on_client_endpoint(self):
        pedido = self.create_pedido()
        self.auth(self.worker_total)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_without_worker_role_is_forbidden_on_client_endpoint(self):
        pedido = self.create_pedido()
        staff_without_worker_role = create_user(
            email="staff-no-worker@test.com",
            staff=True,
            worker_role="none",
        )
        self.auth(staff_without_worker_role)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_staff_worker_role_is_forbidden_on_client_endpoint(self):
        pedido = self.create_pedido(owner=self.worker_total)
        self.worker_total.is_staff = False
        self.worker_total.save(update_fields=["is_staff"])
        self.auth(self.worker_total)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_worker_total_can_download_ready_order(self):
        pedido = self.create_pedido(estado=PedidosModel.EstadoPedido.LISTO)
        self.auth(self.worker_total)

        response = self.client_api.get(reverse("worker-pedido-recibo", kwargs={"pedido_id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="recibo-000001.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_worker_parcial_can_download_shipped_order(self):
        pedido = self.create_pedido(estado=PedidosModel.EstadoPedido.ENVIADO)
        self.auth(self.worker_parcial)

        response = self.client_api.get(reverse("worker-pedido-recibo", kwargs={"pedido_id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_non_worker_gets_403_on_worker_endpoint(self):
        pedido = self.create_pedido()
        self.auth(self.owner)

        response = self.client_api.get(reverse("worker-pedido-recibo", kwargs={"pedido_id": pedido.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recibo_renders_without_address(self):
        pedido = self.create_pedido(direccion=None)
        self.auth(self.owner)

        response = self.client_api.get(reverse("mi-pedido-recibo", kwargs={"id": pedido.id}))
        html = render_recibo_html(pedido)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Dirección de envío", html)

    def test_render_recibo_html_uses_snapshot_fields_only(self):
        pedido = self.create_pedido(direccion=self.address, item_name="Camisa Azul")
        item = pedido.items.get()
        item.variante = None
        item.producto = None
        item.save(update_fields=["variante", "producto"])

        html = render_recibo_html(pedido)

        self.assertIn("Importaciones Los Bukis", html)
        self.assertIn('<table class="items">', html)
        self.assertIn("Camisa Azul", html)
        self.assertIn("5551234567", html)
        self.assertNotIn("nota_worker", html)
        self.assertNotIn("comprobante", html.lower())

    def test_build_recibo_response_sets_inline_filename(self):
        response = build_recibo_pdf_response(b"%PDF-1.4 test", "000042")

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="recibo-000042.pdf"')
