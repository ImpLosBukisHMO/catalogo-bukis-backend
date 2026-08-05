from django.urls import path
# pyrefly: ignore [missing-import]
from ..views import usuariosViews
# pyrefly: ignore [missing-import]
from .. import apis

# Backend API endpoints
urlsUsuarios = [
    path('signup/', apis.APIRegistro.as_view(), name='registrar'),
    path('login/', apis.APIIniciarSesion.as_view(), name='login'),
    path('logout/', apis.APICerrarSesion.as_view(), name='logout'),
    path('confirmar-cuenta/', apis.APIConfirmarCuenta.as_view(), name='confirmar-cuenta'),
    path('reenviar-confirmacion/', apis.APIReenviarConfirmacion.as_view(), name='reenviar-confirmacion'),
    path('recuperar-password/solicitar/', apis.APISolicitarRecuperacion.as_view(), name='solicitar-recuperacion'),
    path('recuperar-password/confirmar/', apis.APIConfirmarRecuperacion.as_view(), name='confirmar-recuperacion'),
    path('mi_usuario/', apis.APIUsuario.as_view(), name='mi-usuario'),
    path('usuarios/', usuariosViews.UsuariosListCreate.as_view(), name='usuario-view-create'),
    path('usuarios/<int:id>/', usuariosViews.UsuariosRetrieveUpdateDestroy.as_view(), name='usuario-update')
]