# pyrefly: ignore [missing-import]
from django.core.exceptions import ValidationError
# pyrefly: ignore [missing-import]
from django.db import models
# pyrefly: ignore [missing-import]
from django.contrib.auth.models import AbstractUser, BaseUserManager
# pyrefly: ignore [missing-import]
from django.core.validators import RegexValidator
# pyrefly: ignore [missing-import]
from django.db.models import Q
import uuid
import os
# pyrefly: ignore [missing-import]
from django.utils import timezone

hex_color_validator = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message="El color hex debe venir como #RRGGBB, por ejemplo #FFAA00",
)


def get_product_image_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("img/products/", filename)


def get_banner_oferta_path(instance, filename):
    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("img/banner-ofertas/", filename)


def default_color_metadata():
    return {"colores": []}


# Administrador de cuentas.
class AdministradorDeUsuarios(BaseUserManager):
    def create_user(
        self,
        nombre,
        apellido,
        correo,
        telefono,
        password=None,
        staff=False,
        superuser=False,
    ):
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
            superuser=True,
        )
        usuario.is_admin = True
        usuario.save()

        return usuario


# Usuarios (cliente, admin).
class UsuariosModel(AbstractUser):
    username = None
    nombre = models.CharField(max_length=100, null=False, default="", verbose_name="Nombre(s)")
    apellido = models.CharField(max_length=100, null=False, default="", verbose_name="Apellido(s)")
    correo = models.EmailField(unique=True, verbose_name="Correo electrónico")
    telefono = models.CharField(max_length=30, null=False, verbose_name="Teléfono")
    password = models.CharField(max_length=255, null=False, blank=True, verbose_name="Contraseña")

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre", "apellido", "telefono"]

    objects = AdministradorDeUsuarios()

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    def has_module_perms(self, app_label):
        return True

    def has_perm(self, perm, obj=None):
        return self.is_admin

# Descuentos.
class DescuentosModel(models.Model):
    class DescuentoType(models.TextChoices):
        GENERAL = "general", "General"
        ESPECIAL = "especial", "Especial"

    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=DescuentoType.choices, default=DescuentoType.GENERAL)
    porcentaje = models.DecimalField(max_digits=10, decimal_places=2, null=False, default=0)
    activo = models.BooleanField(default=False)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()

    def __str__(self):
        return self.nombre
    
    @property
    def es_valido(self):
        hoy = timezone.now()
        return self.activo and (self.fecha_inicio <= hoy <= self.fecha_fin)

