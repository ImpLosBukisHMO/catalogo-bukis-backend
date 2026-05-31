from rest_framework.response import Response
from rest_framework.decorators import api_view
from api.models import *
from ..serializers import *

# Initial mock response.
@api_view(['GET'])
def getMockData(request):
    datos = {
        'mensaje': 'Bienvenido a la API del Catálogo de Importaciones Los Bukis.'
        }
    return Response(datos)

# Mock data w/ req param.
@api_view(['GET'])
def getMockDataParam(request, param):
    data = {
            'param': param
        }
    return Response(data)