import mimetypes
from pathlib import Path

from django.http import FileResponse


def get_comprobante_display_name(comprobante_field) -> str:
    suffix = Path(comprobante_field.name).suffix.lower()
    return f"comprobante{suffix}" if suffix else "comprobante"


def build_comprobante_response(comprobante_field) -> FileResponse:
    content_type, _ = mimetypes.guess_type(comprobante_field.name)
    filename = get_comprobante_display_name(comprobante_field)

    response = FileResponse(
        comprobante_field.open("rb"),
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