# Categorias de productos.
class CategoriasModel(models.Model):
    nombre = models.CharField(max_length=50, null=False)
    descuento_general = models.ForeignKey(
        DescuentosModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categorias_descuentos"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre


# Productos.
class ProductosModel(models.Model):
    class EstadoProducto(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    nombre = models.CharField(max_length=100, null=False)
    imagen = models.ImageField(upload_to=get_product_image_path, null=False)
    descripcion = models.TextField(default="")
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    medidas = models.TextField(null=False)
    capacidad = models.CharField(max_length=50, null=True, blank=True)
    disponible = models.BooleanField(default=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoProducto.choices,
        default=EstadoProducto.DRAFT,
        db_index=True,
    )
    categoria = models.ForeignKey(
        CategoriasModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos"
    )
    # Worker Panel: worker dueño del producto (null = producto de admin/sin dueño)
    worker = models.ForeignKey(
        "UsuariosModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_propios",
        limit_choices_to={"is_staff": True},
    )
    descuento_especial = models.ForeignKey(
        DescuentosModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_descuentos"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def _active_variants_queryset(self):
        return self.producto_colores.filter(activo=True)

    @staticmethod
    def _has_non_blank_sku(value):
        return bool((value or "").strip())

    def get_publish_validation_errors(self):
        errors = {}
        active_variants = self._active_variants_queryset()

        if not self.disponible:
            errors["disponible"] = [
                "El producto debe estar disponible para publicarse."
            ]

        if not self.categoria:
            errors["categoria"] = [
                "El producto debe tener una categoría para publicarse."
            ]

        if not active_variants.exists():
            errors["variantes"] = [
                "El producto debe tener al menos una variante activa para publicarse."
            ]

        has_valid_sku = any(
            self._has_non_blank_sku(variant.item)
            for variant in active_variants.only("item")
        )
        if not has_valid_sku:
            errors["item"] = [
                "Al menos una variante activa debe tener un SKU válido para publicarse."
            ]

        publishable_variants = []
        for variant in active_variants.prefetch_related("imagenes"):
            has_valid_price = variant.precio_efectivo is not None and variant.precio_efectivo > 0
            has_valid_stock = variant.stock > 0
            has_variant_image = variant.imagenes.exists()

            if (
                has_valid_price
                and has_valid_stock
                and has_variant_image
                and self._has_non_blank_sku(variant.item)
            ):
                publishable_variants.append(variant.id)

        if not active_variants.filter(precio__gt=0).exists() and self.precio <= 0:
            errors["precio"] = [
                "Al menos una variante activa debe tener un precio válido para publicarse."
            ]

        if not active_variants.filter(stock__gt=0).exists():
            errors["stock"] = [
                "Al menos una variante activa debe tener stock válido para publicarse."
            ]

        if not active_variants.filter(imagenes__isnull=False).exists() and not self.imagen:
            errors["imagenes"] = [
                "El producto debe tener una imagen base o al menos una variante activa con imagen para poder publicarse."
            ]

        if not publishable_variants and "variantes" not in errors:
            errors.setdefault("estado", []).append(
                "El producto debe tener al menos una variante activa y publicable."
            )

        return errors

    def validate_can_publish(self):
        errors = self.get_publish_validation_errors()
        if errors:
            raise ValidationError(errors)
        
    def get_discounted_price(self, descuento):
        if descuento.activo:
            return self.precio - (self.precio * descuento.cantidad) / 100
        return self.precio

    def get_final_price(self):
        if self.descuento_especial and self.descuento_especial.activo:
            return self.get_discounted_price(self.precio, self.descuento_especial)
        return self.precio
    
    @property
    def descuento_activo(self):
        if self.descuento_especial and self.descuento_especial.es_valido:
            return self.descuento_especial.porcentaje
        elif self.categoria and self.categoria.descuento_general and self.categoria.descuento_general.es_valido:
            return self.categoria.descuento_general.porcentaje
        return None


# Colores.
class ColorModel(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    hex = models.CharField(max_length=7, unique=True, validators=[hex_color_validator])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "colores"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.hex})"


# Productos X Color (variantes por color).
class ProductoVariantesModel(models.Model):
    producto = models.ForeignKey(
        ProductosModel,
        on_delete=models.CASCADE,
        related_name="producto_colores",
    )
    color = models.ForeignKey(
        ColorModel,
        on_delete=models.PROTECT,
        related_name="color_productos",
    )

    item = models.CharField(max_length=50, null=False, default="")
    codigo_barras = models.CharField(max_length=30, null=False, blank=True, default="")
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "producto_colores"
        ordering = ["color__nombre", "id"]
        constraints = [
            models.UniqueConstraint(fields=["producto", "color"], name="uniq_producto_color"),
            models.UniqueConstraint(
                fields=["producto", "item"],
                condition=~Q(item=""),
                name="unique_producto_item_when_set",
            ),
        ]
        indexes = [
            models.Index(fields=["producto"]),
            models.Index(fields=["color"]),
        ]

    def __str__(self) -> str:
        return f"Producto {self.producto_id} - Color {self.color_id} - Stock {self.stock}"

    @property
    def precio_efectivo(self):
        base_price = self.precio if self.precio is not None else self.producto.precio
        
        # Revisar descuento del producto
        if self.producto.descuento_especial and self.producto.descuento_especial.es_valido:
            discount_pct = self.producto.descuento_especial.porcentaje
            return base_price - (base_price * discount_pct / 100)
        
        # Revisar descuento de la categoría
        elif self.producto.categoria and self.producto.categoria.descuento_general and self.producto.categoria.descuento_general.es_valido:
            discount_pct = self.producto.categoria.descuento_general.porcentaje
            return base_price - (base_price * discount_pct / 100)

        return base_price


# ProductosImagenes (galería y principal por producto o por variante).
class ProductosImagenesModel(models.Model):
    producto = models.ForeignKey(
        ProductosModel,
        on_delete=models.CASCADE,
        related_name="imagenes",
    )
    variante = models.ForeignKey(
        ProductoVariantesModel,
        on_delete=models.CASCADE,
        related_name="imagenes",
        null=True,
        blank=True,
    )

    imagen = models.ImageField(upload_to="img/products/galeria/")
    orden = models.PositiveIntegerField(default=0)
    es_principal = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden", "id"]
        indexes = [
            models.Index(fields=["producto", "variante"]),
        ]


# Productos favoritos.
class ProductosFavoritosModel(models.Model):
    usuario = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE)
    variante = models.ForeignKey(ProductoVariantesModel, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("usuario", "variante")


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


# =========================
# NUEVO: Carrito
# =========================

class CarritoModel(models.Model):
    class EstadoCarrito(models.TextChoices):
        ACTIVO = "ACTIVE", "Activo"
        CONVERTIDO = "CONVERTED", "Convertido"

    cliente = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE, related_name="carritos")
    estado = models.CharField(max_length=20, choices=EstadoCarrito.choices, default=EstadoCarrito.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["cliente", "estado"]),
        ]

    def __str__(self) -> str:
        return f"Carrito {self.id} - Cliente {self.cliente_id} - {self.estado}"


