from django.urls import path
from .views import mockViews, usuariosViews, categoriasViews, direccionesViews, pedidosViews, pedidoProductosViews
from . import apis
from .routes import usuariosURLs

# Backend API endpoints
urlpatterns = [
    path('', mockViews.getMockData),
    path('categorias/', categoriasViews.CategoriasListCreate.as_view(), name='categoria-view-create'),
    path('categorias/<int:id>', categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name='categoria-update'),
    path('direcciones/', direccionesViews.DireccionesListCreate.as_view(), name='direccion-view-create'),
    path('direcciones/<int:id>', direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name='direccion-update'),
    path('pedidos/', pedidosViews.PedidosListCreate.as_view(), name='pedido-view-create'),
    path('pedidos/<int:id>', pedidosViews.PedidosRetrieveUpdateDestroy.as_view(), name='pedido-update'),
    path('pedido-productos/', pedidoProductosViews.PedidoProductosListCreate.as_view(), name='pedido-producto-view-create'),
    path('pedido-productos/<int:id>', pedidoProductosViews.PedidoProductosRetrieveUpdateDestroy.as_view(), name='pedido-producto-update'),
]

urlpatterns += usuariosURLs.urlsUsuarios