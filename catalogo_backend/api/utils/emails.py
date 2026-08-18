# pyrefly: ignore [missing-import]
from django.core.mail import EmailMultiAlternatives
# pyrefly: ignore [missing-import]
from django.utils.html import escape, strip_tags
# pyrefly: ignore [missing-import]
from django.conf import settings
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
    backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
    logo_url = f"{backend_url}/{settings.STATIC_URL}img/logo.png"
    display_name = escape_email_text(recipient_name, "cliente")

    full_mail = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #f8fafc; padding: 32px 12px;">
    <tr>
      <td align="center">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);">
          <!-- Header corporativo limpio en blanco -->
          <tr>
            <td style="background-color: #ffffff; padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #e2e8f0;">
              <div style="border: 1px solid #dd0000; display: inline-block; padding: 14px 24px; border-radius: 12px; margin-bottom: 10px;">
                <img src="{logo_url}" alt="Los Bukis" width="160" style="max-width: 160px; height: auto; display: block; margin: 0 auto;">
              </div>
              <div style="font-size: 1.3em; font-weight: 700; color: #dd0000; letter-spacing: 2px; text-transform: uppercase;">
                Importaciones Los Bukis
              </div>
            </td>
          </tr>
          <!-- Contenido Principal -->
          <tr>
            <td style="padding: 36px 32px; color: #334155; font-size: 15px; line-height: 1.6;">
              <h2 style="margin-top: 0; margin-bottom: 20px; font-size: 20px; font-weight: 700; color: #0f172a;">Hola, {display_name}</h2>
              {html_body}
              <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #f1f5f9; font-size: 14px; color: #64748b;">
                Muchas gracias por su atención.<br>
                <strong style="color: #0f172a;">Equipo de Importaciones Los Bukis</strong>
              </div>
            </td>
          </tr>
          <!-- Pie de página -->
          <tr>
            <td style="background-color: #f8fafc; padding: 24px 32px; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #f1f5f9;">
              <p style="margin: 0 0 6px 0;">Copyright &copy; {date.today().year} Importaciones Los Bukis. Todos los derechos reservados.</p>
              <p style="margin: 0;">Blvd. Solidaridad 118 A, Raquet Club II, 83200 Hermosillo, Sonora, México.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # Clean plain text version for spam filters
    body = f"Hola, {display_name}.\n\n"
    # Unescape html_body and remove simple tags for plain text
    clean_html_body = unescape(strip_tags(html_body.replace("<br>", "\n").replace("</p>", "\n\n")))
    body += clean_html_body.strip()
    body += "\n\nMuchas gracias por su atención.\nEquipo de Importaciones Los Bukis\n\nCopyright (c) Importaciones Los Bukis. Todos los derechos reservados."

    msg = EmailMultiAlternatives(
        subject=mail_subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )

    msg.attach_alternative(full_mail, "text/html")
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
