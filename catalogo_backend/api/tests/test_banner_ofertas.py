"""
Tests para BannerOfertaModel y sus endpoints (worker y público).

Cubre:
- Property `esta_vigente` con distintas combinaciones de activo/fechas.
- `clean()` valida fecha_inicio <= fecha_fin.
- Endpoints worker (list/create/update/destroy) requieren rol worker.
- Validaciones del serializer: tamaño de archivo, extensión, máx 10 activos, fechas.
- Endpoint público expone solo banners activos y vigentes, ordenados por `orden`.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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


def _make_image_file(name: str = "slide.jpg", size_bytes: int = 1024) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"x" * size_bytes, content_type="image/jpeg")


def _make_video_file(name: str = "slide.mp4", size_bytes: int = 1024) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"x" * size_bytes, content_type="video/mp4")


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
