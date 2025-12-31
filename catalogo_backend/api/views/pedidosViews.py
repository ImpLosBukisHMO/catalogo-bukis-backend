from django.http import Http404
from rest_framework import generics, status
from rest_framework.response import Response
from ..serializers import PedidosSerializer
from api.models import PedidosModel

class PedidosListCreate(generics.ListCreateAPIView):
    queryset = PedidosModel.objects.all()
    serializer_class = PedidosSerializer


    def post(self, request, *args, **kwargs):
        serializer = PedidosSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'mensaje':'Pedido creado existosamente.', 'datos': request.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        pedidos = PedidosModel.objects.all()
        serializer = PedidosSerializer(pedidos, many=True)
        return Response({'datos': serializer.data}, status=status.HTTP_200_OK)


class PedidosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = PedidosModel.objects.all()
    serializer_class = PedidosSerializer
    lookup_field = 'id'


    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    

    # Actualizar pedido por ID.
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
    
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'mensaje': 'Pedido eliminado con éxito.'}, status=status.HTTP_204_NO_CONTENT)