from rest_framework import serializers

from .models import (
    ProductosModel,
    ColorModel,
    ProductoVariantesModel,
    DireccionesModel,
    PedidosModel,
    PedidoProductosModel,
    ProductosFavoritosModel,
    CategoriasModel,
    UsuariosModel,
    ProductosImagenesModel,
    CarritoModel,
    CarritoItemModel,
)
from . import services


# =========================
# Usuarios
# =========================

class UsuariosSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    def to_internal_value(self, data):
        datos = super().to_internal_value(data)
        if self.instance is not None:
            return datos
        return services.DataClassUsuarios(**datos)

    def update(self, instance, validated_data):
        instance.nombre = validated_data.get("nombre", instance.nombre)
        instance.apellido = validated_data.get("apellido", instance.apellido)
        instance.correo = validated_data.get("correo", instance.correo)
        instance.telefono = validated_data.get("telefono", instance.telefono)

        if "password" in validated_data:
            instance.set_password(validated_data["password"])

        instance.save()
        return instance

    class Meta:
        model = UsuariosModel
        fields = ["id", "nombre", "apellido", "correo", "telefono", "password"]


# =========================
# Catálogos
# =========================

class CategoriasSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriasModel
        fields = "__all__"


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ["id", "nombre", "hex", "created_at", "updated_at"]


class ColorMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ["id", "nombre", "hex"]


# =========================
# Productos
# =========================

class ProductosSerializer(serializers.ModelSerializer):
    categorias = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CategoriasModel.objects.all()
    )

    class Meta:
        model = ProductosModel
        fields = [
            "id",
            "nombre",
            "item",
            "imagen",
            "descripcion",
            "precio",
            "peso",
            "medidas",
            "capacidad",
            "categorias",
            "disponible",
            "created_at",
            "updated_at",
        ]


class ProductoMiniSerializer(serializers.ModelSerializer):
    categorias = CategoriasSerializer(many=True, read_only=True)

    class Meta:
        model = ProductosModel
        fields = ["id", "nombre", "imagen", "precio", "categorias"]


# =========================
# Imágenes
# =========================

class ProductosImagenesSerializer(serializers.ModelSerializer):
    producto = serializers.IntegerField(source="producto_id", read_only=True)
    variante = serializers.IntegerField(source="variante_id", read_only=True)

    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductosModel.objects.all(),
        source="producto",
        write_only=True,
    )
    variante_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductoVariantesModel.objects.all(),
        source="variante",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProductosImagenesModel
        fields = [
            "id",
            "producto",
            "producto_id",
            "variante",
            "variante_id",
            "imagen",
            "orden",
            "es_principal",
            "created_at",
            "updated_at",
        ]


# =========================
# Variantes
# =========================

class ProductoVariantesSerializer(serializers.ModelSerializer):
    producto = ProductoMiniSerializer(read_only=True)
    color = ColorMiniSerializer(read_only=True)

    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductosModel.objects.all(),
        source="producto",
        write_only=True,
    )
    color_id = serializers.PrimaryKeyRelatedField(
        queryset=ColorModel.objects.all(),
        source="color",
        write_only=True,
    )

    disponible = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = [
            "id",
            "producto",
            "producto_id",
            "color",
            "color_id",
            "stock",
            "activo",
            "disponible",
            "created_at",
            "updated_at",
        ]

    def get_disponible(self, obj):
        return obj.activo and obj.stock > 0


class ProductoVariantesEnProductoSerializer(serializers.ModelSerializer):
    color = ColorMiniSerializer(read_only=True)
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "color", "stock", "activo", "disponible", "created_at", "updated_at"]

    def get_disponible(self, obj):
        return obj.activo and obj.stock > 0


# =========================
# Producto detalle
# =========================

class ProductoDetalleSerializer(ProductosSerializer):
    variantes = serializers.SerializerMethodField()

    class Meta(ProductosSerializer.Meta):
        fields = ProductosSerializer.Meta.fields + ["variantes"]

    def get_variantes(self, obj):
        qs = ProductoVariantesModel.objects.filter(producto=obj).select_related("color")
        return ProductoVariantesEnProductoSerializer(qs, many=True).data


# =========================
# Favoritos
# =========================

class ProductosFavoritosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosFavoritosModel
        fields = "__all__"


# =========================
# Pedidos
# =========================

class PedidosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidosModel
        fields = "__all__"


class PedidoProductosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoProductosModel
        fields = "__all__"


# =========================
# Direcciones
# =========================

class DireccionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionesModel
        fields = "__all__"


# =========================
# Carrito
# =========================

class CarritoItemCreateSerializer(serializers.Serializer):
    variante_id = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


class CarritoItemUpdateSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)


class CarritoItemReadSerializer(serializers.ModelSerializer):
    producto_id = serializers.IntegerField(source="variante.producto_id", read_only=True)
    producto_nombre = serializers.CharField(source="variante.producto.nombre", read_only=True)
    color_nombre = serializers.CharField(source="variante.color.nombre", read_only=True)
    color_hex = serializers.CharField(source="variante.color.hex", read_only=True)
    precio_unitario = serializers.DecimalField(
        source="variante.producto.precio",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    subtotal_linea = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = CarritoItemModel
        fields = [
            "id",
            "variante_id",
            "cantidad",
            "producto_id",
            "producto_nombre",
            "color_nombre",
            "color_hex",
            "precio_unitario",
            "subtotal_linea",
            "imagen",
        ]

    def get_subtotal_linea(self, obj):
        return obj.variante.producto.precio * obj.cantidad

    def get_imagen(self, obj):
        p = obj.variante.producto

        # Imagen principal del producto (tabla productos_imagenes)
        img = (
            ProductosImagenesModel.objects
            .filter(producto=p, es_principal=True)
            .order_by("orden", "id")
            .first()
        )

        if img:
            return img.imagen.url if hasattr(img.imagen, "url") else str(img.imagen)

        # Fallback: imagen directa del producto
        return p.imagen.url if hasattr(p.imagen, "url") else str(p.imagen)


class CarritoReadSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CarritoModel
        fields = ["id", "estado", "subtotal", "items"]

    def get_items(self, obj):
        qs = obj.items.select_related(
            "variante__producto",
            "variante__color"
        ).all()
        return CarritoItemReadSerializer(qs, many=True).data

    def get_subtotal(self, obj):
        total = 0
        for it in obj.items.select_related("variante__producto").all():
            total += it.variante.producto.precio * it.cantidad
        return total


# =========================
# Worker (sin categoria FK)
# =========================

class WorkerVariantSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    stock = serializers.IntegerField()
    disponible = serializers.BooleanField()
    color = ColorMiniSerializer()
    producto = serializers.SerializerMethodField()
    imagen_principal = serializers.SerializerMethodField()

    def get_producto(self, obj):
        p = obj.producto
        return {
            "id": p.id,
            "nombre": p.nombre,
            "precio": p.precio,
            "categorias": [c.id for c in p.categorias.all()],
        }

    def get_imagen_principal(self, obj):
        img = (
            ProductosImagenesModel.objects
            .filter(variante=obj, es_principal=True)
            .order_by("orden", "id")
            .first()
        )
        if img:
            return img.imagen.url if hasattr(img.imagen, "url") else str(img.imagen)

        p = obj.producto
        return p.imagen.url if hasattr(p.imagen, "url") else str(p.imagen)