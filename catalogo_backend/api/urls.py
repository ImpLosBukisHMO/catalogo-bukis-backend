from django.urls import path
from .views import (
    mockViews,
    categoriasViews,
    direccionesViews,
    pedidosViews,
    productosFavoritosViews,
    coloresViews,
)

from api.views.productosViews import ProductosListCreate, ProductosRetrieveUpdateDestroy
from .views.productoVariantesViews import (
    ProductoVariantesListCreateView,
    ProductoVariantesDetailView,
)
from .views.productosImagenesViews import (
    ProductosImagenesListCreateView,
    ProductosImagenesDetailView,
)
from .routes import usuariosURLs

urlpatterns = [
    path("", mockViews.getMockData),

    # Categorías
    path("categorias/", categoriasViews.CategoriasListCreate.as_view(), name="categoria-view-create"),
    path("categorias/<int:id>/", categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name="categoria-update"),

    # Direcciones
    path("direcciones/", direccionesViews.DireccionesListCreate.as_view(), name="direccion-view-create"),
    path("direcciones/<int:id>/", direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name="direccion-update"),

    # Pedidos
    path("pedidos/", pedidosViews.PedidosListCreate.as_view(), name="pedido-view-create"),
    path("pedidos/<int:id>/", pedidosViews.PedidosRetrieveUpdateDestroy.as_view(), name="pedido-update"),

    # Pedido - Productos
    path("pedido-productos/", pedidosViews.PedidoProductosListCreate.as_view(), name="pedido-producto-view-create"),
    path("pedido-productos/<int:id>/", pedidosViews.PedidoProductosRetrieveUpdateDestroy.as_view(), name="pedido-producto-update"),

    # Favoritos
    path("productos-favoritos/", productosFavoritosViews.ProductosFavoritosListCreate.as_view(), name="producto-favorito-view-create"),
    path("productos-favoritos/<int:id>/", productosFavoritosViews.ProductosFavoritosRetrieveUpdateDestroy.as_view(), name="producto-favorito-update"),

    # Colores
    path("colores/", coloresViews.ColoresListCreateView.as_view(), name="colores-list-create"),
    path("colores/<int:id>/", coloresViews.ColoresDetailView.as_view(), name="colores-detail"),

    # Producto - Variantes (antes producto-colores)
    path("producto-variantes/", ProductoVariantesListCreateView.as_view(), name="producto-variantes-list-create"),
    path("producto-variantes/<int:id>/", ProductoVariantesDetailView.as_view(), name="producto-variantes-detail"),

    # Productos
    path("productos/", ProductosListCreate.as_view(), name="productos-list-create"),
    path("productos/<int:id>/", ProductosRetrieveUpdateDestroy.as_view(), name="producto-detail"),

    path("productos-imagenes/", ProductosImagenesListCreateView.as_view(), name="productos-imagenes-list-create"),
    path("productos-imagenes/<int:id>/", ProductosImagenesDetailView.as_view(), name="productos-imagenes-detail"),

]

urlpatterns += usuariosURLs.urlsUsuarios
