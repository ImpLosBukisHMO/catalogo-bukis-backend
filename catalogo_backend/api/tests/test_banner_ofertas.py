"""
Tests para BannerOfertaModel y sus endpoints (worker y público).

Cubre:
- Property `esta_vigente` con distintas combinaciones de activo/fechas.
- `clean()` valida fecha_inicio <= fecha_fin.
- Endpoints worker (list/create/update/destroy) requieren rol worker.
- Validaciones del serializer: tamaño, extensión, contenido real (Pillow + magic
  numbers), máx 10 activos (incluye caso omitiendo el campo), consistencia de
  tipo en PATCH, fechas.
- Endpoint público expone solo banners activos y vigentes, ordenados por `orden`.
"""
import io
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from api.models import BannerOfertaModel, UsuariosModel


# =========================
# Helpers
# =========================

def _create_user(email: str, staff: bool = False) -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="Banner",
        correo=email,
        telefono="555-0000000",
        password="testpass123",
        staff=staff,
    )


def _image_bytes(format: str = "JPEG", size=(16, 16)) -> bytes:
    """Genera bytes de imagen real usando Pillow."""
    buf = io.BytesIO()
    Image.new("RGB", size, color=(200, 30, 30)).save(buf, format=format)
    return buf.getvalue()


def _make_image_file(
    name: str = "slide.jpg",
    size_bytes: int | None = None,
    format: str = "JPEG",
) -> SimpleUploadedFile:
    """
    Genera un archivo de imagen válido. Si `size_bytes` se pide (para test de
    tamaño), padea con un chunk final de datos para inflar sin corromper el header.
    Pillow ya valida el header al inicio del archivo.
    """
    payload = _image_bytes(format=format)
    if size_bytes is not None and size_bytes > len(payload):
        payload = payload + b"\x00" * (size_bytes - len(payload))
    return SimpleUploadedFile(name, payload, content_type="image/jpeg")


def _make_video_file(
    name: str = "slide.mp4",
    size_bytes: int | None = None,
    container: str = "mp4",
) -> SimpleUploadedFile:
    """
    Genera un archivo con magic numbers válidos de contenedor mp4/webm.
    Es contenido mínimo (no reproducible), pero pasa la validación magic-number.
    """
    if container == "mp4":
        # 4 bytes size + 'ftyp' + 'isom' + 4 bytes minor version + brands
        header = (
            b"\x00\x00\x00\x20"  # box size 32
            + b"ftyp"
            + b"isom"
            + b"\x00\x00\x02\x00"
            + b"isomiso2mp41"
        )
    elif container == "webm":
        # EBML header (0x1A45DFA3)
        header = b"\x1a\x45\xdf\xa3" + b"\x01\x00\x00\x00" + b"\x00" * 24
    else:
        raise ValueError(f"container desconocido: {container}")

    payload = header
    if size_bytes is not None and size_bytes > len(payload):
        payload = payload + b"\x00" * (size_bytes - len(payload))
    return SimpleUploadedFile(name, payload, content_type=f"video/{container}")


def _create_banner(**overrides) -> BannerOfertaModel:
    defaults = {
        "tipo": BannerOfertaModel.MediaType.IMAGEN,
        "archivo": _make_image_file(),
        "orden": 0,
        "activo": True,
    }
    defaults.update(overrides)
    return BannerOfertaModel.objects.create(**defaults)


# =========================
# Model
# =========================

