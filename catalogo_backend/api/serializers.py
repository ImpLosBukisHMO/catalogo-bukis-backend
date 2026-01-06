from rest_framework import serializers
from api.models import *
from . import services

class UsuariosSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    correo = serializers.EmailField()
    telefono = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True)

    def to_internal_value(self, data):
        datos = super().to_internal_value(data)
        return services.DataClassUsuarios(**datos)
    
    class Meta:
        model = UsuariosModel
        fields = ['nombre', 'apellido', 'correo', 'telefono', 'password', 'id']


class CategoriasSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriasModel
        fields = '__all__'

class ProductosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosModel
        fields = '__all__'

class ProductosFavoritosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosFavoritosModel
        fields = '__all__'

class PedidosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidosModel
        fields = '__all__'

class PedidoProductosSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoProductosModel
        fields = '__all__'

class DireccionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionesModel
        fields = '__all__'