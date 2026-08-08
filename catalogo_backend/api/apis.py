from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
import dataclasses
from rest_framework import views, response, exceptions, permissions, status
# pyrefly: ignore [missing-import]
from . import serializers
# pyrefly: ignore [missing-import]
from . import services
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
# pyrefly: ignore [missing-import]
from .throttles import LoginByIpThrottle, LoginByAccountThrottle


# Registrarse.
class APIRegistro(views.APIView):
    def post(self, request):
        plain_password = request.data.get("password")

        if plain_password is None:
            raise DRFValidationError({"password": ["La contraseña es obligatoria."]})

        try:
            validate_password(plain_password)
        except DjangoValidationError as e:
            raise DRFValidationError({"password": list(e.messages)})

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

        return response.Response({'datos': res, 'mensaje': mensaje}, status=status.HTTP_201_CREATED)


# Iniciar sesión.
class APIIniciarSesion(views.APIView):
    throttle_classes = [LoginByIpThrottle, LoginByAccountThrottle]

    def throttled(self, request, wait):
        int_wait = int(wait) if wait is not None else 60
        raise exceptions.Throttled(
            wait=wait,
            detail=f"Has superado el límite de intentos de inicio de sesión. Debes esperar {int_wait} segundos para volver a intentarlo."
        )

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
        res = response.Response({"mensaje": "Autenticación exitosa"})
        res.set_cookie(key='access_token', value=str(refresh.access_token), httponly=True, samesite='Lax')
        res.set_cookie(key='refresh_token', value=str(refresh), httponly=True, samesite='Lax')
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


# Solicitar recuperación de contraseña
class APISolicitarRecuperacion(views.APIView):
    def post(self, request):
        correo = request.data.get('correo')
        if not correo:
            return response.Response({'error': 'El correo es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        
        usuario = services.filtrarUsuarioPorCorreo(correo)
        if usuario:
            # Generate code and send email
            services.enviar_correo_recuperacion(usuario)
            
        # Siempre devolvemos el mismo mensaje para evitar enumeración de correos
        return response.Response(
            {'mensaje': 'Si el correo está registrado, recibirás un código de recuperación.'}, 
            status=status.HTTP_200_OK
        )


# Confirmar recuperación de contraseña
class APIConfirmarRecuperacion(views.APIView):
    def post(self, request):
        correo = request.data.get('correo')
        codigo = request.data.get('codigo')
        nueva_password = request.data.get('nueva_password')
        
        if not correo or not codigo or not nueva_password:
            return response.Response(
                {'error': 'Todos los campos son requeridos (correo, código, nueva contraseña).'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        exito, mensaje = services.restablecer_password(correo, codigo, nueva_password)
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
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        res = response.Response({'mensaje': 'La sesión se cerró exitosamente.'})
        res.set_cookie(key='access_token', value='', max_age=0, path='/', httponly=True, samesite='Lax')
        res.set_cookie(key='refresh_token', value='', max_age=0, path='/', httponly=True, samesite='Lax')
        res.set_cookie(key='jwt', value='', max_age=0, path='/', httponly=True, samesite='Lax')
        res.delete_cookie(key='access_token', path='/', samesite='Lax')
        res.delete_cookie(key='refresh_token', path='/', samesite='Lax')
        res.delete_cookie(key='jwt', path='/', samesite='Lax')
        return res
        
        
class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginByIpThrottle, LoginByAccountThrottle]

    def throttled(self, request, wait):
        int_wait = int(wait) if wait is not None else 60
        raise exceptions.Throttled(
            wait=wait,
            detail=f"Has superado el límite de intentos de inicio de sesión. Debes esperar {int_wait} segundos para volver a intentarlo."
        )
    
    def post(self, request, *args, **kwargs):
        res = super().post(request, *args, **kwargs)
        if res.status_code == 200:
            correo = request.data.get('correo')
            usuario = services.filtrarUsuarioPorCorreo(correo)
            if usuario and not usuario.is_email_verified:
                raise exceptions.AuthenticationFailed('Debes confirmar tu cuenta de correo antes de iniciar sesión.')

            access_token = res.data.get('access')
            refresh_token = res.data.get('refresh')
            res.set_cookie(key='access_token', value=access_token, httponly=True, samesite='Lax')
            res.set_cookie(key='refresh_token', value=refresh_token, httponly=True, samesite='Lax')
        return res


class CookieTokenRefreshView(TokenRefreshView):
    """
    Vista que lee el refresh token desde las cookies HttpOnly y devuelve
    nuevos tokens en formato cookie en vez del body.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        
        if not refresh_token:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed("No se proporcionó un token de actualización en las cookies.")
            
        # Inyectar el refresh_token en el request.data para engañar a SimpleJWT
        # y que lo procese como si hubiera venido por el body.
        if not isinstance(request.data, dict):
            # Request data can be immutable QueryDict
            request.data._mutable = True
        request.data['refresh'] = refresh_token
        res = super().post(request, *args, **kwargs)
        if res.status_code == 200:
            access_token = res.data.get('access')
            res.set_cookie(key='access_token', value=access_token, httponly=True, samesite='Lax')
            if 'refresh' in res.data:
                res.set_cookie(key='refresh_token', value=res.data['refresh'], httponly=True, samesite='Lax')
        return res