# Aquí van todos los serializers del worker
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from api.models import DescuentosModel
from api.models import (
    ProductosModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    ColorModel,
    PedidosModel,
    BannerOfertaModel,
)
from api.utils.imagenes import get_variante_imagen


# =========================
# WORKER - BANNER DE OFERTAS
# =========================
class WorkerBannerOfertaSerializer(serializers.ModelSerializer):
    MAX_VIDEO_BYTES = 20 * 1024 * 1024  # 20 MB
    MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB
    MAX_ACTIVE_SLIDES = 10
    ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_VIDEO_EXTS = {"mp4", "webm"}
    # Pillow → nuestro tipo. Cualquier otro formato válido para Pillow se rechaza.
    PILLOW_FORMAT_TO_EXT = {
        "JPEG": {"jpg", "jpeg"},
        "PNG": {"png"},
        "WEBP": {"webp"},
    }

    # Default explícito para no depender del comportamiento de DRF con multipart,
    # que interpreta un BooleanField ausente como False en vez de usar el default del modelo.
    activo = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = BannerOfertaModel
        fields = [
            "id",
            "tipo",
            "archivo",
            "orden",
            "activo",
            "fecha_inicio",
            "fecha_fin",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    # -------------------------
    # Helpers de contenido real
    # -------------------------
    @staticmethod
    def _peek_bytes(archivo, n: int) -> bytes:
        """Lee `n` bytes del archivo sin consumir la posición para lecturas posteriores."""
        data = b""
        try:
            try:
                archivo.seek(0)
            except Exception:
                # Si no es seekable no podemos hacer un peek confiable.
                return b""
            data = archivo.read(n) or b""
        finally:
            try:
                archivo.seek(0)
            except Exception:
                pass
        return data

    def _validate_image_content(self, archivo, ext: str) -> None:
        """
        Confirma que `archivo` es realmente una imagen y su formato coincide con la extensión.
        Pillow lanza DecompressionBombError si el tamaño descomprimido supera su umbral por defecto
        (~89 megapíxeles), lo que nos cubre contra imágenes-bomba chicas en bytes pero enormes en RAM.
        """
        try:
            archivo.seek(0)
            with Image.open(archivo) as img:
                img.verify()  # valida integridad; también dispara DecompressionBombError
                detected = (img.format or "").upper()
        except UnidentifiedImageError:
            raise serializers.ValidationError(
                {"archivo": "El archivo no es una imagen válida."}
            )
        except Image.DecompressionBombError:
            raise serializers.ValidationError(
                {"archivo": "La imagen es demasiado grande para procesarse."}
            )
        except Exception:
            raise serializers.ValidationError(
                {"archivo": "El archivo no es una imagen válida."}
            )
        finally:
            try:
                archivo.seek(0)
            except Exception:
                pass

        allowed_exts_for_format = self.PILLOW_FORMAT_TO_EXT.get(detected)
        if not allowed_exts_for_format or ext not in allowed_exts_for_format:
            raise serializers.ValidationError(
                {"archivo": "El contenido del archivo no coincide con su extensión."}
            )

    def _validate_video_content(self, archivo, ext: str) -> None:
        """
        Valida magic numbers de contenedores mp4/webm.
        - mp4: bytes 4..8 = 'ftyp' (ISO Base Media File Format)
        - webm: bytes 0..4 = 0x1A45DFA3 (EBML header, compartido con mkv)
        """
        head = self._peek_bytes(archivo, 32)
        if len(head) < 12:
            raise serializers.ValidationError(
                {"archivo": "El archivo de video está incompleto o vacío."}
            )
        is_mp4 = head[4:8] == b"ftyp"
        is_webm = head[0:4] == b"\x1a\x45\xdf\xa3"

        if ext == "mp4" and not is_mp4:
            raise serializers.ValidationError(
                {"archivo": "El contenido no es un mp4 válido."}
            )
        if ext == "webm" and not is_webm:
            raise serializers.ValidationError(
                {"archivo": "El contenido no es un webm válido."}
            )

    # -------------------------
    # Validaciones
    # -------------------------
    def validate(self, attrs):
        # Fechas: aplicar sobre el estado efectivo (instance + attrs)
        fi = attrs.get("fecha_inicio", getattr(self.instance, "fecha_inicio", None))
        ff = attrs.get("fecha_fin", getattr(self.instance, "fecha_fin", None))
        if fi and ff and fi > ff:
            raise serializers.ValidationError(
                {"fecha_fin": "Debe ser posterior a la fecha de inicio."}
            )

        # Estado efectivo de tipo y archivo (tras aplicar el payload)
        tipo_efectivo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        archivo_nuevo = attrs.get("archivo", None)
        cambio_tipo = "tipo" in attrs and self.instance is not None and attrs["tipo"] != self.instance.tipo

        # Regla: si cambia el tipo en un update, debe re-subirse un archivo compatible.
        if cambio_tipo and archivo_nuevo is None:
            raise serializers.ValidationError(
                {"archivo": "Debes re-subir el archivo cuando cambies el tipo del banner."}
            )

        # Validación del archivo (solo cuando venga uno nuevo)
        if archivo_nuevo is not None:
            if tipo_efectivo is None:
                raise serializers.ValidationError(
                    {"tipo": "Debes indicar si el archivo es imagen o video."}
                )

            size = getattr(archivo_nuevo, "size", 0) or 0
            if tipo_efectivo == BannerOfertaModel.MediaType.VIDEO and size > self.MAX_VIDEO_BYTES:
                raise serializers.ValidationError(
                    {"archivo": "El video no puede superar 20 MB."}
                )
            if tipo_efectivo == BannerOfertaModel.MediaType.IMAGEN and size > self.MAX_IMAGE_BYTES:
                raise serializers.ValidationError(
                    {"archivo": "La imagen no puede superar 5 MB."}
                )

            name = getattr(archivo_nuevo, "name", "") or ""
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

            if tipo_efectivo == BannerOfertaModel.MediaType.VIDEO:
                if ext not in self.ALLOWED_VIDEO_EXTS:
                    raise serializers.ValidationError(
                        {"archivo": "Formato de video inválido. Usa mp4 o webm."}
                    )
                self._validate_video_content(archivo_nuevo, ext)
            elif tipo_efectivo == BannerOfertaModel.MediaType.IMAGEN:
                if ext not in self.ALLOWED_IMAGE_EXTS:
                    raise serializers.ValidationError(
                        {"archivo": "Formato de imagen inválido. Usa jpg, png o webp."}
                    )
                self._validate_image_content(archivo_nuevo, ext)

        return attrs

    # -------------------------
    # Enforcement transaccional del límite de 10 activos
    # -------------------------
    def _assert_max_active_slides(self, activo_efectivo: bool) -> None:
        """
        Debe llamarse dentro de una transacción. Fuerza la evaluación del queryset
        con `list(...)` para que las filas queden bloqueadas por `select_for_update`.
        Nota: `.count()` no dispara el lock porque Django limpia la flag select_for_update
        en agregaciones (ver Query.get_aggregation en Django 6).
        En SQLite `select_for_update` es no-op — el lock efectivo se toma solo en Postgres.
        """
        if not activo_efectivo:
            return
        qs = BannerOfertaModel.objects.select_for_update().filter(activo=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        # Materializar para que el lock se aplique realmente, y contar sobre la lista.
        active_ids = list(qs.values_list("id", flat=True))
        if len(active_ids) >= self.MAX_ACTIVE_SLIDES:
            raise serializers.ValidationError(
                {"activo": "No puedes tener más de 10 banners activos a la vez."}
            )

    def create(self, validated_data):
        activo_efectivo = validated_data.get("activo", True)
        with transaction.atomic():
            self._assert_max_active_slides(activo_efectivo)
            return super().create(validated_data)

    def update(self, instance, validated_data):
        activo_efectivo = validated_data.get("activo", instance.activo)
        with transaction.atomic():
            self.instance = instance  # asegura exclude(pk) correcto
            self._assert_max_active_slides(activo_efectivo)
            return super().update(instance, validated_data)

# para productos
class WorkerVariantSerializer(serializers.ModelSerializer):
    variant_id = serializers.IntegerField(source="id")
    producto = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    imagen_principal = serializers.SerializerMethodField()

    class Meta:
        model = ProductoVariantesModel
        fields = [
            "variant_id",
            "item",
            "codigo_barras",
            "producto",
            "color",
            "stock",
            "activo",
            "imagen_principal",
        ]

    # -------------------------
    # Producto
    # -------------------------
    def get_producto(self, obj):
        p = obj.producto
        cat_data = None
        if p.categoria:
            desc_cat_data = None
            if p.categoria.descuento_general:
                desc = p.categoria.descuento_general
                desc_cat_data = {
                    "id": desc.id,
                    "nombre": desc.nombre,
                    "porcentaje": float(desc.porcentaje),
                    "es_valido": desc.es_valido,
                }
            cat_data = {
                "id": p.categoria.id,
                "nombre": p.categoria.nombre,
                "descuento": desc_cat_data
            }

        desc_prod_data = None
        if p.descuento_especial:
            desc = p.descuento_especial
            desc_prod_data = {
                "id": desc.id,
                "nombre": desc.nombre,
                "porcentaje": float(desc.porcentaje),
                "es_valido": desc.es_valido,
            }

        return {
            "id": p.id,
            "nombre": p.nombre,
            "precio_original": str(obj.precio if obj.precio is not None else p.precio),
            "precio": str(obj.precio_efectivo),
            "categoria": cat_data,
            "descuento_especial": desc_prod_data,
        }

    # -------------------------
    # Color
    # -------------------------
    def get_color(self, obj):
        c = obj.color
        return {
            "id": c.id,
            "nombre": c.nombre,
            "hex": c.hex,
        }

    # -------------------------
    # Imagen principal
    # -------------------------
    def get_imagen_principal(self, obj):
        return get_variante_imagen(obj)


# para pedidos
class WorkerPedidoSerializer(serializers.ModelSerializer):
    cliente = serializers.SerializerMethodField()
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "folio",
            "cliente",
            "estado",
            "precio_total",
            "items_count",
            "created_at",
        ]

    def get_cliente(self, obj):
        return {
            "id": obj.cliente.id,
            "nombre": f"{obj.cliente.nombre} {obj.cliente.apellido}",
            "correo": obj.cliente.correo,
        }


# =========================
# WORKER - DETALLE DE PEDIDO (con items)
# =========================
class WorkerPedidoItemSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField()
    nombre = serializers.CharField(source="producto_nombre_snapshot")
    item = serializers.CharField(source="producto_item_snapshot")
    color = serializers.CharField(source="color_nombre_snapshot")
    color_hex = serializers.CharField(source="color_hex_snapshot")
    precio_unitario = serializers.DecimalField(source="precio_unitario_snapshot", max_digits=10, decimal_places=2)
    descuento_porcentaje = serializers.DecimalField(source="descuento_porcentaje_snapshot", max_digits=5, decimal_places=2)
    subtotal = serializers.DecimalField(source="subtotal_linea_snapshot", max_digits=10, decimal_places=2)
    imagen = serializers.CharField(source="imagen_principal_snapshot")


class WorkerPedidoDetalleSerializer(serializers.ModelSerializer):
    cliente = serializers.SerializerMethodField()
    items = WorkerPedidoItemSerializer(many=True, read_only=True)

    class Meta:
        model = PedidosModel
        fields = [
            "id",
            "public_id",
            "folio",
            "cliente",
            "estado",
            "precio_total",
            "subtotal_snapshot",
            "nota_cliente",
            "nota_worker",
            "denegado_razon",
            "aprobado_eta",
            "items",
            "created_at",
        ]

    def get_cliente(self, obj):
        return {
            "id": obj.cliente.id,
            "nombre": f"{obj.cliente.nombre} {obj.cliente.apellido}",
            "correo": obj.cliente.correo,
            "telefono": obj.cliente.telefono,
        }


# =========================
# WORKER - CAMBIAR ESTADO PEDIDO
# =========================
class WorkerCambiarEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=PedidosModel.EstadoPedido.choices)
    nota_worker = serializers.CharField(required=False, allow_blank=True)
    denegado_razon = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        pedido = self.context["pedido"]
        estado_actual = pedido.estado
        estado_nuevo = data["estado"]

        transiciones = PedidosModel.TRANSICIONES_VALIDAS.get(estado_actual, [])

        if estado_nuevo == estado_actual:
            raise serializers.ValidationError(
                f"El pedido ya se encuentra en estado '{estado_actual}'."
            )
        if estado_nuevo not in transiciones:
            raise serializers.ValidationError(
                f"Transición inválida: '{estado_actual}' → '{estado_nuevo}'. "
                f"Transiciones permitidas: {transiciones or 'ninguna'}."
            )
        if estado_nuevo in {
            PedidosModel.EstadoPedido.DENEGADO,
            PedidosModel.EstadoPedido.CANCELADO,
        } and not data.get("denegado_razon"):
            raise serializers.ValidationError(
                "Se requiere 'denegado_razon' para denegar o cancelar un pedido."
            )
        return data


