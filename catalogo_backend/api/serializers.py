from rest_framework import serializers
from api.models import *

class UsuariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuariosModel
        fields = '__all__'

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