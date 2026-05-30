from django.test import TestCase

from api.models import UsuariosModel, PedidosModel
from api.serializer.worker import WorkerCambiarEstadoSerializer


class WorkerCambiarEstadoSerializerTest(TestCase):
    def setUp(self):
        self.cliente = UsuariosModel.objects.create_user(
            nombre="Test",
            apellido="Customer",
            correo="customer@test.com",
            telefono="555-1234567",
            password="testpass123",
            staff=False,
        )
        self.pedido = PedidosModel.objects.create(
            cliente=self.cliente,
            clave="TEST-KEY-001",
            estado=PedidosModel.EstadoPedido.PENDIENTE,
            precio_total=100.00,
            subtotal_snapshot=90.00,
        )

    def _validate(self, estado, **kwargs):
        data = {"estado": estado, **kwargs}
        s = WorkerCambiarEstadoSerializer(
            data=data,
            context={"pedido": self.pedido},
        )
        return s

    # ── Valid transitions ─────────────────────────────────────────

    def test_pending_to_approved(self):
        s = self._validate("APPROVED")
        self.assertTrue(s.is_valid())

    def test_pending_to_denied_with_reason(self):
        s = self._validate("DENIED", denegado_razon="Out of stock")
        self.assertTrue(s.is_valid())

    def test_approved_to_ready(self):
        self.pedido.estado = PedidosModel.EstadoPedido.APROBADO
        self.pedido.save()
        s = self._validate("READY")
        self.assertTrue(s.is_valid())

    def test_ready_to_shipped(self):
        self.pedido.estado = PedidosModel.EstadoPedido.LISTO
        self.pedido.save()
        s = self._validate("SHIPPED")
        self.assertTrue(s.is_valid())

    def test_shipped_to_completed(self):
        self.pedido.estado = PedidosModel.EstadoPedido.ENVIADO
        self.pedido.save()
        s = self._validate("COMPLETED")
        self.assertTrue(s.is_valid())

    # ── Invalid transitions ───────────────────────────────────────

    def test_pending_to_shipped_skip(self):
        s = self._validate("SHIPPED")
        self.assertFalse(s.is_valid())

    def test_approved_to_completed_skip(self):
        self.pedido.estado = PedidosModel.EstadoPedido.APROBADO
        self.pedido.save()
        s = self._validate("COMPLETED")
        self.assertFalse(s.is_valid())

    def test_denied_without_reason(self):
        s = self._validate("DENIED")
        self.assertFalse(s.is_valid())

    def test_same_state_rejected(self):
        s = self._validate("PENDING")
        self.assertFalse(s.is_valid())

    def test_denied_terminal(self):
        self.pedido.estado = PedidosModel.EstadoPedido.DENEGADO
        self.pedido.save()
        s = self._validate("APPROVED")
        self.assertFalse(s.is_valid())

    def test_completed_terminal(self):
        self.pedido.estado = PedidosModel.EstadoPedido.COMPLETADO
        self.pedido.save()
        s = self._validate("SHIPPED")
        self.assertFalse(s.is_valid())
