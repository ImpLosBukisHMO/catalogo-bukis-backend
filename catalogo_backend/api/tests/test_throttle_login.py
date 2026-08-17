import hashlib
from django.test import TestCase, override_settings
from django.core.cache import cache
from rest_framework.test import APIClient

from api.models import UsuariosModel

LOGIN_URL = "/api/login/"
JWT_LOGIN_URL = "/api/auth/login/"

@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "api.authentication.JWTCookieAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.AllowAny",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login_ip": "5/minute",
            "login_account": "10/minute",
        }
    }
)
class LoginThrottleByIpTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        
        self.usuario = UsuariosModel.objects.create_user(
            nombre="Test",
            apellido="IP",
            correo="ip@test.com",
            telefono="5550000000",
            password="TestPassword1!",
        )
        self.usuario.is_email_verified = True
        self.usuario.save(update_fields=["is_email_verified"])

    def test_login_permite_5_intentos_dentro_del_limite(self):
        for _ in range(5):
            res = self.client.post(LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
            self.assertEqual(res.status_code, 401)
            
    def test_login_bloquea_al_6to_intento_por_ip(self):
        for _ in range(5):
            self.client.post(LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
            
        res = self.client.post(LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
        self.assertEqual(res.status_code, 429)

    def test_throttle_devuelve_mensaje_en_espanol(self):
        for _ in range(6):
            res = self.client.post(LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
            
        self.assertEqual(res.status_code, 429)
        self.assertIn("Has superado el límite de intentos de inicio de sesión.", res.data.get("detail", ""))

    def test_jwt_login_tambien_aplica_throttle_ip(self):
        for _ in range(5):
            self.client.post(JWT_LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
            
        res = self.client.post(JWT_LOGIN_URL, {"correo": "wrong@test.com", "password": "123"}, format="json")
        self.assertEqual(res.status_code, 429)


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "api.authentication.JWTCookieAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.AllowAny",
        ),
        "DEFAULT_THROTTLE_RATES": {
            "login_ip": "100/minute",  # Aumentamos para no cruzar con el límite de cuenta
            "login_account": "10/minute",
        }
    }
)
class LoginThrottleByAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        
        self.usuario = UsuariosModel.objects.create_user(
            nombre="Test",
            apellido="Acc",
            correo="account@test.com",
            telefono="5550000000",
            password="TestPassword1!",
        )
        self.usuario.is_email_verified = True
        self.usuario.save(update_fields=["is_email_verified"])

    def test_login_bloquea_cuenta_despues_de_10_intentos(self):
        # Simulamos peticiones desde IPs distintas para asegurar que es el throttle de cuenta el que bloquea
        for i in range(10):
            client = APIClient(REMOTE_ADDR=f"192.168.1.{i}")
            res = client.post(LOGIN_URL, {"correo": "account@test.com", "password": "wrong"}, format="json")
            self.assertEqual(res.status_code, 401)
            
        client = APIClient(REMOTE_ADDR="192.168.1.99")
        res = client.post(LOGIN_URL, {"correo": "account@test.com", "password": "wrong"}, format="json")
        self.assertEqual(res.status_code, 429)

    def test_throttle_cache_key_usa_hash_correo(self):
        from api.throttles import LoginByAccountThrottle
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.post(LOGIN_URL, {"correo": "Hash@Test.com", "password": "123"}, format="json")
        
        view = type("Dummy", (), {})()
        throttle = LoginByAccountThrottle()
        key = throttle.get_cache_key(request, view)
        
        # El correo normalizado debe ser "hash@test.com"
        expected_hash = hashlib.sha256("hash@test.com".encode()).hexdigest()
        self.assertIn(expected_hash, key)
        self.assertNotIn("hash@test.com", key)