class CarritoItemModel(models.Model):
    carrito = models.ForeignKey(CarritoModel, on_delete=models.CASCADE, related_name="items")
    variante = models.ForeignKey(ProductoVariantesModel, on_delete=models.PROTECT, related_name="carrito_items")
    cantidad = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["carrito", "variante"], name="uniq_carrito_variante"),
        ]
        indexes = [
            models.Index(fields=["carrito"]),
            models.Index(fields=["variante"]),
        ]

    def __str__(self) -> str:
        return f"Carrito {self.carrito_id} - Variante {self.variante_id} - Cant {self.cantidad}"


# =========================
# Pedidos con estados y snapshots
# =========================

class PedidosModel(models.Model):
    class EstadoPedido(models.TextChoices):
        PENDIENTE = "PENDING", "Pendiente"
        APROBADO = "APPROVED", "Aprobado"
        DENEGADO = "DENIED", "Denegado"
        LISTO = "READY", "Listo"
        ENVIADO = "SHIPPED", "Enviado"
        COMPLETADO = "COMPLETED", "Completado"
        CANCELADO = "CANCELED", "Cancelado"

    # Transiciones válidas de estado (worker panel)
    TRANSICIONES_VALIDAS = {
        "PENDING": ["APPROVED", "DENIED"],
        "APPROVED": ["READY", "CANCELED"],
        "READY": ["SHIPPED", "CANCELED"],
        "SHIPPED": ["COMPLETED", "CANCELED"],
        "DENIED": [],
        "COMPLETED": [],
        "CANCELED": ["PENDING"],
    }

    cliente = models.ForeignKey(UsuariosModel, on_delete=models.CASCADE, related_name="pedidos")
    clave = models.CharField(max_length=255, null=False)
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    estado = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
        default=EstadoPedido.PENDIENTE,
    )

    direccion = models.ForeignKey(
        DireccionesModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    subtotal_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    aprobado_eta = models.DateTimeField(null=True, blank=True)
    denegado_razon = models.TextField(null=True, blank=True)

    nota_cliente = models.TextField(null=True, blank=True)
    nota_worker = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["cliente", "estado"]),
            models.Index(fields=["estado", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Pedido {self.folio} - Cliente {self.cliente_id} - {self.estado}"

    @property
    def folio(self):
        return f"{self.id:06d}"


class PedidoProductosModel(models.Model):
    pedido = models.ForeignKey(PedidosModel, on_delete=models.CASCADE, related_name="items")

    # Nuevo: referencia a variante (nullable para que el pedido no se rompa si borran la variante)
    variante = models.ForeignKey(
        ProductoVariantesModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedido_items",
    )

    cantidad = models.PositiveIntegerField(null=False)

    # Snapshots por línea (lo que el cliente compró en ese momento)
    producto_nombre_snapshot = models.CharField(max_length=100, null=False, default="")
    producto_item_snapshot = models.CharField(max_length=50, null=False, default="")
    descripcion_snapshot = models.TextField(null=False, default="")

    color_nombre_snapshot = models.CharField(max_length=50, null=False, default="")
    color_hex_snapshot = models.CharField(max_length=7, null=False, default="")

    precio_unitario_snapshot = models.DecimalField(max_digits=10, decimal_places=2, null=False, default=0)
    # Porcentaje de descuento vigente en el momento del checkout (0 = sin descuento)
    descuento_porcentaje_snapshot = models.DecimalField(max_digits=5, decimal_places=2, null=False, default=0)
    subtotal_linea_snapshot = models.DecimalField(max_digits=10, decimal_places=2, null=False, default=0)

    imagen_principal_snapshot = models.CharField(max_length=500, null=False, default="")

    # Legacy (opcional): para no romper datos viejos mientras migras
    producto = models.ForeignKey(ProductosModel, on_delete=models.SET_NULL, null=True, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    precio_unitario_producto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["variante"]),
        ]

    def __str__(self) -> str:
        return f"Pedido {self.pedido.folio} - Variante {self.variante_id} - Cant {self.cantidad}"