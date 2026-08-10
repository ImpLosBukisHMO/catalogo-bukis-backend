from django.http import Http404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from api.models import DescuentosModel
from api.permissions import CanManageDiscountCodes
from ..serializers import DescuentosSerializer

"""
/////////////////////////////////////
Views de los descuentos
/////////////////////////////////////
"""
class DescuentosListCreate(generics.ListCreateAPIView):
    queryset = DescuentosModel.objects.all()
    serializer_class = DescuentosSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), CanManageDiscountCodes()]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Descuento creado exitosamente.', 'datos': serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class DescuentosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = DescuentosModel.objects.all()
    serializer_class = DescuentosSerializer
    lookup_field = 'id'
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), CanManageDiscountCodes()]

    # Obtener info del descuento por ID.
    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({'datos': serializer.data}, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Descuento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    # Actualizar descuento por ID.
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos del descuento actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'mensaje': 'Datos del descuento actualizados con éxito.',
                    'datos': serializer.data
                }, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Eliminar descuento por ID.
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'mensaje': 'Descuento eliminado con éxito.'}, status=status.HTTP_200_OK)