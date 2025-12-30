from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from api.models import *
from ..serializers import *

# Initial mock response.
@api_view(['GET'])
def getMockData(request):
    data = {
        'usuario_de_prueba': {
            'id': 1,
            'nombre': 'Juan',
            'apellido': 'Medina',
            'correo_electronico': 'juan.medina2@email.com'
            }
        }
    return Response(data)

# Mock data w/ req param.
@api_view(['GET'])
def getMockDataParam(request, param):
    data = {
            'param': param
        }
    return Response(data)