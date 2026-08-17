# api/views/productosImagenesViews.py
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS

from api.models import ProductosImagenesModel
from api.permissions import CanEditProducts
from api.serializers import ProductosImagenesSerializer
from api.utils.imagenes import get_existing_product_images


class ProductosImagenesListCreateView(generics.ListCreateAPIView):
    queryset = ProductosImagenesModel.objects.all()
    serializer_class = ProductosImagenesSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), CanEditProducts()]

    def get_queryset(self):
        qs = ProductosImagenesModel.objects.all().select_related("producto", "variante").order_by("orden", "id")

        producto_id = self.request.query_params.get("producto")
        variante_id = self.request.query_params.get("variante")

        if producto_id:
            qs = qs.filter(producto_id=producto_id)

        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        if self.request.method in SAFE_METHODS:
            return get_existing_product_images(qs)

        return qs

    def perform_create(self, serializer):
        producto = serializer.validated_data.get("producto")
        self._ensure_partial_worker_owns_product(producto)
        serializer.save()

    def _ensure_partial_worker_owns_product(self, producto):
        user = self.request.user
        if getattr(user, "worker_role", "none") != "parcial":
            return
        if producto is None or producto.worker_id != user.id:
            raise PermissionDenied("No tienes permisos para modificar imágenes de este producto.")


class ProductosImagenesDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductosImagenesModel.objects.all()
    serializer_class = ProductosImagenesSerializer
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), CanEditProducts()]

    def get_object(self):
        image = super().get_object()
        self._ensure_partial_worker_owns_product(image.producto)
        return image

    def perform_update(self, serializer):
        producto = serializer.validated_data.get("producto", serializer.instance.producto)
        self._ensure_partial_worker_owns_product(producto)
        serializer.save()

    def _ensure_partial_worker_owns_product(self, producto):
        user = self.request.user
        if self.request.method in SAFE_METHODS or getattr(user, "worker_role", "none") != "parcial":
            return
        if producto is None or producto.worker_id != user.id:
            raise PermissionDenied("No tienes permisos para modificar imágenes de este producto.")
