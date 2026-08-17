"""
Pruebas para el flujo de recuperación de contraseña:
  - POST /api/recuperar-password/solicitar/  → APISolicitarRecuperacion
  - POST /api/recuperar-password/confirmar/  → APIConfirmarRecuperacion
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import UsuariosModel
from api import services


# ─────────────────────────────────────────────────────────────────────────────
# URLs y helpers
# ─────────────────────────────────────────────────────────────────────────────

SOLICITAR_URL = "/api/recuperar-password/solicitar/"
CONFIRMAR_URL = "/api/recuperar-password/confirmar/"


def _create_verified_user(
    correo: str = "recovery@test.com",
    password: str = "TestPassword1!",
) -> UsuariosModel:
    u = UsuariosModel.objects.create_user(
        nombre="Recovery",
        apellido="Test",
        correo=correo,
        telefono="5550000000",
        password=password,
    )
    u.is_email_verified = True
    u.save(update_fields=["is_email_verified"])
    return u


def _create_user_with_recovery_code(
    correo: str = "withcode@test.com",
    code: str = "123456",
    password: str = "TestPassword1!",
    expired: bool = False,
) -> UsuariosModel:
    u = UsuariosModel.objects.create_user(
        nombre="Recovery",
        apellido="Code",
        correo=correo,
        telefono="5550000000",
        password=password,
    )
    u.verification_code = code
    if expired:
        u.verification_code_expires = timezone.now() - datetime.timedelta(hours=1)
    else:
        u.verification_code_expires = timezone.now() + datetime.timedelta(minutes=30)
    u.save(update_fields=["verification_code", "verification_code_expires"])
    return u


# =============================================================================
# 1. Solicitar recuperación
# =============================================================================

class SolicitarRecuperacionTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_solicitar_correo_existente_retorna_200(self):
        """Siempre devuelve 200 con el mismo mensaje genérico."""
        _create_verified_user(correo="existe@test.com")
        res = self.client.post(SOLICITAR_URL, {"correo": "existe@test.com"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("recibirás", res.data.get("mensaje", ""))

    def test_solicitar_correo_inexistente_retorna_200(self):
        """Anti-enumeración: misma respuesta para correos no registrados."""
        res = self.client.post(SOLICITAR_URL, {"correo": "noexiste@test.com"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("recibirás", res.data.get("mensaje", ""))

    def test_solicitar_sin_correo_retorna_400(self):
        res = self.client.post(SOLICITAR_URL, {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_solicitar_genera_codigo_otp_en_bd(self):
        """Al solicitar, se debe generar un código OTP en la BD del usuario."""
        usuario = _create_verified_user(correo="otpgen@test.com")
        self.assertIsNone(usuario.verification_code)

        self.client.post(SOLICITAR_URL, {"correo": "otpgen@test.com"}, format="json")
        usuario.refresh_from_db()
        self.assertIsNotNone(usuario.verification_code)
        self.assertEqual(len(usuario.verification_code), 6)
        self.assertTrue(usuario.verification_code.isdigit())


# =============================================================================
# 2. Confirmar recuperación (cambiar contraseña)
# =============================================================================

class ConfirmarRecuperacionTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_confirmar_con_codigo_correcto_cambia_password(self):
        usuario = _create_user_with_recovery_code(correo="ok@test.com", code="111111")
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "ok@test.com",
            "codigo": "111111",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 200, res.data)

        # Verificar que la contraseña realmente cambió
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("NuevaSegura1!"))

    def test_confirmar_con_codigo_incorrecto_retorna_400(self):
        _create_user_with_recovery_code(correo="bad@test.com", code="111111")
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "bad@test.com",
            "codigo": "999999",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_confirmar_con_codigo_expirado_retorna_400(self):
        _create_user_with_recovery_code(
            correo="expirado@test.com", code="222222", expired=True,
        )
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "expirado@test.com",
            "codigo": "222222",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_confirmar_sin_campos_requeridos_retorna_400(self):
        # Sin correo
        res = self.client.post(CONFIRMAR_URL, {
            "codigo": "111111",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 400)

        # Sin código
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "alguien@test.com",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 400)

        # Sin nueva_password
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "alguien@test.com",
            "codigo": "111111",
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_confirmar_con_password_debil_retorna_400(self):
        """La nueva contraseña debe cumplir las reglas de complejidad."""
        _create_user_with_recovery_code(correo="debil@test.com", code="333333")
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "debil@test.com",
            "codigo": "333333",
            "nueva_password": "12345",  # Muy corta, sin mayúsculas, sin especiales
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_confirmar_verifica_cuenta_automaticamente(self):
        """Al restablecer contraseña, is_email_verified debe quedar True."""
        usuario = _create_user_with_recovery_code(correo="verify@test.com", code="444444")
        self.assertFalse(usuario.is_email_verified)

        self.client.post(CONFIRMAR_URL, {
            "correo": "verify@test.com",
            "codigo": "444444",
            "nueva_password": "NuevaSegura1!",
        }, format="json")

        usuario.refresh_from_db()
        self.assertTrue(usuario.is_email_verified)

    def test_confirmar_limpia_codigo_y_expiracion(self):
        """Tras restablecer, los campos de verificación deben quedar en None."""
        _create_user_with_recovery_code(correo="limpio@test.com", code="555555")
        self.client.post(CONFIRMAR_URL, {
            "correo": "limpio@test.com",
            "codigo": "555555",
            "nueva_password": "NuevaSegura1!",
        }, format="json")

        usuario = UsuariosModel.objects.get(correo="limpio@test.com")
        self.assertIsNone(usuario.verification_code)
        self.assertIsNone(usuario.verification_code_expires)

    def test_confirmar_usuario_inexistente_retorna_400(self):
        res = self.client.post(CONFIRMAR_URL, {
            "correo": "fantasma@test.com",
            "codigo": "111111",
            "nueva_password": "NuevaSegura1!",
        }, format="json")
        self.assertEqual(res.status_code, 400)
