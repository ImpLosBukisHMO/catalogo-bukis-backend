from django.urls import reverse
from rest_framework import serializers

from api.models import (
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
    DescuentosModel
)
from api import services
from api.utils.comprobantes import get_comprobante_display_name
from api.utils.imagenes import get_variante_imagen


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

# =========================
# Descuentos
# =========================
class DescuentosSerializer(serializers.ModelSerializer):
    es_valido = serializers.ReadOnlyField()

    class Meta:
        model = DescuentosModel
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
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=CategoriasModel.objects.all(),
        allow_null=True,
        required=False
    )
    descuento_especial = serializers.PrimaryKeyRelatedField(
        queryset=DescuentosModel.objects.all(),
        allow_null=True,
        required=False
    )

    class Meta:
        model = ProductosModel
        fields = [
            "id",
            "nombre",
            "imagen",
            "descripcion",
            "precio",
            "peso",
            "medidas",
            "capacidad",
            "categoria",
            "descuento_especial",
            "disponible",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Anidar categoría completa
        if instance.categoria:
            data["categoria"] = CategoriasSerializer(instance.categoria).data
            
            if instance.categoria.descuento_general:
                data["categoria"]["descuento"] = DescuentosSerializer(instance.categoria.descuento_general).data
            
        # Anidar descuento completo
        if instance.descuento_especial:
            data["descuento_especial"] = DescuentosSerializer(instance.descuento_especial).data
            
        return data


class ProductoMiniSerializer(serializers.ModelSerializer):
    categoria = CategoriasSerializer(read_only=True)

    class Meta:
        model = ProductosModel
        fields = ["id", "nombre", "imagen", "precio", "categoria"]


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
            "codigo_barras",
            "producto",
            "producto_id",
            "color",
            "color_id",
            "item",
            "precio",
            "stock",
            "activo",
            "disponible",
            "created_at",
            "updated_at",
        ]

    def get_disponible(self, obj):
        return obj.activo and obj.stock > 0
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Anidar categoría completa
        if instance.producto.categoria:
            data["producto"]["categoria"] = CategoriasSerializer(instance.producto.categoria).data
            
            if instance.producto.categoria.descuento_general:
                data["producto"]["categoria"]["descuento_general"] = DescuentosSerializer(instance.producto.categoria.descuento_general).data
            
        # Anidar descuento completo
        if instance.producto.descuento_especial:
            data["producto"]["descuento_especial"] = DescuentosSerializer(instance.producto.descuento_especial).data
            
        return data


class ProductoVariantesEnProductoSerializer(serializers.ModelSerializer):
    color = ColorMiniSerializer(read_only=True)
    disponible = serializers.SerializerMethodField()
    precio = serializers.DecimalField(
        source="precio_efectivo", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "item", "codigo_barras", "color", "precio", "stock", "activo", "disponible", "created_at", "updated_at"]

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
        qs = ProductoVariantesModel.objects.filter(producto=obj, activo=True).select_related("color", "producto")
        return ProductoVariantesEnProductoSerializer(qs, many=True).data


# =========================
# Favoritos
# =========================

class FavoritoVarianteSerializer(serializers.ModelSerializer):
    producto_id = serializers.IntegerField(source="producto.id", read_only=True)
    nombre_producto = serializers.CharField(source="producto.nombre", read_only=True)
    precio = serializers.DecimalField(
        source="precio_efectivo", max_digits=10, decimal_places=2, read_only=True
    )
    color = ColorMiniSerializer(read_only=True)
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "item", "stock", "activo", "producto_id", "nombre_producto", "precio", "color", "imagen"]

    def get_imagen(self, obj):
        return get_variante_imagen(obj)


class ProductosFavoritosSerializer(serializers.ModelSerializer):
    variante = FavoritoVarianteSerializer(read_only=True)
    variante_id = serializers.PrimaryKeyRelatedField(
        source="variante",
        queryset=ProductoVariantesModel.objects.all(),
        write_only=True,
    )

    class Meta:
        model = ProductosFavoritosModel
        fields = ["id", "variante", "variante_id"]


