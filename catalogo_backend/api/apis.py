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
        instancia_usuario = services.filtrarUsuarioPorCorreo(nuevoUsuario.correo)
        
        mensaje = 'Usuario registrado con éxito. Revisa tu correo para confirmar la cuenta.'
        if instancia_usuario:
            exito, msg_correo = services.enviar_correo_confirmacion(instancia_usuario)
            if not exito:
                mensaje = 'Usuario registrado con éxito, pero tuvimos un problema enviando el correo. Intenta reenviarlo más tarde.'
        
        res = dataclasses.asdict(nuevoUsuario)
        res.pop('password', None)

        return response.Response(
            {
                'datos': res,
                'mensaje': mensaje
            },
            status=status.HTTP_201_CREATED
        )


# Iniciar sesión.
class APIIniciarSesion(views.APIView):
    def post(self, request):
        correoUsuario = request.data.get('correo')
        contrasenaUsuario = request.data.get('password')
        usuario = services.filtrarUsuarioPorCorreo(correoUsuario)
        
        if usuario is None:
            raise exceptions.AuthenticationFailed('Credenciales inválidas.')
        
        if not usuario.check_password(raw_password=contrasenaUsuario):
            raise exceptions.AuthenticationFailed('Contraseña incorrecta.')
        
        if not usuario.is_email_verified:
            raise exceptions.AuthenticationFailed('Debes confirmar tu cuenta de correo antes de iniciar sesión.')
        
        refresh = RefreshToken.for_user(usuario)
        token = str(refresh.access_token)
        res = response.Response({"token": token})
        res.set_cookie(key='jwt', value=token, httponly=True)
        return res


# Confirmar cuenta
class APIConfirmarCuenta(views.APIView):
    def post(self, request):
        correo = request.data.get('correo')
        codigo = request.data.get('codigo')
        
        if not correo or not codigo:
            return response.Response({'error': 'El correo y el código son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)
        
        exito, mensaje = services.confirmar_cuenta_codigo(correo, codigo)
        if not exito:
            return response.Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
        
        return response.Response({'mensaje': mensaje}, status=status.HTTP_200_OK)


# Reenviar confirmación
class APIReenviarConfirmacion(views.APIView):
    def post(self, request):
        correo = request.data.get('correo')
        if not correo:
            return response.Response({'error': 'El correo es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        
        exito, mensaje = services.reenviar_correo_confirmacion(correo)
        if not exito:
            return response.Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
        
        return response.Response({'mensaje': mensaje}, status=status.HTTP_200_OK)


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