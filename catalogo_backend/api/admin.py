from django.contrib import admin
from . import models

class AdminUsuario(admin.ModelAdmin):
    list_display = ("id", "nombre", "apellido", "correo", "telefono")

class AdminDireccion(admin.ModelAdmin):
    list_display = ("id", "usuario", "calle", "colonia", "codigo_postal", "ciudad", "estado", "pais")

class AdminCategorias(admin.ModelAdmin):
    list_display = ("id", "nombre")

class AdminPedidos(admin.ModelAdmin):
    list_display = ("id", "clave", "cliente", "precio_total")

class AdminPedidoProductos(admin.ModelAdmin):
    list_display = ("id", "pedido", "producto", "cantidad", "color", "precio_unitario_producto")


class AdminColores(admin.ModelAdmin):
    list_display = ("id", "nombre", "hex")

class AdminProductos(admin.ModelAdmin):
    list_display = ("id", "nombre", "precio", "mostrar_categorias")

    def mostrar_categorias(self, obj):
        return ", ".join(
            categoria.nombre for categoria in obj.categorias.all()
        )

    mostrar_categorias.short_description = "Categorías"


class AdminProductoVariantes(admin.ModelAdmin):
    list_display = ("id", "producto", "color", "stock", "activo")

class AdminProductosImagenes(admin.ModelAdmin):
    list_display = ("id", "producto", "variante", "orden", "es_principal", "imagen")

class AdminCarrito(admin.ModelAdmin):
    list_display = ("id", "cliente", "estado", "created_at", "updated_at")

class AdminCarritoItem(admin.ModelAdmin):
    list_display = ("id", "carrito", "variante", "cantidad", "created_at", "updated_at")


admin.site.register(models.UsuariosModel, AdminUsuario)
admin.site.register(models.DireccionesModel, AdminDireccion)
admin.site.register(models.CategoriasModel, AdminCategorias)
admin.site.register(models.PedidosModel, AdminPedidos)
admin.site.register(models.PedidoProductosModel, AdminPedidoProductos)

admin.site.register(models.ColorModel, AdminColores)
admin.site.register(models.ProductosModel, AdminProductos)
admin.site.register(models.ProductoVariantesModel, AdminProductoVariantes)
admin.site.register(models.ProductosImagenesModel, AdminProductosImagenes)
admin.site.register(models.CarritoModel, AdminCarrito)
admin.site.register(models.CarritoItemModel, AdminCarritoItem)
