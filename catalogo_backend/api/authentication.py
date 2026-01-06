from django.conf import settings
from rest_framework import authentication, exceptions
import jwt
from . import models

class AutenticacionUsuario(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get('jwt')
        
        if not token:
            return None
        
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            raise exceptions.AuthenticationFailed('Acceso restringido: Token inválido.')
        
        usuario = models.UsuariosModel.objects.filter(id=payload['id']).first()
        
        if not usuario:
            raise exceptions.AuthenticationFailed('Usuario no encontrado.')
            
        return (usuario, None)