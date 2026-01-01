from django.urls import path
from .views import mockViews, usuariosViews, categoriasViews, direccionesViews, pedidosViews, pedidoProductosViews, productosViews, productosFavoritosViews

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
    path('pedidos/', pedidosViews.PedidosListCreate.as_view(), name='pedido-view-create'),
    path('pedidos/<int:id>', pedidosViews.PedidosRetrieveUpdateDestroy.as_view(), name='pedido-update'),
    path('pedido-productos/', pedidoProductosViews.PedidoProductosListCreate.as_view(), name='pedido-producto-view-create'),
    path('pedido-productos/<int:id>', pedidoProductosViews.PedidoProductosRetrieveUpdateDestroy.as_view(), name='pedido-producto-update'),
    path("productos/", productosViews.ProductosListCreate.as_view(), name="producto-view-create"),
    path("productos/<int:id>", productosViews.ProductosRetrieveUpdateDestroy.as_view(), name="producto-update"),
    path("productos-favoritos/", productosFavoritosViews.ProductosFavoritosListCreate.as_view(), name="producto-favorito-view-create"),
    path("productos-favoritos/<int:id>", productosFavoritosViews.ProductosFavoritosRetrieveUpdateDestroy.as_view(), name="producto-favorito-update"),
]