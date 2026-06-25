# Aquí van todos los serializers del worker

from rest_framework import serializers
from api.models import (
    ProductosModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    ColorModel,
    PedidosModel,
)
from api.utils.imagenes import get_variante_imagen

# para productos
class WorkerVariantSerializer(serializers.ModelSerializer):
    variant_id = serializers.IntegerField(source="id")

    producto = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    imagen_principal = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = [
            "variant_id",
            "item",
            "codigo_barras",
            "producto",
            "color",
            "stock",
            "activo",
            "imagen_principal",
        ]

    # -------------------------
    # Producto
    # -------------------------
    def get_producto(self, obj):
        p = obj.producto
        return {
            "id": p.id,
            "nombre": p.nombre,
            "precio": str(obj.precio_efectivo),
            "categorias": [c.id for c in p.categorias.all()],
        }

    # -------------------------
    # Color
    # -------------------------
    def get_color(self, obj):
        c = obj.color
        return {
            "id": c.id,
            "nombre": c.nombre,
            "hex": c.hex,
        }

    # -------------------------
    # Imagen principal
    # -------------------------
    def get_imagen_principal(self, obj):
        return get_variante_imagen(obj)


# para pedidos
class WorkerPedidoSerializer(serializers.ModelSerializer):
    cliente = serializers.SerializerMethodField()
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "cliente",
            "estado",
            "precio_total",
            "items_count",
            "created_at",
        ]

    def get_cliente(self, obj):
        return {
            "id": obj.cliente.id,
            "nombre": f"{obj.cliente.nombre} {obj.cliente.apellido}",
            "correo": obj.cliente.correo,
        }


# =========================
# WORKER - DETALLE DE PEDIDO (con items)
# =========================
class WorkerPedidoItemSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField()
    nombre = serializers.CharField(source="producto_nombre_snapshot")
    item = serializers.CharField(source="producto_item_snapshot")
    color = serializers.CharField(source="color_nombre_snapshot")
    color_hex = serializers.CharField(source="color_hex_snapshot")
    precio_unitario = serializers.DecimalField(source="precio_unitario_snapshot", max_digits=10, decimal_places=2)
    subtotal = serializers.DecimalField(source="subtotal_linea_snapshot", max_digits=10, decimal_places=2)
    imagen = serializers.CharField(source="imagen_principal_snapshot")


class WorkerPedidoDetalleSerializer(serializers.ModelSerializer):
    cliente = serializers.SerializerMethodField()
    items = WorkerPedidoItemSerializer(many=True, read_only=True)

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "cliente",
            "estado",
            "precio_total",
            "subtotal_snapshot",
            "nota_cliente",
            "nota_worker",
            "denegado_razon",
            "aprobado_eta",
            "items",
            "created_at",
        ]

    def get_cliente(self, obj):
        return {
            "id": obj.cliente.id,
            "nombre": f"{obj.cliente.nombre} {obj.cliente.apellido}",
            "correo": obj.cliente.correo,
            "telefono": obj.cliente.telefono,
        }


# =========================
# WORKER - CAMBIAR ESTADO PEDIDO
# =========================
class WorkerCambiarEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=PedidosModel.EstadoPedido.choices)
    nota_worker = serializers.CharField(required=False, allow_blank=True)
    denegado_razon = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        pedido = self.context["pedido"]
        estado_actual = pedido.estado
        estado_nuevo = data["estado"]

        transiciones = PedidosModel.TRANSICIONES_VALIDAS.get(estado_actual, [])

        if estado_nuevo == estado_actual:
            raise serializers.ValidationError(
                f"El pedido ya se encuentra en estado '{estado_actual}'."
            )
        if estado_nuevo not in transiciones:
            raise serializers.ValidationError(
                f"Transición inválida: '{estado_actual}' → '{estado_nuevo}'. "
                f"Transiciones permitidas: {transiciones or 'ninguna'}."
            )
        if estado_nuevo == PedidosModel.EstadoPedido.DENEGADO and not data.get("denegado_razon"):
            raise serializers.ValidationError(
                "Se requiere 'denegado_razon' para denegar un pedido."
            )
        return data


# =========================
# WORKER - PRODUCTOS PROPIOS
# =========================
class WorkerProductoSerializer(serializers.ModelSerializer):
    categorias = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    categorias_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=__import__("api.models", fromlist=["CategoriasModel"]).CategoriasModel.objects.all(),
        source="categorias",
        required=False,
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
            "disponible",
            "categorias",
            "categorias_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# =========================
# WORKER - VARIANTE (crear para producto propio)
# =========================
class WorkerVarianteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "item", "color", "stock", "activo", "codigo_barras"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "item": {"allow_blank": True, "default": ""},
            "codigo_barras": {"allow_blank": True, "default": ""},
        }

    def validate_color(self, value):
        producto = self.context["producto"]
        if ProductoVariantesModel.objects.filter(producto=producto, color=value).exists():
            raise serializers.ValidationError(
                "Ya existe una variante con ese color para este producto."
            )
        return value

    def validate_item(self, value):
        """
        Reject duplicate non-empty item values within the same product.
        Empty string is allowed and may repeat (no constraint on item='').
        Excludes the current instance when updating (pk-based exclusion).
        """
        if not value:
            return value

        producto = self.context["producto"]
        instance = self.instance

        qs = ProductoVariantesModel.objects.filter(producto=producto, item=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "Este SKU ya está en uso para este producto."
            )
        return value


# =========================
# WORKER - IMAGEN (subir para producto propio)
# =========================
class WorkerImagenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosImagenesModel
        fields = ["id", "variante", "imagen", "orden", "es_principal"]
        read_only_fields = ["id"]
