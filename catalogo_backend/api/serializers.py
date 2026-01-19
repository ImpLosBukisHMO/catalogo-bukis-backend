from rest_framework import serializers
from .models import (
    ProductosModel, ColorModel, ProductoVariantesModel,
    DireccionesModel, PedidosModel, PedidoProductosModel,
    ProductosFavoritosModel, CategoriasModel, UsuariosModel,
    ProductosImagenesModel
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
