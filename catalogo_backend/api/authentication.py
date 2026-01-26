from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed, TokenError

class AutenticacionUsuario(JWTAuthentication):
    def authenticate(self, request):
        """
        Extiende JWTAuthentication para:
        1. Soportar tokens en Cookies ('jwt').
        2. No lanzar 401 si el token es inválido (retorna None para permitir acceso anónimo).
        """
        
        # 1. Intentar autenticación por Header (Estándar)
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                try:
                    validated_token = self.get_validated_token(raw_token)
                    return self.get_user(validated_token), validated_token
                except (InvalidToken, AuthenticationFailed, TokenError):
                    # Si el token del header es inválido, lo ignoramos (no lanzamos error)
                    pass
        
        # 2. Intentar autenticación por Cookie
        raw_token = request.COOKIES.get('jwt')
        if raw_token is not None:
            try:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, AuthenticationFailed, TokenError):
                # Si el token de la cookie es inválido, lo ignoramos
                pass

        # Si no hay token válido, retornamos None (Usuario Anónimo)
        return None