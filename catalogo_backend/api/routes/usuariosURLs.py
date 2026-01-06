from django.urls import path
from ..views import usuariosViews
from .. import apis

# Backend API endpoints
urlsUsuarios = [
    path('signup/', apis.APIRegistro.as_view(), name='registrar'),
    path('login/', apis.APIIniciarSesion.as_view(), name='login'),
    path('logout/', apis.APICerrarSesion.as_view(), name='logout'),
    path('mi_usuario/', apis.APIUsuario.as_view(), name='mi-usuario'),
    path('usuarios/', usuariosViews.UsuariosListCreate.as_view(), name='usuario-view-create'),
    path('usuarios/<int:id>', usuariosViews.UsuariosRetrieveUpdateDestroy.as_view(), name='usuario-update')
]