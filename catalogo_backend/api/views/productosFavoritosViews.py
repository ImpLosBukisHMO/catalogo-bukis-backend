from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import IntegrityError, transaction

from api.models import ProductosFavoritosModel
from api.serializers import ProductosFavoritosSerializer


class ProductosFavoritosListCreate(generics.ListCreateAPIView):
    serializer_class = ProductosFavoritosSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ProductosFavoritosModel.objects
            .filter(usuario=self.request.user)
            .select_related(
                "variante__producto",
                "variante__color",
            )
            .prefetch_related("variante__imagenes")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variante = serializer.validated_data["variante"]

        try:
            with transaction.atomic():
                obj, created = ProductosFavoritosModel.objects.get_or_create(
                    usuario=request.user,
                    variante=variante,
                )
        except IntegrityError:
            obj = ProductosFavoritosModel.objects.get(
                usuario=request.user, variante=variante
            )
            created = False

        out = self.get_serializer(obj).data
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out, status=code)


class ProductosFavoritosRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductosFavoritosSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return ProductosFavoritosModel.objects.filter(usuario=self.request.user)
