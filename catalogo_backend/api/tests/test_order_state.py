from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from rest_framework.test import APIClient

from api.models import UsuariosModel, PedidosModel
from api.serializer.worker import WorkerCambiarEstadoSerializer
from api.utils.emails import send_bukis_email


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

    def test_approved_to_canceled_with_reason(self):
        self.pedido.estado = PedidosModel.EstadoPedido.APROBADO
        self.pedido.save()
        s = self._validate("CANCELED", denegado_razon="Payment window expired")
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

    def test_canceled_without_reason(self):
        self.pedido.estado = PedidosModel.EstadoPedido.APROBADO
        self.pedido.save()
        s = self._validate("CANCELED")
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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BukisEmailSafetyTest(TestCase):
    def test_send_bukis_email_escapes_recipient_name_but_keeps_plain_text_readable(self):
        send_bukis_email(
            recipient_name='<img src=x onerror="alert(1)">',
            recipient_email="customer@test.com",
            mail_subject="Test",
            html_body='<p>Motivo: &lt;b&gt;rechazado&lt;/b&gt;</p>',
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', message.alternatives[0][0])
        self.assertNotIn('<img src=x onerror="alert(1)">', message.alternatives[0][0])
        self.assertIn('Motivo: <b>rechazado</b>', message.body)


class WorkerCambiarEstadoEmailEscapingTest(TestCase):
    def setUp(self):
        self.worker = UsuariosModel.objects.create_user(
            nombre="Worker",
            apellido="Test",
            correo="worker@test.com",
            telefono="555-0000001",
            password="testpass123",
            staff=True,
        )
        self.worker.worker_role = UsuariosModel.WorkerRole.TOTAL
        self.worker.save(update_fields=["worker_role"])
        self.cliente = UsuariosModel.objects.create_user(
            nombre='Ana <script>alert(1)</script>',
            apellido='Cliente',
            correo="customer@test.com",
            telefono="555-1234567",
            password="testpass123",
            staff=False,
        )
        self.pedido = PedidosModel.objects.create(
            cliente=self.cliente,
            clave="TEST-KEY-002",
            estado=PedidosModel.EstadoPedido.PENDIENTE,
            precio_total=100.00,
            subtotal_snapshot=90.00,
        )
        self.api = APIClient()
        self.url = reverse("worker-cambiar-estado", kwargs={"pedido_id": self.pedido.id})

    def test_denied_email_escapes_worker_controlled_html(self):
        thread_targets = []

        class ImmediateThread:
            def __init__(self, target=None, args=(), kwargs=None):
                self.target = target
                self.args = args
                self.kwargs = kwargs or {}

            def start(self):
                thread_targets.append((self.target, self.args, self.kwargs))
                if self.target:
                    self.target(*self.args, **self.kwargs)

        self.api.force_authenticate(user=self.worker)

        with patch("api.views.workerViews.threading.Thread", ImmediateThread), patch(
            "api.views.workerViews.send_bukis_email"
        ) as mocked_send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.api.patch(
                    self.url,
                    data={
                        "estado": "DENIED",
                        "denegado_razon": '<script>alert("x")</script>',
                        "nota_worker": '<b>nota</b>',
                    },
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200, response.content)
        mocked_send.assert_called_once()
        mail_body = mocked_send.call_args.args[3]
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', mail_body)
        self.assertIn('&lt;b&gt;nota&lt;/b&gt;', mail_body)
        self.assertNotIn('<script>alert("x")</script>', mail_body)
        self.assertNotIn('<b>nota</b>', mail_body)
