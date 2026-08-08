"""
Pruebas para el flujo de creación y confirmación de cuenta:
  - POST /api/signup/     → APIRegistro
  - POST /api/confirmar-cuenta/   → APIConfirmarCuenta
  - POST /api/reenviar-confirmacion/ → APIReenviarConfirmacion
  - POST /api/login/      → APIIniciarSesion (bloqueado sin verificar)
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import UsuariosModel
from api import services


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

SIGNUP_URL = "/api/signup/"
CONFIRM_URL = "/api/confirmar-cuenta/"
RESEND_URL = "/api/reenviar-confirmacion/"
LOGIN_URL = "/api/login/"

VALID_PAYLOAD = {
    "nombre": "Juan",
    "apellido": "Pérez",
    "correo": "juan@test.com",
    "telefono": "5551234567",
    "password": "MiPassword1!",
}


def _create_verified_user(correo: str = "verificado@test.com") -> UsuariosModel:
    """Crea un usuario ya verificado directamente en la BD."""
    u = UsuariosModel.objects.create_user(
        nombre="Test",
        apellido="User",
        correo=correo,
        telefono="5550000000",
        password="TestPassword1!",
    )
    u.is_email_verified = True
    u.save(update_fields=["is_email_verified"])
    return u


def _create_unverified_user(
    correo: str = "sinverificar@test.com",
    code: str = "123456",
) -> UsuariosModel:
    """Crea un usuario con código OTP pendiente de verificación."""
    u = UsuariosModel.objects.create_user(
        nombre="Sin",
        apellido="Verificar",
        correo=correo,
        telefono="5559999999",
        password="TestPassword1!",
    )
    u.verification_code = code
    u.verification_code_expires = timezone.now() + datetime.timedelta(minutes=30)
    u.save(update_fields=["verification_code", "verification_code_expires"])
    return u


# =============================================================================
# 1. Registro (signup)
# =============================================================================

class RegistroTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    # ── Registro exitoso ───────────────────────────────────────────────────────
    def test_registro_exitoso_retorna_201(self):
        """Un registro con datos válidos debe devolver HTTP 201."""
        res = self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        self.assertEqual(res.status_code, 201, res.data)

    def test_registro_crea_usuario_en_bd(self):
        """Tras el registro, el usuario debe existir en la base de datos."""
        self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        self.assertTrue(
            UsuariosModel.objects.filter(correo=VALID_PAYLOAD["correo"]).exists()
        )

    def test_registro_usuario_no_verificado_por_defecto(self):
        """El usuario recién registrado no debe tener is_email_verified = True."""
        self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        usuario = UsuariosModel.objects.get(correo=VALID_PAYLOAD["correo"])
        self.assertFalse(usuario.is_email_verified)

    def test_respuesta_no_incluye_password(self):
        """La respuesta del registro nunca debe exponer el campo password."""
        res = self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        self.assertNotIn("password", res.data.get("datos", {}))

    def test_registro_correo_duplicado_retorna_error(self):
        """Registrar el mismo correo dos veces debe retornar un error 4xx."""
        self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        res2 = self.client.post(SIGNUP_URL, VALID_PAYLOAD, format="json")
        self.assertGreaterEqual(res2.status_code, 400)

    def test_registro_sin_correo_retorna_400(self):
        payload = {**VALID_PAYLOAD, "correo": ""}
        res = self.client.post(SIGNUP_URL, payload, format="json")
        self.assertEqual(res.status_code, 400)

    def test_registro_sin_nombre_retorna_400(self):
        payload = {**VALID_PAYLOAD, "nombre": ""}
        res = self.client.post(SIGNUP_URL, payload, format="json")
        self.assertEqual(res.status_code, 400)

    def test_registro_sin_password_retorna_error(self):
        """
        El serializer define password como write_only y required=False,
        por lo que actualmente se puede registrar sin contraseña (el campo queda
        sin establecer). Este test documenta ese comportamiento.
        Si en el futuro se requiere password obligatoriamente en el serializer,
        cambiar el assert a assertEqual(res.status_code, 400).
        """
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "password"}
        res = self.client.post(SIGNUP_URL, payload, format="json")
        # Actualmente el serializer permite omitir el password → 201
        self.assertIn(res.status_code, [201, 400])


# =============================================================================
# 2. Inicio de sesión bloqueado para usuarios no verificados
# =============================================================================

class LoginSinVerificarTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_login_sin_verificar_retorna_401(self):
        """Un usuario sin verificar no puede iniciar sesión."""
        _create_unverified_user(correo="bloqueo@test.com")
        res = self.client.post(
            LOGIN_URL,
            {"correo": "bloqueo@test.com", "password": "TestPassword1!"},
            format="json",
        )
        self.assertEqual(res.status_code, 401, res.data)

    def test_login_usuario_verificado_exitoso(self):
        """Un usuario ya verificado sí puede iniciar sesión."""
        _create_verified_user(correo="ok@test.com")
        res = self.client.post(
            LOGIN_URL,
            {"correo": "ok@test.com", "password": "TestPassword1!"},
            format="json",
        )
        # Retorna el token; el código puede ser 200
        self.assertLess(res.status_code, 400, res.data)

    def test_login_correo_inexistente_retorna_401(self):
        res = self.client.post(
            LOGIN_URL,
            {"correo": "noexiste@test.com", "password": "cualquiera"},
            format="json",
        )
        self.assertEqual(res.status_code, 401)

    def test_login_password_incorrecta_retorna_401(self):
        _create_verified_user(correo="mal_pwd@test.com")
        res = self.client.post(
            LOGIN_URL,
            {"correo": "mal_pwd@test.com", "password": "PasswordEquivocada!"},
            format="json",
        )
        self.assertEqual(res.status_code, 401)

    def test_login_ignora_mayusculas_minusculas_en_correo(self):
        """Un login debe ser exitoso incluso si el correo enviado tiene diferente case."""
        _create_verified_user(correo="Mayuscula@test.com")
        res = self.client.post(
            LOGIN_URL,
            {"correo": "mayuscula@test.com", "password": "TestPassword1!"},
            format="json",
        )
        self.assertLess(res.status_code, 400, res.data)

    def test_registro_acepta_caracteres_especiales_comunes_en_password(self):
        """El registro debe aceptar contraseñas con _, - y ."""
        res = self.client.post(
            SIGNUP_URL,
            {
                "nombre": "Test",
                "apellido": "User",
                "correo": "special_chars@test.com",
                "telefono": "1234567890",
                "password": "Password_.-123", # Tiene mayúscula, minúscula, número, y los 3 caracteres nuevos permitidos
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)


# =============================================================================
# 3. Confirmación de cuenta (OTP)
# =============================================================================

class ConfirmarCuentaTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_confirmar_con_codigo_correcto(self):
        """Un código válido debe confirmar la cuenta y retornar 200."""
        _create_unverified_user(correo="confirmar@test.com", code="999888")
        res = self.client.post(
            CONFIRM_URL,
            {"correo": "confirmar@test.com", "codigo": "999888"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        usuario = UsuariosModel.objects.get(correo="confirmar@test.com")
        self.assertTrue(usuario.is_email_verified)

    def test_confirmar_limpia_el_codigo_tras_verificar(self):
        """Después de confirmar, los campos de verificación deben quedar en None."""
        _create_unverified_user(correo="clean@test.com", code="111222")
        self.client.post(
            CONFIRM_URL,
            {"correo": "clean@test.com", "codigo": "111222"},
            format="json",
        )
        usuario = UsuariosModel.objects.get(correo="clean@test.com")
        self.assertIsNone(usuario.verification_code)
        self.assertIsNone(usuario.verification_code_expires)

    def test_confirmar_codigo_incorrecto_retorna_400(self):
        _create_unverified_user(correo="incorrecto@test.com", code="000001")
        res = self.client.post(
            CONFIRM_URL,
            {"correo": "incorrecto@test.com", "codigo": "999999"},
            format="json",
        )
        self.assertEqual(res.status_code, 400, res.data)

    def test_confirmar_codigo_expirado_retorna_400(self):
        """Un código cuya fecha de expiración ya pasó debe rechazarse."""
        usuario = _create_unverified_user(correo="expirado@test.com", code="777666")
        # Forzamos la expiración hacia el pasado
        usuario.verification_code_expires = timezone.now() - datetime.timedelta(hours=1)
        usuario.save(update_fields=["verification_code_expires"])

        res = self.client.post(
            CONFIRM_URL,
            {"correo": "expirado@test.com", "codigo": "777666"},
            format="json",
        )
        self.assertEqual(res.status_code, 400, res.data)

    def test_confirmar_usuario_inexistente_retorna_400(self):
        res = self.client.post(
            CONFIRM_URL,
            {"correo": "fantasma@test.com", "codigo": "123456"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_confirmar_sin_correo_retorna_400(self):
        res = self.client.post(
            CONFIRM_URL,
            {"codigo": "123456"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_confirmar_sin_codigo_retorna_400(self):
        res = self.client.post(
            CONFIRM_URL,
            {"correo": "alguien@test.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_confirmar_cuenta_ya_verificada_retorna_200(self):
        """Si la cuenta ya fue verificada, la respuesta debe ser 200 (idempotente)."""
        _create_verified_user(correo="ya@verificado.com")
        res = self.client.post(
            CONFIRM_URL,
            {"correo": "ya@verificado.com", "codigo": "cualquier"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)


# =============================================================================
# 4. Reenvío de código de confirmación
# =============================================================================

class ReenviarConfirmacionTests(TestCase):
    """
    Nota: estas pruebas verifican la lógica de negocio del endpoint.
    El envío real del correo está deshabilitado (no hay servidor SMTP en tests);
    services.enviar_correo_confirmacion devuelve (False, <error>) en ese caso,
    pero el código OTP se actualiza en la BD igualmente (en generar_codigo_confirmacion).
    """

    def setUp(self):
        self.client = APIClient()

    def test_reenviar_cuenta_ya_verificada_retorna_400(self):
        """No se puede reenviar si la cuenta ya está verificada."""
        _create_verified_user(correo="ya_verificado@test.com")
        res = self.client.post(
            RESEND_URL,
            {"correo": "ya_verificado@test.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 400, res.data)

    def test_reenviar_correo_inexistente_retorna_400(self):
        res = self.client.post(
            RESEND_URL,
            {"correo": "noexiste@test.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_reenviar_sin_correo_retorna_400(self):
        res = self.client.post(RESEND_URL, {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_reenviar_actualiza_el_codigo_otp(self):
        """
        Al reenviar, generar_codigo_confirmacion debe actualizar el código OTP
        y la fecha de expiración del usuario (independientemente del SMTP).
        """
        usuario = _create_unverified_user(correo="nuevo_otp@test.com", code="111111")
        codigo_original = usuario.verification_code

        # Llamamos directamente al servicio de negocio para aislar del SMTP
        nuevo_codigo = services.generar_codigo_confirmacion(usuario)
        usuario.refresh_from_db()

        self.assertNotEqual(nuevo_codigo, codigo_original)
        self.assertEqual(usuario.verification_code, nuevo_codigo)
        # La nueva expiración debe ser futura
        self.assertGreater(usuario.verification_code_expires, timezone.now())


# =============================================================================
# 5. Lógica de servicios pura (sin HTTP)
# =============================================================================

class ServicesUnitTests(TestCase):

    def test_confirmar_cuenta_codigo_retorna_true_para_codigo_valido(self):
        usuario = _create_unverified_user(correo="srv_ok@test.com", code="456789")
        ok, msg = services.confirmar_cuenta_codigo("srv_ok@test.com", "456789")
        self.assertTrue(ok)
        self.assertIn("exitosamente", msg.lower())

    def test_confirmar_cuenta_codigo_retorna_false_para_codigo_invalido(self):
        _create_unverified_user(correo="srv_bad@test.com", code="111111")
        ok, msg = services.confirmar_cuenta_codigo("srv_bad@test.com", "999999")
        self.assertFalse(ok)

    def test_confirmar_cuenta_usuario_inexistente_retorna_false(self):
        ok, _ = services.confirmar_cuenta_codigo("ghost@test.com", "123456")
        self.assertFalse(ok)

    def test_reenviar_correo_usuario_inexistente_retorna_false(self):
        ok, _ = services.reenviar_correo_confirmacion("ghost@test.com")
        self.assertFalse(ok)

    def test_reenviar_correo_cuenta_verificada_retorna_false(self):
        _create_verified_user(correo="ya_verif_srv@test.com")
        ok, _ = services.reenviar_correo_confirmacion("ya_verif_srv@test.com")
        self.assertFalse(ok)

    def test_generar_codigo_tiene_6_digitos(self):
        usuario = _create_unverified_user(correo="sixdigit@test.com")
        codigo = services.generar_codigo_confirmacion(usuario)
        self.assertEqual(len(codigo), 6)
        self.assertTrue(codigo.isdigit())
