from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed, TokenError

class JWTCookieAuthentication(JWTAuthentication):
    def authenticate(self, request):
        """
        Extiende JWTAuthentication para:
        1. Soportar tokens en Cookies ('access_token').
        2. Mantener soporte para headers ('Authorization: Bearer') por retrocompatibilidad.
        3. No lanzar 401 automático si el token es inválido (retorna None para permitir acceso anónimo en rutas públicas).
        """
        
        # 1. Intentar autenticación por Header (Estándar/Retrocompatibilidad)
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                try:
                    validated_token = self.get_validated_token(raw_token)
                    return self.get_user(validated_token), validated_token
                except (InvalidToken, AuthenticationFailed, TokenError):
                    pass
        
        # 2. Intentar autenticación por Cookie
        raw_token = request.COOKIES.get('access_token')
        if raw_token is not None:
            try:
                validated_token = self.get_validated_token(raw_token)
                user = self.get_user(validated_token)
                # CSRF solo aplica en métodos no seguros (POST, PUT, PATCH, DELETE).
                # Los métodos seguros (GET, HEAD, OPTIONS) no requieren CSRF.
                if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
                    self.enforce_csrf(request)
                return user, validated_token
            except (InvalidToken, AuthenticationFailed, TokenError):
                pass

        # Si no hay token válido, retornamos None (Usuario Anónimo)
        return None

    def enforce_csrf(self, request):
        """
        Obliga a validar CSRF para peticiones autenticadas vía cookie en métodos no seguros.
        """
        from rest_framework.authentication import CSRFCheck
        check = CSRFCheck(get_response=lambda request: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise AuthenticationFailed(f'CSRF Failed: {reason}')