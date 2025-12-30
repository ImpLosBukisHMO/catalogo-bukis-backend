from django.db import models

# Usuarios (cliente, admin).
class UsuariosModel(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    apellido = models.CharField(max_length=100, null=True, blank=True)
    contrasena = models.CharField(max_length=254, null=False)
    correo = models.EmailField(max_length=254, null=False)
    telefono = models.CharField(max_length=20, null=False)
    rol = models.CharField(max_length=20, null=False)       # ej.: 'admin', 'cliente'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Categorias de productos.
class CategoriasModel(models.Model):
    nombre = models.CharField(max_length=50, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos.
class ProductosModel(models.Model):
    def default_color_metadata():
        return {"colores": []}

    nombre = models.CharField(max_length=100, null=False)
    item = models.CharField(max_length=50, null=False)
    imagen = models.ImageField(upload_to='media/img/productos', null=False)
    descripcion = models.TextField(default="")
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    medidas = models.TextField(null=False)
    capacidad = models.CharField(max_length=50, null=True, blank=True)
    colores_meta_datos = models.JSONField(default=default_color_metadata)
    categoria = models.ForeignKey(CategoriasModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos favoritos.
class ProductosFavoritosModel(models.Model):
    usuario = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    producto = models.ForeignKey(ProductosModel, on_delete=models.CASCADE)

# Pedidos de los clientes.
class PedidosModel(models.Model):
    cliente = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    clave = models.CharField(max_length=254, null=False)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos dentro de los pedidos.
class PedidoProductosModel(models.Model):
    pedido = models.ForeignKey(PedidosModel, on_delete=models.CASCADE)
    producto = models.ForeignKey(ProductosModel, on_delete=models.CASCADE)
    cantidad = models.IntegerField(null=False)
    color = models.CharField(max_length=50, null=False)
    precio_unitario_producto = models.DecimalField(max_digits=10, decimal_places=2)


# Direcciones de los usuarios.
class DireccionesModel(models.Model):
    usuario = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    calle = models.CharField(max_length=100, null=False)
    colonia = models.CharField(max_length=100, null=False)
    codigo_postal = models.CharField(max_length=50, null=False)
    ciudad = models.CharField(max_length=50, null=False)
    estado = models.CharField(max_length=50, null=False)
    pais = models.CharField(max_length=50, null=False)