from django.urls import path
from .views import mockViews
from .views import usuariosViews
from .views import categoriasViews
from .views import direccionesViews


# Backend API endpoints
urlpatterns = [
    path('mock/', mockViews.getMockData),
    path('mock/param/<int:param>/', mockViews.getMockDataParam),
    path('usuarios/', usuariosViews.UsuariosListCreate.as_view(), name='usuario-view-create'),
    path('usuarios/<int:id>', usuariosViews.UsuariosRetrieveUpdateDestroy.as_view(), name='usuario-update'),
    path('categorias/', categoriasViews.CategoriasListCreate.as_view(), name='categoria-view-create'),
    path('categorias/<int:id>', categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name='categoria-update'),
    path('direcciones/', direccionesViews.DireccionesListCreate.as_view(), name='direccion-view-create'),
    path('direcciones/<int:id>', direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name='direccion-update'),
]