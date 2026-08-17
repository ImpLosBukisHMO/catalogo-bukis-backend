"""
Pruebas para el management command: cancelar_pedidos_vencidos.

Verifica que el cron cancela automáticamente los pedidos APROBADO
cuyo comprobante_deadline expiró sin que el cliente haya subido comprobante.
"""
import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from api.models import (
    CarritoModel,
    CarritoItemModel,
    ColorModel,
    PedidosModel,
    ProductoVariantesModel,
    ProductosModel,
    UsuariosModel,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_user(correo: str = "cron@test.com") -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Cron",
        apellido="Test",
        correo=correo,
        telefono="5550000000",
        password="TestPassword1!",
    )


def _create_pedido_aprobado(
    cliente: UsuariosModel,
    deadline_offset_hours: int = -1,
    comprobante: str = "",
) -> PedidosModel:
    """
    Crea un pedido en estado APROBADO con un deadline dado.
    deadline_offset_hours negativo = deadline en el pasado (expirado).
    """
    pedido = PedidosModel.objects.create(
        cliente=cliente,
        estado=PedidosModel.EstadoPedido.APROBADO,
        comprobante_deadline=timezone.now() + datetime.timedelta(hours=deadline_offset_hours),
        comprobante_pago=comprobante,
    )
    return pedido


# =============================================================================
# Tests
# =============================================================================

class CancelarPedidosVencidosTests(TestCase):

    def setUp(self):
        self.user = _create_user()

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_cancela_pedido_aprobado_con_deadline_expirado_sin_comprobante(self, mock_thread):
        """Un pedido APROBADO con deadline vencido y sin comprobante debe ser cancelado."""
        pedido = _create_pedido_aprobado(self.user, deadline_offset_hours=-2)

        out = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=out)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidosModel.EstadoPedido.CANCELADO)
        self.assertIn("automaticamente", pedido.denegado_razon or "")
        self.assertIsNone(pedido.comprobante_deadline)

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_no_cancela_pedido_aprobado_con_comprobante_subido(self, mock_thread):
        """Si el cliente ya subió comprobante, no se cancela (un worker lo revisa)."""
        pedido = _create_pedido_aprobado(
            self.user, deadline_offset_hours=-2, comprobante="comprobantes/test.pdf",
        )

        out = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=out)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidosModel.EstadoPedido.APROBADO)

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_no_cancela_pedido_con_deadline_futuro(self, mock_thread):
        """Un pedido cuyo deadline aún no pasa NO debe cancelarse."""
        pedido = _create_pedido_aprobado(self.user, deadline_offset_hours=24)

        out = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=out)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidosModel.EstadoPedido.APROBADO)

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_no_cancela_pedido_en_estado_diferente_a_aprobado(self, mock_thread):
        """Solo pedidos APROBADO son candidatos a cancelación."""
        pedido = PedidosModel.objects.create(
            cliente=self.user,
            estado=PedidosModel.EstadoPedido.PENDIENTE,
            comprobante_deadline=timezone.now() - datetime.timedelta(hours=2),
        )

        out = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=out)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidosModel.EstadoPedido.PENDIENTE)

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_cancelacion_asigna_razon_y_limpia_deadline(self, mock_thread):
        """La razón debe explicar por qué fue cancelado y el deadline debe quedar en None."""
        pedido = _create_pedido_aprobado(self.user, deadline_offset_hours=-3)

        call_command("cancelar_pedidos_vencidos", stdout=StringIO())

        pedido.refresh_from_db()
        self.assertIsNotNone(pedido.denegado_razon)
        self.assertIn("48 horas", pedido.denegado_razon)
        self.assertIsNone(pedido.comprobante_deadline)

    @patch("api.management.commands.cancelar_pedidos_vencidos.threading.Thread")
    def test_sin_pedidos_vencidos_no_hace_nada(self, mock_thread):
        """Si no hay pedidos vencidos, el command no falla y no modifica nada."""
        out = StringIO()
        call_command("cancelar_pedidos_vencidos", stdout=out)
        output = out.getvalue()
        self.assertIn("No hay pedidos vencidos", output)
