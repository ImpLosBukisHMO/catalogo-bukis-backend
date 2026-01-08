from django.contrib import admin
from . import models

class AdminUsuario(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'apellido', 'correo', 'telefono')

class AdminDireccion(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'calle', 'colonia', 'codigo_postal', 'ciudad', 'estado', 'pais')

class AdminCategorias(admin.ModelAdmin):
    list_display = ('id', 'nombre')

class AdminPedidos(admin.ModelAdmin):
    list_display = ('id', 'clave', 'cliente', 'precio_total')

class AdminPedidoProductos(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'producto', 'cantidad', 'color', 'precio_unitario_producto')

admin.site.register(models.UsuariosModel, AdminUsuario)
admin.site.register(models.DireccionesModel, AdminDireccion)
admin.site.register(models.CategoriasModel, AdminCategorias)
admin.site.register(models.PedidosModel, AdminPedidos)
admin.site.register(models.PedidoProductosModel, AdminPedidoProductos)