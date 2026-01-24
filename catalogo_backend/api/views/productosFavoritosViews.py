from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import IntegrityError, transaction

from api.models import ProductosFavoritosModel
from api.serializers import ProductosFavoritosSerializer


class ProductosFavoritosListCreate(generics.ListCreateAPIView):
    serializer_class = ProductosFavoritosSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return ProductosFavoritosModel.objects.none()

        qs = ProductosFavoritosModel.objects.all()

        usuario = self.request.query_params.get("usuario")
        if usuario:
            qs = qs.filter(usuario_id=usuario)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = serializer.validated_data["usuario"]
        producto = serializer.validated_data["producto"]

        try:
            with transaction.atomic():
                obj, created = ProductosFavoritosModel.objects.get_or_create(
                    usuario=usuario,
                    producto=producto,
                )
        except IntegrityError:
            obj = ProductosFavoritosModel.objects.get(usuario=usuario, producto=producto)
            created = False

        out = self.get_serializer(obj).data
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out, status=code)


class ProductosFavoritosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductosFavoritosModel.objects.all()
    serializer_class = ProductosFavoritosSerializer
    lookup_field = "id"