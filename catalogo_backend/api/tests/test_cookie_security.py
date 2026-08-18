"""
Tests de regresión para atributos de seguridad de cookies de auth.

Contexto: en producción el frontend y el backend viven en dominios distintos
(cross-site). Los navegadores modernos rechazan silenciosamente las cookies
que no cumplen `SameSite=None; Secure` en contexto cross-site, rompiendo el
login. Este archivo asegura que login, refresh y logout emiten las cookies
con los atributos correctos según el entorno (DEBUG vs. producción).

Ref: issue #69 — fix(auth): SameSite=None; Secure requerido en cookies
cross-site (login roto en producción).
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.models import UsuariosModel


LOGIN_LEGACY_URL = "/api/login/"
LOGIN_JWT_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/logout/"


# Throttles del login están respaldados por cache. Limpiar entre tests
# evita 429 espurios al ejecutar múltiples logins en la misma test-class.
_DISABLE_LOGIN_THROTTLE = override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "api.authentication.JWTCookieAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.AllowAny",
        ),
        # Sin rates → LoginByIpThrottle / LoginByAccountThrottle no throttlean
        "DEFAULT_THROTTLE_RATES": {},
    }
)


def _create_verified_user(correo="cookie@test.com", password="TestPassword1!"):
    u = UsuariosModel.objects.create_user(
        nombre="Cookie",
        apellido="User",
        correo=correo,
        telefono="5550000000",
        password=password,
    )
    u.is_email_verified = True
    u.save(update_fields=["is_email_verified"])
    return u


def _assert_cookie_attrs(testcase, cookie, expected_samesite, expected_secure):
    """Verifica los atributos de seguridad de una cookie del response."""
    testcase.assertEqual(
        cookie["samesite"],
        expected_samesite,
        f"Cookie {cookie.key!r} debe tener SameSite={expected_samesite!r}, "
        f"tiene {cookie['samesite']!r}",
    )
    testcase.assertEqual(
        bool(cookie["secure"]),
        expected_secure,
        f"Cookie {cookie.key!r} debe tener Secure={expected_secure}, "
        f"tiene Secure={bool(cookie['secure'])}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Producción: DEBUG=False → SameSite=None, Secure=True (cross-site OK)
# ─────────────────────────────────────────────────────────────────────────────

@_DISABLE_LOGIN_THROTTLE
@override_settings(
    DEBUG=False,
    COOKIE_SAMESITE="None",
    COOKIE_SECURE=True,
    CSRF_COOKIE_SAMESITE="None",
    CSRF_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
)
class ProductionCookieSecurityTests(TestCase):
    """En prod, las cookies deben ser SameSite=None + Secure para cross-site."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = _create_verified_user()
        self.password = "TestPassword1!"

    def test_login_legacy_emite_cookies_cross_site_safe(self):
        """POST /api/login/ debe emitir access_token y refresh_token con
        SameSite=None + Secure para funcionar en contexto cross-site."""
        res = self.client.post(
            LOGIN_LEGACY_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)
        _assert_cookie_attrs(self, res.cookies["access_token"], "None", True)
        _assert_cookie_attrs(self, res.cookies["refresh_token"], "None", True)

    def test_login_legacy_cookies_httponly(self):
        """access_token y refresh_token deben ser HttpOnly para bloquear XSS."""
        res = self.client.post(
            LOGIN_LEGACY_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertTrue(res.cookies["access_token"]["httponly"])
        self.assertTrue(res.cookies["refresh_token"]["httponly"])

    def test_login_jwt_emite_cookies_cross_site_safe(self):
        """POST /api/auth/login/ (SimpleJWT) también debe emitir cookies
        cross-site-safe."""
        res = self.client.post(
            LOGIN_JWT_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)
        _assert_cookie_attrs(self, res.cookies["access_token"], "None", True)
        _assert_cookie_attrs(self, res.cookies["refresh_token"], "None", True)

    def test_refresh_emite_cookie_cross_site_safe(self):
        """POST /api/auth/refresh/ debe emitir access_token nuevo con
        SameSite=None + Secure."""
        # Primero login para obtener refresh_token en cookie
        login_res = self.client.post(
            LOGIN_JWT_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        # Ahora refresh: el cliente ya tiene la cookie refresh_token
        refresh_res = self.client.post(REFRESH_URL, format="json")
        self.assertEqual(refresh_res.status_code, 200)
        self.assertIn("access_token", refresh_res.cookies)
        _assert_cookie_attrs(self, refresh_res.cookies["access_token"], "None", True)

    def test_logout_borra_cookies_con_mismos_attrs(self):
        """POST /api/logout/ debe emitir Set-Cookie con SameSite=None + Secure
        para que el navegador matchee y borre efectivamente las cookies
        seteadas en el login. Si los atributos no matchean, el browser
        deja las cookies vivas."""
        self.client.post(
            LOGIN_JWT_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        logout_res = self.client.post(LOGOUT_URL, format="json")
        self.assertEqual(logout_res.status_code, 200)
        # Todas las cookies del logout deben salir con los mismos attrs
        # que las del login para que el browser las borre.
        for cookie_name in ("access_token", "refresh_token", "jwt", "csrftoken"):
            self.assertIn(cookie_name, logout_res.cookies)
            _assert_cookie_attrs(self, logout_res.cookies[cookie_name], "None", True)


# ─────────────────────────────────────────────────────────────────────────────
# Desarrollo: DEBUG=True → SameSite=Lax, Secure=False (localhost sin HTTPS)
# ─────────────────────────────────────────────────────────────────────────────

@_DISABLE_LOGIN_THROTTLE
@override_settings(
    DEBUG=True,
    COOKIE_SAMESITE="Lax",
    COOKIE_SECURE=False,
    CSRF_COOKIE_SAMESITE="Lax",
    CSRF_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
)
class DevelopmentCookieSecurityTests(TestCase):
    """En dev, cookies con SameSite=Lax + Secure=False para trabajar contra
    localhost sin HTTPS."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = _create_verified_user()
        self.password = "TestPassword1!"

    def test_login_legacy_dev_usa_lax_sin_secure(self):
        res = self.client.post(
            LOGIN_LEGACY_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        _assert_cookie_attrs(self, res.cookies["access_token"], "Lax", False)
        _assert_cookie_attrs(self, res.cookies["refresh_token"], "Lax", False)

    def test_login_jwt_dev_usa_lax_sin_secure(self):
        res = self.client.post(
            LOGIN_JWT_URL,
            {"correo": self.user.correo, "password": self.password},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        _assert_cookie_attrs(self, res.cookies["access_token"], "Lax", False)
        _assert_cookie_attrs(self, res.cookies["refresh_token"], "Lax", False)


# ─────────────────────────────────────────────────────────────────────────────
# Helper directo: cookie_security_kwargs() reacciona al setting COOKIE_*
# ─────────────────────────────────────────────────────────────────────────────

class CookieSecurityKwargsHelperTests(TestCase):
    """cookie_security_kwargs() debe leer settings dinámicamente para
    respetar override_settings (usado por prod deploys, tests, etc.)."""

    @override_settings(COOKIE_SAMESITE="None", COOKIE_SECURE=True)
    def test_helper_devuelve_valores_de_prod(self):
        from catalogo_backend.settings import cookie_security_kwargs
        kwargs = cookie_security_kwargs()
        self.assertEqual(kwargs["samesite"], "None")
        self.assertEqual(kwargs["secure"], True)

    @override_settings(COOKIE_SAMESITE="Lax", COOKIE_SECURE=False)
    def test_helper_devuelve_valores_de_dev(self):
        from catalogo_backend.settings import cookie_security_kwargs
        kwargs = cookie_security_kwargs()
        self.assertEqual(kwargs["samesite"], "Lax")
        self.assertEqual(kwargs["secure"], False)