# =========================
# WORKER - PRODUCTOS PROPIOS
# =========================
class WorkerDescuentosSerializer(serializers.ModelSerializer):
    es_valido = serializers.ReadOnlyField()

    class Meta:
        model = DescuentosModel
        fields = "__all__"

class WorkerProductoSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(read_only=True)
    categoria_id = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=__import__("api.models", fromlist=["CategoriasModel"]).CategoriasModel.objects.all(),
        source="categoria",
        required=False,
        allow_null=True,
    )
    descuento_especial = serializers.PrimaryKeyRelatedField(
        queryset=__import__("api.models", fromlist=["DescuentosModel"]).DescuentosModel.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProductosModel
        fields = [
            "id",
            "nombre",
            "imagen",
            "descripcion",
            "precio",
            "peso",
            "medidas",
            "capacidad",
            "disponible",
            "estado",
            "categoria",
            "categoria_id",
            "descuento_especial",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_estado(self, value):
        if self.instance is None:
            return ProductosModel.EstadoProducto.DRAFT
        return value


    def validate(self, attrs):
        instance = self.instance

        # Solo validar publicación si el usuario está EXPLÍCITAMENTE cambiando
        # el estado a ACTIVE en este request. Si ya está activo pero el PATCH
        # no incluye 'estado', no re-validar (evita 400 al editar campos normales).
        if "estado" not in attrs:
            return attrs

        target_estado = attrs["estado"]
        if target_estado != ProductosModel.EstadoProducto.ACTIVE:
            return attrs

        producto = instance or ProductosModel(
            worker=self.context.get("request").user if self.context.get("request") else None,
            nombre=attrs.get("nombre", ""),
            imagen=attrs.get("imagen") or "img/products/default.jpg",
            descripcion=attrs.get("descripcion", ""),
            precio=attrs.get("precio", 0),
            peso=attrs.get("peso", 0),
            medidas=attrs.get("medidas", ""),
            capacidad=attrs.get("capacidad"),
            disponible=attrs.get("disponible", True),
            estado=target_estado,
            categoria=attrs.get("categoria"),
        )

        if instance is not None:
            for field, value in attrs.items():
                setattr(producto, field, value)

        errors = producto.get_publish_validation_errors()

        if errors:
            raise serializers.ValidationError(errors)

        return attrs



# =========================
# WORKER - VARIANTE (crear para producto propio)
# =========================
class WorkerVarianteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "item", "color", "stock", "activo", "codigo_barras"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "item": {"allow_blank": True, "default": ""},
            "codigo_barras": {
                "allow_blank": False,
                "required": True,
                "trim_whitespace": True,
                "error_messages": {
                    "blank": "El código de barras es obligatorio para nuevas variantes.",
                    "required": "El código de barras es obligatorio para nuevas variantes.",
                },
            },
        }

    def validate_color(self, value):
        producto = self.context["producto"]
        if ProductoVariantesModel.objects.filter(producto=producto, color=value).exists():
            raise serializers.ValidationError(
                "Ya existe una variante con ese color para este producto."
            )
        return value

    def validate_item(self, value):
        """
        Reject duplicate non-empty item values within the same product.
        Empty string is allowed and may repeat (no constraint on item='').
        Excludes the current instance when updating (pk-based exclusion).
        """
        if not value:
            return value

        producto = self.context["producto"]
        instance = self.instance

        qs = ProductoVariantesModel.objects.filter(producto=producto, item=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "Este SKU ya está en uso para este producto."
            )
        return value

    def validate_codigo_barras(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "El código de barras es obligatorio para nuevas variantes."
            )
        return value


# =========================
# WORKER - IMAGEN (subir para producto propio)
# =========================
class WorkerImagenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductosImagenesModel
        fields = ["id", "variante", "imagen", "orden", "es_principal"]
        read_only_fields = ["id"]


# =========================
# WORKER - VARIANTE (editar: stock, item, precio, activo, codigo_barras)
# =========================
class WorkerVarianteUpdateSerializer(serializers.ModelSerializer):
    """Serializer para PATCH de una variante existente del worker.
    Solo permite actualizar campos de negocio; color y producto son inmutables.
    """
    class Meta:
        model = ProductoVariantesModel
        fields = ["id", "item", "stock", "activo", "precio", "codigo_barras"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "item": {"allow_blank": True},
            "codigo_barras": {"allow_blank": True},
            "stock": {"required": False},
            "activo": {"required": False},
            "precio": {"required": False, "allow_null": True},
        }
    
    def validate_item(self, value):
        if not value or value.strip() == "": return value
        instance = self.instance

        if instance:
            product = instance.producto
            is_duplicated = ProductoVariantesModel.objects.filter(producto=product, item=value).exclude(pk=instance.pk).exists()
            
            if is_duplicated:
                raise serializers.ValidationError("There\'s already a variant with the same item/SKU code.")
            
        return value
