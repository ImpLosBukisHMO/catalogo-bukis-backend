# Aquí van todos los serializers del cliente

# api/serializer/client.py
from rest_framework import serializers
from api.models import UsuariosModel, BannerOfertaModel

class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuariosModel
        fields = [
            "id",
            "nombre",
            "apellido",
            "correo",
            "telefono",
            "is_admin",
            "is_staff",
            "is_superuser",
        ]


class BannerOfertaPublicSerializer(serializers.ModelSerializer):
    """Vista pública mínima del banner de ofertas para la home."""
    class Meta:
        model = BannerOfertaModel
        fields = ["id", "tipo", "archivo", "orden"]
