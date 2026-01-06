from django.contrib import admin
from . import models

class AdminUsuario(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'apellido', 'correo', 'telefono')

class AdminDireccion(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'calle', 'colonia', 'codigo_postal', 'ciudad', 'estado', 'pais')

class AdminCategorias(admin.ModelAdmin):
    list_display = ('id', 'nombre')

admin.site.register(models.UsuariosModel, AdminUsuario)
admin.site.register(models.DireccionesModel, AdminDireccion)
admin.site.register(models.CategoriasModel, AdminCategorias)