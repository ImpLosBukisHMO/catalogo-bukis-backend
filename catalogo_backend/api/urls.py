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
from .views.productoColoresViews import ProductoColorListCreateView, ProductoColorDetailView
from .routes import usuariosURLs

urlpatterns = [
    path("", mockViews.getMockData),

    path("categorias/", categoriasViews.CategoriasListCreate.as_view(), name="categoria-view-create"),
    path("categorias/<int:id>/", categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name="categoria-update"),

    path("direcciones/", direccionesViews.DireccionesListCreate.as_view(), name="direccion-view-create"),
    path("direcciones/<int:id>/", direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name="direccion-update"),

    path("pedidos/", pedidosViews.PedidosListCreate.as_view(), name="pedido-view-create"),
    path("pedidos/<int:id>/", pedidosViews.PedidosRetrieveUpdateDestroy.as_view(), name="pedido-update"),

    path("pedido-productos/", pedidosViews.PedidoProductosListCreate.as_view(), name="pedido-producto-view-create"),
    path("pedido-productos/<int:id>/", pedidosViews.PedidoProductosRetrieveUpdateDestroy.as_view(), name="pedido-producto-update"),

    path("productos-favoritos/", productosFavoritosViews.ProductosFavoritosListCreate.as_view(), name="producto-favorito-view-create"),
    path("productos-favoritos/<int:id>/", productosFavoritosViews.ProductosFavoritosRetrieveUpdateDestroy.as_view(), name="producto-favorito-update"),

    path("colores/", coloresViews.ColoresListCreateView.as_view()),
    path("colores/<int:id>/", coloresViews.ColoresDetailView.as_view()),

    path("producto-colores/", ProductoColorListCreateView.as_view()),
    path("producto-colores/<int:id>/", ProductoColorDetailView.as_view()),

    path("productos/", ProductosListCreate.as_view(), name="productos-list-create"),
    path("productos/<int:id>/", ProductosRetrieveUpdateDestroy.as_view(), name="producto-detail"),
]

urlpatterns += usuariosURLs.urlsUsuarios
