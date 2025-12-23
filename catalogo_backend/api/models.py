from django.contrib.postgres.fields import ArrayField
from django.db import models

# Usuarios (cliente, admin).
class Usuarios(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    apellido = models.CharField(max_length=100, null=True, blank=True)
    contrasena = models.CharField(max_length=255, null=False)
    correo = models.CharField(max_length=255, null=False)
    telefono = models.CharField(max_length=20, null=False)
    rol = models.UniqueConstraint(fields=['admin', 'cliente'])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Categorias de productos.
class Categorias(models.Model):
    nombre = models.CharField(max_length=50, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos.
class Productos(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    medidas = models.TextField(null=False)
    capacidad = models.CharField(max_length=50, null=True, blank=True)
    color = ArrayField(models.CharField(max_length=50), null=True, default=list)
    categoria = models.ForeignKey(Categorias, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos favoritos.
class ProductosFavoritos(models.Model):
    usuario = models.ForeignKey(Usuarios, on_delete=models.CASCADE)
    producto = models.ForeignKey(Productos, on_delete=models.CASCADE)

# Pedidos de los clientes.
class Pedidos(models.Model):
    cliente = models.ForeignKey(Usuarios, on_delete=models.CASCADE)
    clave = models.CharField(max_length=255, null=False)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos dentro de los pedidos.
class PedidoProductos(models.Model):
    pedido = models.ForeignKey(Pedidos, on_delete=models.CASCADE)
    producto = models.ForeignKey(Productos, on_delete=models.CASCADE)
    cantidad = models.IntegerField(null=False)
    color = models.CharField(max_length=50, null=False)
    precio_unitario_producto = models.DecimalField(max_digits=10, decimal_places=2)


# Direcciones de los usuarios.
class Direcciones(models.Model):
    usuario = models.ForeignKey(Usuarios, on_delete=models.CASCADE)
    calle = models.CharField(max_length=100, null=False)
    colonia = models.CharField(max_length=100, null=False)
    codigo_postal = models.CharField(max_length=50, null=False)
    ciudad = models.CharField(max_length=50, null=False)
    estado = models.CharField(max_length=50, null=False)
    pais = models.CharField(max_length=50, null=False)