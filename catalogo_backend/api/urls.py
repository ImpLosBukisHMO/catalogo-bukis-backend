from django.urls import path
from .views import mockViews, usuariosViews, categoriasViews, direccionesViews
from . import apis
from .routes import usuariosURLs

# Backend API endpoints
urlpatterns = [
    path('', mockViews.getMockData),
    path('categorias/', categoriasViews.CategoriasListCreate.as_view(), name='categoria-view-create'),
    path('categorias/<int:id>', categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name='categoria-update'),
    path('direcciones/', direccionesViews.DireccionesListCreate.as_view(), name='direccion-view-create'),
    path('direcciones/<int:id>', direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name='direccion-update'),
]

urlpatterns += usuariosURLs.urlsUsuarios