class BannerOfertaModelTest(TestCase):
    def test_esta_vigente_false_when_activo_false(self):
        banner = _create_banner(activo=False)
        self.assertFalse(banner.esta_vigente)

    def test_esta_vigente_false_when_fecha_inicio_futura(self):
        banner = _create_banner(
            activo=True,
            fecha_inicio=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(banner.esta_vigente)

    def test_esta_vigente_false_when_fecha_fin_pasada(self):
        banner = _create_banner(
            activo=True,
            fecha_fin=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(banner.esta_vigente)

    def test_esta_vigente_true_when_activo_sin_fechas(self):
        banner = _create_banner(activo=True)
        self.assertTrue(banner.esta_vigente)

    def test_esta_vigente_true_dentro_de_ventana(self):
        now = timezone.now()
        banner = _create_banner(
            activo=True,
            fecha_inicio=now - timedelta(days=1),
            fecha_fin=now + timedelta(days=1),
        )
        self.assertTrue(banner.esta_vigente)

    def test_clean_rechaza_fecha_inicio_posterior_a_fin(self):
        now = timezone.now()
        banner = BannerOfertaModel(
            tipo=BannerOfertaModel.MediaType.IMAGEN,
            archivo=_make_image_file(),
            fecha_inicio=now + timedelta(days=2),
            fecha_fin=now + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            banner.clean()


# =========================
# Endpoints worker
# =========================

class WorkerBannerOfertasEndpointTest(TestCase):
    def setUp(self):
        self.worker = _create_user("worker@bukis.mx", staff=True)
        self.client_user = _create_user("cliente@bukis.mx", staff=False)
        self.api = APIClient()
        self.list_url = reverse("worker-banner-ofertas")

    def _auth_worker(self):
        self.api.force_authenticate(user=self.worker)

    def _auth_cliente(self):
        self.api.force_authenticate(user=self.client_user)

    def test_cliente_no_puede_listar(self):
        self._auth_cliente()
        resp = self.api.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cliente_no_puede_crear(self):
        self._auth_cliente()
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": _make_image_file(), "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonimo_no_puede_listar_worker(self):
        resp = self.api.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_worker_puede_crear_imagen_valida(self):
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": _make_image_file(), "orden": 5, "activo": True},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(BannerOfertaModel.objects.count(), 1)

    def test_worker_puede_crear_video_valido(self):
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {"tipo": "video", "archivo": _make_video_file(), "orden": 1, "activo": True},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

    def test_worker_puede_listar(self):
        _create_banner()
        _create_banner(orden=1)
        self._auth_worker()
        resp = self.api.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Puede venir paginado o no; contemplar ambos
        data = resp.json()
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        self.assertEqual(len(data), 2)

    def test_worker_puede_actualizar_orden_y_activo(self):
        banner = _create_banner(orden=0, activo=True)
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        resp = self.api.patch(detail_url, {"orden": 9, "activo": False}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        banner.refresh_from_db()
        self.assertEqual(banner.orden, 9)
        self.assertFalse(banner.activo)

    def test_worker_puede_eliminar(self):
        banner = _create_banner()
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        resp = self.api.delete(detail_url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BannerOfertaModel.objects.filter(id=banner.id).exists())

    def test_no_permite_mas_de_10_activos(self):
        for i in range(10):
            _create_banner(orden=i, activo=True)
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": _make_image_file(), "orden": 11, "activo": True},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BannerOfertaModel.objects.filter(activo=True).count(), 10)

    def test_permite_11avo_inactivo(self):
        for i in range(10):
            _create_banner(orden=i, activo=True)
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": _make_image_file(), "orden": 11, "activo": False},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

    def test_video_sobre_20mb_rechazado(self):
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {
                "tipo": "video",
                "archivo": _make_video_file(size_bytes=20 * 1024 * 1024 + 1),
                "orden": 1,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_imagen_sobre_5mb_rechazada(self):
        self._auth_worker()
        resp = self.api.post(
            self.list_url,
            {
                "tipo": "imagen",
                "archivo": _make_image_file(size_bytes=5 * 1024 * 1024 + 1),
                "orden": 1,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extension_invalida_video(self):
        self._auth_worker()
        bad_file = SimpleUploadedFile("slide.avi", b"x" * 1024, content_type="video/avi")
        resp = self.api.post(
            self.list_url,
            {"tipo": "video", "archivo": bad_file, "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extension_invalida_imagen(self):
        self._auth_worker()
        bad_file = SimpleUploadedFile("slide.bmp", b"x" * 1024, content_type="image/bmp")
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": bad_file, "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contenido_no_es_imagen_real(self):
        """Un archivo llamado .jpg pero con contenido basura debe rechazarse."""
        self._auth_worker()
        fake = SimpleUploadedFile("slide.jpg", b"\x00" * 2048, content_type="image/jpeg")
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": fake, "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contenido_imagen_formato_distinto_a_extension(self):
        """Un PNG guardado como .jpg debe rechazarse (mismatch contenido/extensión)."""
        self._auth_worker()
        png_bytes_as_jpg = SimpleUploadedFile(
            "slide.jpg", _image_bytes(format="PNG"), content_type="image/jpeg"
        )
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": png_bytes_as_jpg, "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contenido_no_es_video_real(self):
        """Un archivo llamado .mp4 pero sin magic numbers válidos debe rechazarse."""
        self._auth_worker()
        fake = SimpleUploadedFile("slide.mp4", b"\x00" * 2048, content_type="video/mp4")
        resp = self.api.post(
            self.list_url,
            {"tipo": "video", "archivo": fake, "orden": 1},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_permite_11avo_activo_omitiendo_campo_activo(self):
        """El default=True del modelo NO debe bypassear el límite de 10 activos."""
        for i in range(10):
            _create_banner(orden=i, activo=True)
        self._auth_worker()
        # Nótese: NO se envía 'activo' → default es True
        resp = self.api.post(
            self.list_url,
            {"tipo": "imagen", "archivo": _make_image_file(), "orden": 11},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BannerOfertaModel.objects.filter(activo=True).count(), 10)

    def test_patch_activar_cuando_ya_hay_10_activos_falla(self):
        """Actualizar un slide inactivo a activo cuando ya hay 10 activos debe fallar."""
        for i in range(10):
            _create_banner(orden=i, activo=True)
        inactivo = _create_banner(orden=99, activo=False)
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[inactivo.id])
        resp = self.api.patch(detail_url, {"activo": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_cambiar_tipo_sin_archivo_falla(self):
        """Cambiar tipo (imagen→video) sin re-subir archivo debe rechazarse."""
        banner = _create_banner(
            tipo=BannerOfertaModel.MediaType.IMAGEN, archivo=_make_image_file()
        )
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        resp = self.api.patch(detail_url, {"tipo": "video"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_cambiar_tipo_con_archivo_valido_funciona(self):
        banner = _create_banner(
            tipo=BannerOfertaModel.MediaType.IMAGEN, archivo=_make_image_file()
        )
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        resp = self.api.patch(
            detail_url,
            {"tipo": "video", "archivo": _make_video_file()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        banner.refresh_from_db()
        self.assertEqual(banner.tipo, BannerOfertaModel.MediaType.VIDEO)

    def test_patch_solo_orden_no_dispara_validacion_de_archivo(self):
        """Un PATCH solo con orden no debe requerir re-subir archivo."""
        banner = _create_banner(orden=0)
        self._auth_worker()
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        resp = self.api.patch(detail_url, {"orden": 7}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

    def test_fechas_invalidas_rechazadas(self):
        self._auth_worker()
        now = timezone.now()
        resp = self.api.post(
            self.list_url,
            {
                "tipo": "imagen",
                "archivo": _make_image_file(),
                "orden": 1,
                "fecha_inicio": (now + timedelta(days=2)).isoformat(),
                "fecha_fin": (now + timedelta(days=1)).isoformat(),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# =========================
# Endpoint público
# =========================

class BannerOfertasPublicEndpointTest(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.url = reverse("banner-ofertas-public")

    def test_anonimo_puede_listar(self):
        _create_banner(orden=0, activo=True)
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_solo_activos(self):
        _create_banner(orden=0, activo=True)
        _create_banner(orden=1, activo=False)
        resp = self.api.get(self.url)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["orden"], 0)

    def test_oculta_futuros(self):
        _create_banner(
            orden=0,
            activo=True,
            fecha_inicio=timezone.now() + timedelta(days=1),
        )
        resp = self.api.get(self.url)
        self.assertEqual(len(resp.json()), 0)

    def test_oculta_expirados(self):
        _create_banner(
            orden=0,
            activo=True,
            fecha_fin=timezone.now() - timedelta(days=1),
        )
        resp = self.api.get(self.url)
        self.assertEqual(len(resp.json()), 0)

    def test_muestra_sin_fechas(self):
        _create_banner(orden=0, activo=True)
        resp = self.api.get(self.url)
        self.assertEqual(len(resp.json()), 1)

    def test_orden_ascendente(self):
        _create_banner(orden=2, activo=True)
        _create_banner(orden=0, activo=True)
        _create_banner(orden=1, activo=True)
        resp = self.api.get(self.url)
        data = resp.json()
        ordenes = [item["orden"] for item in data]
        self.assertEqual(ordenes, [0, 1, 2])

    def test_incluye_campos_publicos(self):
        _create_banner(orden=0, activo=True)
        resp = self.api.get(self.url)
        item = resp.json()[0]
        self.assertIn("id", item)
        self.assertIn("tipo", item)
        self.assertIn("archivo", item)
        self.assertIn("orden", item)
        # No debe filtrarse info de administración
        self.assertNotIn("activo", item)
        self.assertNotIn("fecha_inicio", item)
