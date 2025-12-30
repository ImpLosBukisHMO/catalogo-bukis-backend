from django.http import Http404
from rest_framework import generics, status
from rest_framework.response import Response
from api.models import CategoriasModel
from ..serializers import CategoriasSerializer

"""
////////////////////////////
Views de categorías
////////////////////////////
"""
class CategoriasListCreate(generics.ListCreateAPIView):
    queryset = CategoriasModel.objects.all()
    serializer_class = CategoriasSerializer

    def post(self, request, *args, **kwargs):
        serializer = CategoriasSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Categoría creada existosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        usuarios = CategoriasModel.objects.all()
        serializer = CategoriasSerializer(usuarios, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class CategoriasRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = CategoriasModel.objects.all()
    serializer_class = CategoriasSerializer
    lookup_field = 'id'

    # Obtener info de usuario por ID.
    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Categoría no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    

    # Actualizar usuario por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos de la categoría actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    # Eliminar usuario por ID.
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'mensaje': 'Categoría eliminada con éxito.'}, status=status.HTTP_200_OK)