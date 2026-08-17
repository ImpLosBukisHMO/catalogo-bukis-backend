# Aquí van todos los serializers del cliente

# api/serializer/client.py
import warnings

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from api.models import UsuariosModel, BannerOfertaModel, PedidosModel

class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuariosModel
        fields = [
            "id",
            "nombre",
            "apellido",
            "correo",
            "telefono",
            "is_admin",
            "is_staff",
            "is_superuser",
            "worker_role",
            "can_add_products",
            "can_edit_products",
            "can_edit_prices",
            "can_manage_discount_codes",
            "can_apply_discounts",
            "can_manage_offers",
        ]
        read_only_fields = [
            "worker_role",
            "can_add_products",
            "can_edit_products",
            "can_edit_prices",
            "can_manage_discount_codes",
            "can_apply_discounts",
            "can_manage_offers",
        ]


class BannerOfertaPublicSerializer(serializers.ModelSerializer):
    """Vista pública mínima del banner de ofertas para la home."""
    class Meta:
        model = BannerOfertaModel
        fields = ["id", "tipo", "archivo", "orden"]


class MiPedidoComprobanteUpdateSerializer(serializers.ModelSerializer):
    MAX_FILE_BYTES = 10 * 1024 * 1024
    ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
    PILLOW_FORMAT_TO_EXT = {
        "JPEG": {"jpg", "jpeg"},
        "PNG": {"png"},
        "WEBP": {"webp"},
    }

    comprobante_pago = serializers.FileField(required=True, allow_empty_file=False)

    class Meta:
        model = PedidosModel
        fields = ["comprobante_pago"]

    @staticmethod
    def _peek_bytes(uploaded_file, size: int) -> bytes:
        data = b""
        try:
            uploaded_file.seek(0)
            data = uploaded_file.read(size) or b""
        finally:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
        return data

    def _validate_image_content(self, uploaded_file, extension: str) -> None:
        try:
            uploaded_file.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(uploaded_file) as image:
                    image.verify()
                    detected_format = (image.format or "").upper()
        except Image.DecompressionBombError:
            raise serializers.ValidationError(
                {"comprobante_pago": "La imagen es demasiado grande para procesarse."}
            )
        except Image.DecompressionBombWarning:
            raise serializers.ValidationError(
                {"comprobante_pago": "La imagen es demasiado grande para procesarse."}
            )
        except UnidentifiedImageError:
            raise serializers.ValidationError(
                {"comprobante_pago": "El archivo no es una imagen válida."}
            )
        except Exception:
            raise serializers.ValidationError(
                {"comprobante_pago": "El archivo no es una imagen válida."}
            )
        finally:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass

        allowed_exts = self.PILLOW_FORMAT_TO_EXT.get(detected_format)
        if not allowed_exts or extension not in allowed_exts:
            raise serializers.ValidationError(
                {"comprobante_pago": "El contenido del archivo no coincide con su extensión."}
            )

    def _validate_pdf_content(self, uploaded_file) -> None:
        header = self._peek_bytes(uploaded_file, 4)
        if header != b"%PDF":
            raise serializers.ValidationError(
                {"comprobante_pago": "El archivo no es un PDF válido."}
            )

    def validate_comprobante_pago(self, uploaded_file):
        size = getattr(uploaded_file, "size", 0) or 0
        if size > self.MAX_FILE_BYTES:
            raise serializers.ValidationError("El archivo no puede superar 10 MB.")

        content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
        filename = getattr(uploaded_file, "name", "") or ""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if content_type == "application/pdf":
            if extension != "pdf":
                raise serializers.ValidationError("El archivo debe tener extensión .pdf.")
            self._validate_pdf_content(uploaded_file)
            return uploaded_file

        if content_type not in self.ALLOWED_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError(
                "Formato inválido. Usa jpg, png, webp o pdf."
            )

        if extension not in self.ALLOWED_IMAGE_EXTS:
            raise serializers.ValidationError(
                "Formato inválido. Usa jpg, png, webp o pdf."
            )

        self._validate_image_content(uploaded_file, extension)
        return uploaded_file
