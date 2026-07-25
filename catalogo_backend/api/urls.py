# pyrefly: ignore [missing-import]
from django.urls import path
# pyrefly: ignore [missing-import]
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from api.views.descuentosViews import DescuentosRetrieveUpdateDestroy
from api.views.descuentosViews import DescuentosListCreate
from api.views import (
    mockViews,
    categoriasViews,
    direccionesViews,
    pedidosViews,
    productosFavoritosViews,
    coloresViews,
    carritoViews,
)
from api.views.workerViews import (
    WorkerVariantListView,
    WorkerPedidoListView,
    WorkerPedidoDetailView,
    WorkerCambiarEstadoView,
    WorkerProductoListCreateView,
    WorkerProductoUpdateView,
    WorkerVarianteCreateView,
    WorkerVarianteDetailView,
    WorkerImagenCreateView,
    WorkerDescuentosListCreate,
    WorkerDescuentosRetrieveUpdateDestroy,
    WorkerDescuentosTiposView,
)
from api.views.usuariosViews import MiUsuarioView
from api.views.productosViews import ProductosListCreate, ProductosRetrieveUpdateDestroy
from api.views.productoVariantesViews import ProductoVariantesListCreateView, ProductoVariantesDetailView
from api.views.productosImagenesViews import ProductosImagenesListCreateView, ProductosImagenesDetailView
from api.views.bannerOfertasViews import (
    WorkerBannerOfertasListCreate,
    WorkerBannerOfertasRetrieveUpdateDestroy,
    BannerOfertasPublicList,
)
from api.routes import usuariosURLs


urlpatterns = [
    path("", mockViews.getMockData),

    # Perfil (quién soy)
    path("mi_usuario/", MiUsuarioView.as_view(), name="mi-usuario"),

    # Categorías
    path("categorias/", categoriasViews.CategoriasListCreate.as_view(), name="categoria-view-create"),
    path("categorias/<int:id>/", categoriasViews.CategoriasRetrieveUpdateDestroy.as_view(), name="categoria-update"),

    # Direcciones
    path("direcciones/", direccionesViews.DireccionesListCreate.as_view(), name="direccion-view-create"),
    path("direcciones/<int:id>/", direccionesViews.DireccionesRetrieveUpdateDestroy.as_view(), name="direccion-update"),
    path("direcciones/usuario/<int:id_usuario>/", direccionesViews.DireccionesUsuarioView.as_view(), name="direccion-usuario"),

    # Pedidos
    path("pedidos/", pedidosViews.PedidosListCreate.as_view(), name="pedido-view-create"),
    path("pedidos/<int:id>/", pedidosViews.PedidosRetrieveUpdateDestroy.as_view(), name="pedido-update"),

    # Mis pedidos (cliente autenticado)
    path("mis-pedidos/", pedidosViews.MisPedidosListView.as_view(), name="mis-pedidos"),
    path("mis-pedidos/<int:id>/", pedidosViews.MiPedidoDetalleView.as_view(), name="mi-pedido-detalle"),

    # Pedido - Productos
    path("pedido-productos/", pedidosViews.PedidoProductosListCreate.as_view(), name="pedido-producto-view-create"),
    path("pedido-productos/<int:id>/", pedidosViews.PedidoProductosRetrieveUpdateDestroy.as_view(), name="pedido-producto-update"),

    # Favoritos
    path("productos-favoritos/", productosFavoritosViews.ProductosFavoritosListCreate.as_view(), name="producto-favorito-view-create"),
    path("productos-favoritos/<int:id>/", productosFavoritosViews.ProductosFavoritosRetrieveUpdateDestroy.as_view(), name="producto-favorito-update"),

    # Colores
    path("colores/", coloresViews.ColoresListCreateView.as_view(), name="colores-list-create"),
    path("colores/<int:id>/", coloresViews.ColoresDetailView.as_view(), name="colores-detail"),

    # Producto - Variantes
    path("producto-variantes/", ProductoVariantesListCreateView.as_view(), name="producto-variantes-list-create"),
    path("producto-variantes/<int:id>/", ProductoVariantesDetailView.as_view(), name="producto-variantes-detail"),

    # Productos
    path("productos/", ProductosListCreate.as_view(), name="productos-list-create"),
    path("productos/<int:id>/", ProductosRetrieveUpdateDestroy.as_view(), name="producto-detail"),

    # Productos - Imágenes
    path("productos-imagenes/", ProductosImagenesListCreateView.as_view(), name="productos-imagenes-list-create"),
    path("productos-imagenes/<int:id>/", ProductosImagenesDetailView.as_view(), name="productos-imagenes-detail"),

    # Descuentos
    path("descuentos/", DescuentosListCreate.as_view(), name="descuentos-list-create"),
    path("descuentos/<int:id>/", DescuentosRetrieveUpdateDestroy.as_view(), name="descuentos-detail"),

    # Banner de ofertas (público - home)
    path("banner-ofertas/", BannerOfertasPublicList.as_view(), name="banner-ofertas-public"),

    # Carrito
    path("carrito/", carritoViews.carrito_actual, name="carrito-actual"),  # GET
    path("carrito/items/", carritoViews.carrito_add_item, name="carrito-add-item"),  # POST
    path("carrito/items/<int:item_id>/", carritoViews.carrito_item_detail, name="carrito-item-detail"),  # PATCH/DELETE
    path("carrito/checkout/", carritoViews.carrito_checkout, name="carrito-checkout"),  # POST

    # JWT
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Worker - variantes (existente)
    path("worker/variants/", WorkerVariantListView.as_view(), name="worker-variants"),
    path("worker/variants/<int:id>/", WorkerVarianteDetailView.as_view(), name="worker-variant-detail"),

    # Worker - pedidos
    path("worker/pedidos/", WorkerPedidoListView.as_view(), name="worker-pedidos"),
    path("worker/pedidos/<int:pedido_id>/", WorkerPedidoDetailView.as_view(), name="worker-pedido-detail"),
    path("worker/pedidos/<int:pedido_id>/cambiar-estado/", WorkerCambiarEstadoView.as_view(), name="worker-cambiar-estado"),

    # Worker - productos propios
    path("worker/productos/", WorkerProductoListCreateView.as_view(), name="worker-productos"),
    path("worker/productos/<int:producto_id>/", WorkerProductoUpdateView.as_view(), name="worker-producto-detail"),
    path("worker/productos/<int:producto_id>/variantes/", WorkerVarianteCreateView.as_view(), name="worker-variante-create"),
    path("worker/productos/<int:producto_id>/imagenes/", WorkerImagenCreateView.as_view(), name="worker-imagen-create"),

    # Worker - descuentos
    path("worker/descuentos/", WorkerDescuentosListCreate.as_view(), name="worker-descuentos"),
    path("worker/descuentos/tipos/", WorkerDescuentosTiposView.as_view(), name="worker-descuentos-tipos"),
    path("worker/descuentos/<int:id>/", WorkerDescuentosRetrieveUpdateDestroy.as_view(), name="worker-descuentos-detail"),

    # Worker - banner de ofertas
    path("worker/banner-ofertas/", WorkerBannerOfertasListCreate.as_view(), name="worker-banner-ofertas"),
    path("worker/banner-ofertas/<int:id>/", WorkerBannerOfertasRetrieveUpdateDestroy.as_view(), name="worker-banner-ofertas-detail"),
]

# Signup/Login/Logout legacy + usuarios CRUD (según su archivo routes/usuariosURLs.py)
urlpatterns += usuariosURLs.urlsUsuarios