# =========================
# Pedidos
# =========================

class PedidosSerializer(serializers.ModelSerializer):
    folio = serializers.ReadOnlyField()

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "cliente",
            "clave",
            "public_id",
            "folio",
            "estado",
            "direccion",
            "subtotal_snapshot",
            "precio_total",
            "aprobado_eta",
            "denegado_razon",
            "nota_cliente",
            "nota_worker",
            "created_at",
            "updated_at",
        ]


class PedidoProductosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoProductosModel
        fields = "__all__"


# Serializers para el cliente (mis pedidos)

class ClientePedidoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoProductosModel
        fields = [
            "id",
            "cantidad",
            "producto_nombre_snapshot",
            "producto_item_snapshot",
            "color_nombre_snapshot",
            "color_hex_snapshot",
            "precio_unitario_snapshot",
            "descuento_porcentaje_snapshot",
            "subtotal_linea_snapshot",
            "imagen_principal_snapshot",
        ]


class ClientePedidoSerializer(serializers.ModelSerializer):
    items = ClientePedidoItemSerializer(many=True, read_only=True)
    folio = serializers.ReadOnlyField()
    comprobante_pago_subido = serializers.SerializerMethodField()
    comprobante_pago_nombre = serializers.SerializerMethodField()
    comprobante_pago_url = serializers.SerializerMethodField()

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "folio",
            "estado",
            "precio_total",
            "subtotal_snapshot",
            "nota_cliente",
            "nota_worker",
            "denegado_razon",
            "aprobado_eta",
            "comprobante_deadline",
            "comprobante_pago_subido",
            "comprobante_pago_nombre",
            "comprobante_pago_url",
            "created_at",
            "items",
        ]

    def get_comprobante_pago_subido(self, obj):
        return bool(obj.comprobante_pago)

    def get_comprobante_pago_nombre(self, obj):
        if not obj.comprobante_pago:
            return None
        return get_comprobante_display_name(obj.comprobante_pago)

    def get_comprobante_pago_url(self, obj):
        if not obj.comprobante_pago:
            return None
        return reverse("mi-pedido-comprobante", kwargs={"id": obj.id})


class ClientePedidoListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    folio = serializers.ReadOnlyField()
    comprobante_pago_subido = serializers.SerializerMethodField()

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "folio",
            "estado",
            "precio_total",
            "created_at",
            "comprobante_deadline",
            "items_count",
            "comprobante_pago_subido",
        ]

    def get_items_count(self, obj):
        return obj.items.count()

    def get_comprobante_pago_subido(self, obj):
        return bool(obj.comprobante_pago)


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
    item = serializers.CharField(source="variante.item", read_only=True)
    codigo_barras = serializers.CharField(source="variante.producto.codigo_barras", read_only=True)
    color_nombre = serializers.CharField(source="variante.color.nombre", read_only=True)
    color_hex = serializers.CharField(source="variante.color.hex", read_only=True)
    precio_unitario = serializers.DecimalField(
        source="variante.precio_efectivo",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    descuento = serializers.DecimalField(
        source="variante.producto.descuento_activo",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    subtotal_linea = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = CarritoItemModel
        fields = [
            "id",
            "variante_id",
            "cantidad",
            "item",
            "producto_id",
            "producto_nombre",
            "codigo_barras",
            "color_nombre",
            "color_hex",
            "precio_unitario",
            "descuento",
            "subtotal_linea",
            "imagen",
        ]

    def get_subtotal_linea(self, obj):
        return obj.variante.precio_efectivo * obj.cantidad

    def get_imagen(self, obj):
        return get_variante_imagen(obj.variante)


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
            total += it.variante.precio_efectivo * it.cantidad
        return total
