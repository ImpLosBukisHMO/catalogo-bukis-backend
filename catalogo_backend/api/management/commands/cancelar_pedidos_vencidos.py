"""
Management command: cancelar_pedidos_vencidos
---------------------------------------------
Cancela automaticamente los pedidos en estado APROBADO cuyo
`comprobante_deadline` ya expiro (es decir, el cliente no subio
su comprobante dentro del plazo de 48 horas).

Uso:
    py manage.py cancelar_pedidos_vencidos

Se recomienda ejecutarlo periodicamente (ej. cada hora) via cron o Celery Beat.
"""
import threading

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import PedidosModel
from api.utils.emails import escape_email_text, send_bukis_email


class Command(BaseCommand):
    help = "Cancela pedidos APROBADO cuyo plazo de comprobante ha vencido."

    def handle(self, *args, **options):
        now = timezone.now()

        # Filtrar pedidos vencidos: APROBADO + deadline pasado + SIN comprobante.
        # Si el cliente ya subió su comprobante, no se cancela automáticamente;
        # un worker debe revisarlo manualmente.
        pedidos_vencidos = PedidosModel.objects.filter(
            estado=PedidosModel.EstadoPedido.APROBADO,
            comprobante_deadline__lt=now,
            comprobante_pago="",
        ).select_related("cliente")

        count = pedidos_vencidos.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No hay pedidos vencidos."))
            return

        self.stdout.write(f"Cancelando {count} pedido(s) vencido(s)...")

        for pedido in pedidos_vencidos:
            pedido.estado = PedidosModel.EstadoPedido.CANCELADO
            pedido.denegado_razon = (
                "El pedido fue cancelado automaticamente porque no se subio "
                "el comprobante de pago dentro del plazo de 48 horas."
            )
            pedido.comprobante_deadline = None
            pedido.save(update_fields=["estado", "denegado_razon", "comprobante_deadline", "updated_at"])

            # Enviar correo de cancelacion (en hilo separado para no bloquear)
            self._enviar_correo_cancelacion(pedido)
            self.stdout.write(f"  - Pedido #{pedido.folio} (ID {pedido.id}) cancelado.")

        self.stdout.write(self.style.SUCCESS(f"Listo. {count} pedido(s) cancelado(s)."))

    @staticmethod
    def _enviar_correo_cancelacion(pedido):
        customer_name = f"{pedido.cliente.nombre} {pedido.cliente.apellido}"
        customer_email = pedido.cliente.correo
        folio = f"#{pedido.folio}"
        rejection_note = escape_email_text(
            pedido.denegado_razon,
            "El plazo para subir el comprobante ha vencido.",
        )
        mail_subject = "!! Su pedido ha sido CANCELADO | Importaciones Los Bukis"
        mail_body = (
            f'<p>Su pedido con el folio <b>{folio}</b> ha sido '
            f'<span style="color: #b91c1c; font-weight: bold;">CANCELADO</span> '
            f'de forma automatica.</p>'
            f'<p><b>Motivo de la cancelacion: </b>{rejection_note}</p>'
            f'<p>Si cree que esto es un error, por favor contactenos.</p>'
        )
        try:
            threading.Thread(
                target=send_bukis_email,
                args=(customer_name, customer_email, mail_subject, mail_body),
            ).start()
        except Exception as e:
            print(f"Error al enviar correo de cancelacion a \"{customer_email}\".\nDetalle(s):\n{e}")
