from django.http import Http404
from rest_framework import generics, status
from rest_framework.response import Response
from api.models import UsuariosModel
from ..serializers import UsuariosSerializer

"""
////////////////////////////
Views de usuarios
////////////////////////////
"""
class UsuariosListCreate(generics.ListCreateAPIView):
    queryset = UsuariosModel.objects.all()
    serializer_class = UsuariosSerializer

    def post(self, request, *args, **kwargs):
        serializer = UsuariosSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Usuario creado existosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        usuarios = UsuariosModel.objects.all()
        serializer = UsuariosSerializer(usuarios, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class UsuariosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = UsuariosModel.objects.all()
    serializer_class = UsuariosSerializer
    lookup_field = 'id'

    # Obtener info de usuario por ID.
    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    

    # Actualizar usuario por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    # Eliminar usuario por ID.
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'mensaje': 'Usuario eliminado con éxito.'}, status=status.HTTP_200_OK)