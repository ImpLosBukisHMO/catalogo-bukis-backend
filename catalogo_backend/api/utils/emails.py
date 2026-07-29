# pyrefly: ignore [missing-import]
from django.core.mail import EmailMultiAlternatives
# pyrefly: ignore [missing-import]
from django.utils.html import escape, strip_tags
# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from django.contrib.staticfiles import finders
from email.mime.image import MIMEImage
from datetime import date
from html import unescape
import logging

from api.models import PedidosModel, UsuariosModel


logger = logging.getLogger(__name__)


def escape_email_text(value, default=""):
    if value in (None, ""):
        return default
    return escape(str(value))

def send_bukis_email(recipient_name, recipient_email, mail_subject, html_body):
    greeting = f"<h2>Hola, {escape_email_text(recipient_name, 'cliente')}.</h2>"

    full_mail = (
        f"{greeting}"
        f"{html_body}"
        f'<p style="font-size: 1.3em;">Muchas gracias por su atención.</p>'
        f'<img src="cid:logo_bukis" width="180" height="auto">'
        f'<p style="font-size: 1.1em;">Copyright &copy; {date.today().year} Importaciones Los Bukis.Todos los derechos reservados.<br>Blvd. Solidaridad 118 A, Raquet Club II, 83200 Hermosillo, Sonora, México.</p>'
    )

    body = unescape(strip_tags(full_mail))

    msg = EmailMultiAlternatives(
        subject=mail_subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    
    msg.attach_alternative(full_mail, "text/html")
    logo_path = finders.find("img/logo.png")

    if logo_path:
        try:
            with open(logo_path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<logo_bukis>')
                img.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg.attach(img)
        except Exception as e:
            print(f"No se pudo adjuntar el logo: {e}")
    else:
        print("Advertencia: No se encontró img/logo.png en los estáticos.")

    msg.send(fail_silently=False)


def send_comprobante_pago_worker_email(pedido: PedidosModel) -> int:
    staff_users = UsuariosModel.objects.filter(is_staff=True, is_active=True).exclude(correo="")
    if not staff_users.exists():
        return 0

    cliente_nombre = escape_email_text(f"{pedido.cliente.nombre} {pedido.cliente.apellido}", "cliente")
    html_body = (
        f'<p style="font-size: 1.3em;">El cliente <b>{cliente_nombre}</b> subió un comprobante '
        f'para el pedido con folio <b>{pedido.folio}</b>.</p>'
        f'<p style="font-size: 1.3em;">Ingresa al panel de pedidos del worker para revisarlo de forma segura.</p>'
    )

    sent = 0
    for worker in staff_users:
        try:
            send_bukis_email(
                recipient_name=worker.nombre or "equipo Bukis",
                recipient_email=worker.correo,
                mail_subject="📎 Nuevo comprobante de pago disponible | Importaciones Los Bukis",
                html_body=html_body,
            )
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send comprobante upload notification",
                extra={"pedido_id": pedido.id, "worker_id": worker.id},
            )

    return sent
