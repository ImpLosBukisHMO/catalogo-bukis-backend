from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import uuid
import os


def get_product_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('media/img/products/', filename)

def default_color_metadata():
    return {"colores": []}

# Administrador de cuentas.
class AdministradorDeUsuarios(BaseUserManager): 
    def create_user(self, nombre, apellido, correo, telefono, 
                    password=None, staff=False, superuser=False):
        
        if not correo:
            raise ValueError("El usuario debe tener un correo electrónico.")
        if not nombre:
            raise ValueError("El usuario debe tener un nombre.")
        if not apellido:
            raise ValueError("El usuario debe tener un apellido.")
        if not telefono:
            raise ValueError("El usuario debe tener un número de teléfono.")
        if not password:
            raise ValueError("El usuario debe tener una contraseña.")
        
        usuario = self.model(correo=self.normalize_email(correo))
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.telefono = telefono
        usuario.set_password(password)
        usuario.is_active = True
        usuario.is_staff = staff
        usuario.is_superuser = superuser
        usuario.save()

        return usuario
    
    def create_superuser(self, nombre, apellido, correo, telefono, password):
        usuario = self.create_user(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            telefono=telefono,
            password=password,
            staff=True,
            superuser=True
        )
        usuario.is_admin = True
        usuario.save()

        return usuario


# Usuarios (cliente, admin).
class UsuariosModel(AbstractUser):
    username = None
    nombre = models.CharField(max_length=100, null=False, default='', verbose_name='Nombre(s)')
    apellido = models.CharField(max_length=100, null=False, default='', verbose_name='Apellido(s)')
    correo = models.EmailField(unique=True, verbose_name='Correo electrónico')
    telefono = models.CharField(max_length=30, null=False, verbose_name='Teléfono')
    password = models.CharField(max_length=255, null=False, verbose_name='Contraseña')
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido', 'telefono']

    objects = AdministradorDeUsuarios()

    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    def has_module_perms(self, app_label):
        return True
    
    def has_perm(self, perm, obj=None):
        return self.is_admin


# Categorias de productos.
class CategoriasModel(models.Model):
    nombre = models.CharField(max_length=50, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos.
class ProductosModel(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    item = models.CharField(max_length=50, null=False)
    imagen = models.ImageField(upload_to=get_product_image_path, null=False)
    descripcion = models.TextField(default="")
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    medidas = models.TextField(null=False)
    capacidad = models.CharField(max_length=50, null=True, blank=True)
    colores_meta_datos = models.JSONField(default=default_color_metadata)
    categoria = models.ForeignKey(CategoriasModel, on_delete=models.CASCADE)
    #activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# Productos favoritos.
class ProductosFavoritosModel(models.Model):
    usuario = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    producto = models.ForeignKey(ProductosModel, on_delete=models.CASCADE)

# Pedidos de los clientes.
class PedidosModel(models.Model):
    cliente = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    clave = models.CharField(max_length=255, null=False)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)