from django.http import Http404
from rest_framework import generics, status
from rest_framework.response import Response
from api.models import DireccionesModel
from ..serializers import DireccionesSerializer

"""
/////////////////////////////////////
Views de direcciones de los clientes
/////////////////////////////////////
"""
class DireccionesListCreate(generics.ListCreateAPIView):
    queryset = DireccionesModel.objects.all()
    serializer_class = DireccionesSerializer

    def post(self, request, *args, **kwargs):
        serializer = DireccionesSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Dirección creada existosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        usuarios = DireccionesModel.objects.all()
        serializer = DireccionesSerializer(usuarios, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class DireccionesRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = DireccionesModel.objects.all()
    serializer_class = DireccionesSerializer
    lookup_field = 'id'

    # Obtener info de dirección por ID.
    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Dirección no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    

    # Actualizar dirección por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos de la dirección actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    # Eliminar usuario por ID.
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'mensaje': 'Dirección eliminada con éxito.'}, status=status.HTTP_200_OK)
    

class DireccionesUsuarioView(generics.ListAPIView):
    serializer_class = DireccionesSerializer

    def get(self, request, *args, **kwargs):
        id_usuario = self.kwargs.get("id_usuario")
        direcciones = DireccionesModel.objects.filter(usuario=id_usuario)
        serializer = DireccionesSerializer(direcciones, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)