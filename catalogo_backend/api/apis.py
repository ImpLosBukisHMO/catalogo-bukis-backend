import dataclasses
from rest_framework import views, response, exceptions, permissions, status
from . import serializers
from . import services
from . import authentication
from rest_framework_simplejwt.tokens import RefreshToken

# Registrarse.
class APIRegistro(views.APIView):
    def post(self, request):
        serializador = serializers.UsuariosSerializer(data=request.data)
        serializador.is_valid(raise_exception=True)
        datos = serializador.validated_data
        nuevoUsuario = services.crear_usuario(dcUsuario=datos)
        res = dataclasses.asdict(nuevoUsuario)
        res.pop('password', None)
        return response.Response({'datos': res}, status=status.HTTP_200_OK)


# Iniciar sesión.
class APIIniciarSesion(views.APIView):
    def post(self, request):
        correoUsuario = request.data['correo']
        contrasenaUsuario = request.data['password']
        usuario = services.filtrarUsuarioPorCorreo(correoUsuario)
        
        if usuario is None:
            raise exceptions.AuthenticationFailed('Credenciales inválidas.')
        if not usuario.check_password(raw_password=contrasenaUsuario):
            raise exceptions.AuthenticationFailed('Contraseña incorrecta.')
        
        refresh = RefreshToken.for_user(usuario)
        token = str(refresh.access_token)
        res = response.Response({"token": token})
        res.set_cookie(key='jwt', value=token, httponly=True)
        return res


# Autenticación de usuario. Solo la puede utilizar un usuario autenticado.
class APIUsuario(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        usuario = request.user
        serializador = serializers.UsuariosSerializer(usuario)
        return response.Response(serializador.data, status=status.HTTP_200_OK)
    

# Cerrar sesión del usuario actual.
class APICerrarSesion(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        res = response.Response()
        res.delete_cookie(key='jwt')
        res.data = {'mensaje': 'La sesión se cerró exitosamente.'}
        return res