from rest_framework import serializers
from .models import (
    ProductosModel, ColorModel, ProductoVariantesModel,
    DireccionesModel, PedidosModel, PedidoProductosModel,
    ProductosFavoritosModel, CategoriasModel, UsuariosModel,
    ProductosImagenesModel, CarritoModel, CarritoItemModel, ProductoVariantesModel, ProductosImagenesModel
)
from . import services

class UsuariosSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    password = serializers.CharField(write_only=True)

    def to_internal_value(self, data):
        datos = super().to_internal_value(data)
        return services.DataClassUsuarios(**datos)

    class Meta:
        model = UsuariosModel
        fields = ["nombre", "apellido", "correo", "telefono", "password", "id"]


class CategoriasSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriasModel
        fields = "__all__"


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ["id", "nombre", "hex", "created_at", "updated_at"]


class ProductosSerializer(serializers.ModelSerializer):
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
            "categoria",
            "disponible",
            "created_at",
            "updated_at",
        ]


class ProductoMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosModel
        fields = ["id", "nombre", "imagen", "precio", "categoria"]


class ColorMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ["id", "nombre", "hex"]


class ProductosImagenesSerializer(serializers.ModelSerializer):
    producto = serializers.IntegerField(source="producto_id", read_only=True)
    variante = serializers.IntegerField(source="variante_id", read_only=True)

    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductosModel.objects.all(),
        source="producto",
        write_only=True
    )
    variante_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductoVariantesModel.objects.all(),
        source="variante",
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = ProductosImagenesModel
        fields = [
            "id",
            "producto", "producto_id",
            "variante", "variante_id",
            "imagen",
            "orden",
            "es_principal",
            "created_at",
            "updated_at",
        ]


class ProductoVariantesSerializer(serializers.ModelSerializer):
    producto = ProductoMiniSerializer(read_only=True)
    color = ColorMiniSerializer(read_only=True)

    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductosModel.objects.all(),
        source="producto",
        write_only=True
    )
    color_id = serializers.PrimaryKeyRelatedField(
        queryset=ColorModel.objects.all(),
        source="color",
        write_only=True
    )

    disponible = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = [
            "id",
            "producto", "producto_id",
            "color", "color_id",
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


class ProductoDetalleSerializer(ProductosSerializer):
    variantes = serializers.SerializerMethodField()

    def get_variantes(self, obj):
        qs = (
            ProductoVariantesModel.objects
            .filter(producto=obj)
            .select_related("color")
        )
        return ProductoVariantesEnProductoSerializer(qs, many=True).data

    class Meta(ProductosSerializer.Meta):
        fields = ProductosSerializer.Meta.fields + ["variantes"]


class ProductosFavoritosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosFavoritosModel
        fields = "__all__"


class PedidosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidosModel
        fields = "__all__"


class PedidoProductosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoProductosModel
        fields = "__all__"


class DireccionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionesModel
        fields = "__all__"

class CarritoItemCreateSerializer(serializers.Serializer):
    variante_id = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)

class CarritoItemUpdateSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)

class CarritoItemReadSerializer(serializers.ModelSerializer):
    # Campos “bonitos” para debug rápido
    producto_id = serializers.IntegerField(source="variante.producto_id", read_only=True)
    producto_nombre = serializers.CharField(source="variante.producto.nombre", read_only=True)
    color_nombre = serializers.CharField(source="variante.color.nombre", read_only=True)
    color_hex = serializers.CharField(source="variante.color.hex", read_only=True)
    precio_unitario = serializers.DecimalField(source="variante.producto.precio", max_digits=10, decimal_places=2, read_only=True)
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
        precio = obj.variante.producto.precio
        return precio * obj.cantidad

    def get_imagen(self, obj):
        # prioridad: imagen principal de variante, luego primera, luego imagen principal del producto
        img = (
            ProductosImagenesModel.objects
            .filter(variante=obj.variante, es_principal=True)
            .order_by("orden", "id")
            .first()
        )
        if not img:
            img = (
                ProductosImagenesModel.objects
                .filter(variante=obj.variante)
                .order_by("orden", "id")
                .first()
            )
        if img:
            return img.imagen.url if hasattr(img.imagen, "url") else str(img.imagen)

        # fallback: imagen del producto
        p = obj.variante.producto
        return p.imagen.url if hasattr(p.imagen, "url") else str(p.imagen)


class CarritoReadSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CarritoModel
        fields = ["id", "estado", "subtotal", "items"]

    def get_items(self, obj):
        qs = (
            obj.items
            .select_related("variante__producto", "variante__color")
            .all()
            .order_by("id")
        )
        return CarritoItemReadSerializer(qs, many=True).data

    def get_subtotal(self, obj):
        total = 0
        qs = obj.items.select_related("variante__producto").all()
        for it in qs:
            total += (it.variante.producto.precio * it.cantidad)
        return total
