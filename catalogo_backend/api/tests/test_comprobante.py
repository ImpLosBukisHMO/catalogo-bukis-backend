import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import PedidosModel, UsuariosModel
from api.serializers import ClientePedidoSerializer
from api.serializer.worker import WorkerPedidoDetalleSerializer


def create_user(*, email: str, staff: bool = False) -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=email,
        telefono="5551234567",
        password="testpass123",
        staff=staff,
    )


def image_bytes(*, image_format: str, size: tuple[int, int] = (32, 32)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(50, 100, 150)).save(buffer, format=image_format)
    return buffer.getvalue()


def image_file(name: str, *, image_format: str, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        image_bytes(image_format=image_format),
        content_type=content_type,
    )


def pdf_file(name: str = "comprobante.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n",
        content_type="application/pdf",
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MiPedidoComprobanteUploadTest(TestCase):
    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.media_override.enable()

        self.owner = create_user(email="owner@test.com")
        self.other_cliente = create_user(email="other@test.com")
        self.worker = create_user(email="worker@test.com", staff=True)
        self.pedido = PedidosModel.objects.create(
            cliente=self.owner,
            clave="PEDIDO-001",
            estado=PedidosModel.EstadoPedido.APROBADO,
            subtotal_snapshot=100,
            precio_total=120,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.url = f"/api/mis-pedidos/{self.pedido.id}/comprobante/"
        self.worker_url = f"/api/worker/pedidos/{self.pedido.id}/comprobante/"
        self.client = APIClient()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def auth(self, user: UsuariosModel) -> None:
        self.client.force_authenticate(user=user)

    def patch_file(self, uploaded_file: SimpleUploadedFile):
        return self.client.patch(
            self.url,
            {"comprobante_pago": uploaded_file},
            format="multipart",
        )

    def test_requires_authentication(self):
        response = self.patch_file(
            image_file("comprobante.jpg", image_format="JPEG", content_type="image/jpeg")
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_non_owner_cliente(self):
        self.auth(self.other_cliente)

        response = self.patch_file(
            image_file("comprobante.jpg", image_format="JPEG", content_type="image/jpeg")
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_worker_using_cliente_endpoint(self):
        self.auth(self.worker)

        response = self.patch_file(
            image_file("comprobante.jpg", image_format="JPEG", content_type="image/jpeg")
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_upload_when_pedido_is_not_approved(self):
        self.auth(self.owner)
        self.pedido.estado = PedidosModel.EstadoPedido.PENDIENTE
        self.pedido.save(update_fields=["estado", "updated_at"])

        response = self.patch_file(
            image_file("comprobante.jpg", image_format="JPEG", content_type="image/jpeg")
        )

        self.assertIn(response.status_code, {status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT})

    def test_accepts_valid_jpeg_png_webp_and_pdf(self):
        self.auth(self.owner)

        valid_files = [
            image_file("comprobante.jpg", image_format="JPEG", content_type="image/jpeg"),
            image_file("comprobante.png", image_format="PNG", content_type="image/png"),
            image_file("comprobante.webp", image_format="WEBP", content_type="image/webp"),
            pdf_file(),
        ]

        for uploaded_file in valid_files:
            response = self.patch_file(uploaded_file)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.pedido.refresh_from_db()
            self.assertTrue(bool(self.pedido.comprobante_pago))

    def test_rejects_missing_file(self):
        self.auth(self.owner)

        response = self.client.patch(self.url, {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_extension_content_mismatch(self):
        self.auth(self.owner)

        response = self.patch_file(
            image_file("comprobante.jpg", image_format="PNG", content_type="image/jpeg")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_fake_image_payload(self):
        self.auth(self.owner)

        response = self.patch_file(
            SimpleUploadedFile(
                "comprobante.jpg",
                b"not a real image",
                content_type="image/jpeg",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_invalid_pdf_magic_bytes(self):
        self.auth(self.owner)

        response = self.patch_file(
            SimpleUploadedFile(
                "comprobante.pdf",
                b"NOTPDF",
                content_type="application/pdf",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_oversized_file(self):
        self.auth(self.owner)
        oversized_payload = b"%PDF" + b"0" * ((10 * 1024 * 1024) + 1)

        response = self.patch_file(
            SimpleUploadedFile(
                "comprobante.pdf",
                oversized_payload,
                content_type="application/pdf",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_disallowed_file_type(self):
        self.auth(self.owner)

        response = self.patch_file(
            SimpleUploadedFile(
                "comprobante.zip",
                b"PK\x03\x04",
                content_type="application/zip",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_rejects_decompression_bomb_image(self):
        self.auth(self.owner)

        with patch("PIL.Image.open", side_effect=Image.DecompressionBombError("boom")):
            response = self.patch_file(
                image_file("comprobante.png", image_format="PNG", content_type="image/png")
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("comprobante_pago", response.json())

    def test_replacement_removes_previous_file(self):
        self.auth(self.owner)
        first_response = self.patch_file(
            image_file("comprobante-1.jpg", image_format="JPEG", content_type="image/jpeg")
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK, first_response.content)

        self.pedido.refresh_from_db()
        old_name = self.pedido.comprobante_pago.name
        old_path = Path(self.pedido.comprobante_pago.path)
        self.assertTrue(old_path.exists())

        second_response = self.patch_file(pdf_file("comprobante-2.pdf"))
        self.assertEqual(second_response.status_code, status.HTTP_200_OK, second_response.content)

        self.pedido.refresh_from_db()
        self.assertNotEqual(self.pedido.comprobante_pago.name, old_name)
        self.assertFalse(old_path.exists())

    def test_owner_can_download_comprobante_from_protected_route(self):
        self.auth(self.owner)
        upload_response = self.patch_file(pdf_file())
        self.assertEqual(upload_response.status_code, status.HTTP_200_OK, upload_response.content)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="comprobante.pdf"', response["Content-Disposition"])

    def test_rejects_non_owner_cliente_downloading_comprobante(self):
        self.auth(self.owner)
        upload_response = self.patch_file(pdf_file())
        self.assertEqual(upload_response.status_code, status.HTTP_200_OK, upload_response.content)

        self.auth(self.other_cliente)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_worker_can_download_comprobante_from_worker_route(self):
        self.auth(self.owner)
        upload_response = self.patch_file(pdf_file())
        self.assertEqual(upload_response.status_code, status.HTTP_200_OK, upload_response.content)

        self.auth(self.worker)
        response = self.client.get(self.worker_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_cliente_serializer_and_worker_serializer_expose_only_protected_metadata(self):
        self.auth(self.owner)
        response = self.patch_file(pdf_file())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        self.pedido.refresh_from_db()
        cliente_data = ClientePedidoSerializer(self.pedido).data
        worker_data = WorkerPedidoDetalleSerializer(self.pedido).data

        self.assertNotIn("comprobante_pago", cliente_data)
        self.assertNotIn("comprobante_pago", worker_data)
        self.assertTrue(cliente_data["comprobante_pago_subido"])
        self.assertTrue(worker_data["comprobante_pago_subido"])
        self.assertEqual(cliente_data["comprobante_pago_nombre"], "comprobante.pdf")
        self.assertEqual(worker_data["comprobante_pago_nombre"], "comprobante.pdf")
        self.assertEqual(cliente_data["comprobante_pago_url"], self.url)
        self.assertEqual(worker_data["comprobante_pago_url"], self.worker_url)
        self.assertNotIn("/media/", cliente_data["comprobante_pago_url"])
        self.assertNotIn("/media/", worker_data["comprobante_pago_url"])

    def test_logs_warning_when_previous_file_delete_fails(self):
        self.auth(self.owner)
        first_response = self.patch_file(
            image_file("comprobante-1.jpg", image_format="JPEG", content_type="image/jpeg")
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK, first_response.content)

        self.pedido.refresh_from_db()
        with patch.object(self.pedido.comprobante_pago.storage, "delete", side_effect=OSError("boom")), patch(
            "api.views.pedidosViews.logger",
            create=True,
        ) as mocked_logger:
            second_response = self.patch_file(pdf_file("comprobante-2.pdf"))

        self.assertEqual(second_response.status_code, status.HTTP_200_OK, second_response.content)
        mocked_logger.warning.assert_called()

    def test_smtp_failure_does_not_roll_back_upload(self):
        self.auth(self.owner)

        with patch(
            "api.views.pedidosViews.send_comprobante_pago_worker_email",
            side_effect=RuntimeError("smtp down"),
            create=True,
        ), patch("api.views.pedidosViews.logger", create=True) as mocked_logger:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.patch_file(pdf_file())

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.pedido.refresh_from_db()
        self.assertTrue(bool(self.pedido.comprobante_pago))
        mocked_logger.exception.assert_called()
