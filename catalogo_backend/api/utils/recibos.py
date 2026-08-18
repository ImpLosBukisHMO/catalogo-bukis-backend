from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import override
from xhtml2pdf import pisa


RECIBO_ALLOWED_STATES = frozenset({"APPROVED", "READY", "SHIPPED", "COMPLETED"})


def _format_fecha(created_at) -> str:
    with override("es-mx"):
        return date_format(localtime(created_at), r"j \d\e F, Y — H:i", use_l10n=True)


def render_recibo_html(pedido) -> str:
    direccion = pedido.direccion
    cliente = pedido.cliente
    context = {
        "business_name": "Importaciones Los Bukis",
        "folio": pedido.folio,
        "fecha": _format_fecha(pedido.created_at),
        "estado_label": pedido.get_estado_display(),
        "cliente": {
            "nombre": f"{cliente.nombre} {cliente.apellido}".strip(),
            "email": cliente.correo,
            "telefono": cliente.telefono,
        },
        "direccion": direccion,
        "items": pedido.items.all(),
        "subtotal": pedido.subtotal_snapshot,
        "total": pedido.precio_total,
    }
    return render_to_string("recibo/recibo_pedido.html", context)


def render_recibo_pdf_bytes(html: str) -> bytes:
    output = BytesIO()
    result = pisa.CreatePDF(src=html, dest=output, encoding="utf-8")
    if result.err:
        raise RuntimeError("Failed to render receipt PDF")
    return output.getvalue()


def build_recibo_pdf_response(pdf_bytes: bytes, folio: str) -> HttpResponse:
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="recibo-{folio}.pdf"'
    return response


def build_recibo_response_for_pedido(pedido) -> HttpResponse:
    html = render_recibo_html(pedido)
    pdf_bytes = render_recibo_pdf_bytes(html)
    return build_recibo_pdf_response(pdf_bytes, pedido.folio)
