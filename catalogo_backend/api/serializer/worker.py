from rest_framework import serializers
from api.models import (
    ProductoVariantesModel,
    ProductosImagenesModel,
)

class WorkerVariantSerializer(serializers.ModelSerializer):
    variant_id = serializers.IntegerField(source="id")

    producto = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    imagen_principal = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = [
            "variant_id",
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
            "item": p.item,
            "precio": str(p.precio),
            "categoria": p.categoria.nombre if p.categoria else None,
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
        # 1. Imagen principal de la variante
        img = (
            ProductosImagenesModel.objects
            .filter(variante=obj, es_principal=True)
            .first()
        )

        # 2. Fallback: imagen principal del producto
        if not img:
            img = (
                ProductosImagenesModel.objects
                .filter(producto=obj.producto, es_principal=True)
                .first()
            )

        return img.imagen.url if img else None
