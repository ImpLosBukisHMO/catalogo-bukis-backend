"""
Clases de throttling para proteccion contra fuerza bruta en el login.

Defensa en profundidad (dos capas simultaneas):
- LoginByIpThrottle: limita peticiones por direccion IP (heredando de AnonRateThrottle).
  Bloquea ataques desde una misma red aunque cambien el usuario objetivo.
- LoginByAccountThrottle: limita peticiones hacia un mismo correo/usuario,
  sin importar la IP de origen (heredando de SimpleRateThrottle).
  Bloquea ataques distribuidos (botnet) contra una cuenta especifica.

Configuracion de tasas en settings.py:
  REST_FRAMEWORK = {
      "DEFAULT_THROTTLE_RATES": {
          "login_ip": "5/minute",
          "login_account": "10/minute",
      }
  }

NOTA DE INFRAESTRUCTURA: Para que el throttle por IP funcione correctamente
detras de un proxy/load balancer (ej. Railway, Nginx), configurar en settings.py:
  NUM_PROXIES = 1  # o el numero de proxies en la cadena
Esto hace que DRF lea la IP real del cliente desde X-Forwarded-For
en lugar de usar la IP del proxy, que bloquearia a todos los usuarios por igual.
"""

import hashlib

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class LoginByIpThrottle(AnonRateThrottle):
    """
    Limita los intentos de login por direccion IP.
    Scope: 'login_ip' -> configurable en DEFAULT_THROTTLE_RATES.
    """
    scope = "login_ip"


class LoginByAccountThrottle(SimpleRateThrottle):
    """
    Limita los intentos de login por cuenta (correo electronico del body).
    Scope: 'login_account' -> configurable en DEFAULT_THROTTLE_RATES.

    La cache key se construye con un hash SHA-256 del correo normalizado
    para evitar exponer datos sensibles en el backend de cache.
    """
    scope = "login_account"

    def get_cache_key(self, request, view):
        # Leer el correo del body del request (compatible con JSON y form-data)
        correo = (
            request.data.get("correo")
            or request.data.get("username")
            or ""
        )
        if not correo:
            # Si no hay correo en el body, usar la IP como fallback
            # para no dejar sin proteccion el endpoint
            return self.get_ident(request)

        # Hash para no guardar el correo en texto plano en la cache
        correo_hash = hashlib.sha256(correo.strip().lower().encode()).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": correo_hash,
        }
