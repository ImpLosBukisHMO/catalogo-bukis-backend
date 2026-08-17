import io
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from api.models import (
    BannerOfertaModel,
    CategoriasModel,
    ColorModel,
    DescuentosModel,
    PedidosModel,
    ProductoVariantesModel,
    ProductosImagenesModel,
    ProductosModel,
    UsuariosModel,
)


def _gif_file(name: str = "product.gif") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        (
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


def _jpeg_file(name: str = "image.jpg", size=(16, 16)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(120, 40, 200)).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def _pdf_file(name: str = "comprobante.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n",
        content_type="application/pdf",
    )


def _create_worker(email: str, role: str, **flags) -> UsuariosModel:
    worker = UsuariosModel.objects.create_user(
        nombre="Worker",
        apellido="Permissions",
        correo=email,
        telefono="5551234567",
        password="testpass123",
        staff=True,
    )
    worker.worker_role = role
    for field, value in flags.items():
        setattr(worker, field, value)
    update_fields = ["worker_role", *flags.keys()]
    worker.save(update_fields=update_fields)
    return worker


def _create_customer(email: str = "customer@test.com") -> UsuariosModel:
    return UsuariosModel.objects.create_user(
        nombre="Customer",
        apellido="Permissions",
        correo=email,
        telefono="5557654321",
        password="testpass123",
        staff=False,
    )


def _create_category(name: str = "Category") -> CategoriasModel:
    return CategoriasModel.objects.create(nombre=name)


def _create_discount(
    name: str = "Discount",
    *,
    tipo: str = DescuentosModel.DescuentoType.ESPECIAL,
) -> DescuentosModel:
    now = timezone.now()
    return DescuentosModel.objects.create(
        nombre=name,
        tipo=tipo,
        porcentaje=Decimal("10.00"),
        activo=True,
        fecha_inicio=now - timedelta(days=1),
        fecha_fin=now + timedelta(days=1),
    )


def _create_product(worker: UsuariosModel, name: str = "Producto") -> ProductosModel:
    return ProductosModel.objects.create(
        nombre=name,
        imagen="img/products/default.jpg",
        descripcion=f"{name} desc",
        precio=Decimal("100.00"),
        peso=Decimal("1.00"),
        medidas="10x10x10",
        capacidad="1L",
        disponible=True,
        estado=ProductosModel.EstadoProducto.DRAFT,
        categoria=_create_category(f"{name} category"),
        worker=worker,
    )


def _create_color(name: str, hex_value: str) -> ColorModel:
    return ColorModel.objects.create(nombre=name, hex=hex_value)


def _create_variant(producto: ProductosModel, color: ColorModel) -> ProductoVariantesModel:
    return ProductoVariantesModel.objects.create(
        producto=producto,
        color=color,
        item="SKU-001",
        codigo_barras="7501234567890",
        precio=Decimal("120.00"),
        stock=10,
        activo=True,
    )


def _create_product_image(producto: ProductosModel, *, orden: int = 0) -> ProductosImagenesModel:
    return ProductosImagenesModel.objects.create(
        producto=producto,
        imagen=_gif_file(f"product-{producto.id}-{orden}.gif"),
        orden=orden,
        es_principal=orden == 0,
    )


def _create_banner(**overrides) -> BannerOfertaModel:
    defaults = {
        "tipo": BannerOfertaModel.MediaType.IMAGEN,
        "archivo": _jpeg_file("banner.jpg"),
        "orden": 0,
        "activo": True,
    }
    defaults.update(overrides)
    return BannerOfertaModel.objects.create(**defaults)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class WorkerEndpointPermissionsTest(TestCase):
    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.media_override.enable()
        self.client = APIClient()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def test_product_create_permissions(self):
        category = _create_category("Create category")
        url = "/api/worker/productos/"
        scenarios = [
            (None, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}, 0),
            (_create_worker("total-create@test.com", UsuariosModel.WorkerRole.TOTAL), {status.HTTP_201_CREATED}, 1),
            (
                _create_worker(
                    "partial-create-ok@test.com",
                    UsuariosModel.WorkerRole.PARCIAL,
                    can_add_products=True,
                ),
                {status.HTTP_201_CREATED},
                2,
            ),
            (
                _create_worker(
                    "partial-create-denied@test.com",
                    UsuariosModel.WorkerRole.PARCIAL,
                    can_add_products=False,
                ),
                {status.HTTP_403_FORBIDDEN},
                2,
            ),
            (_create_worker("none-create@test.com", UsuariosModel.WorkerRole.NONE), {status.HTTP_403_FORBIDDEN}, 2),
        ]

        for user, allowed_statuses, expected_count in scenarios:
            with self.subTest(user=getattr(user, "correo", "anonymous")):
                self.client.force_authenticate(user=user)
                payload = {
                    "nombre": f"Nuevo producto {expected_count}",
                    "imagen": _gif_file(),
                    "descripcion": "Created by worker",
                    "precio": "100.00",
                    "peso": "1.00",
                    "medidas": "10x10x10",
                    "capacidad": "1L",
                    "disponible": True,
                    "estado": ProductosModel.EstadoProducto.ACTIVE,
                    "categoria_id": category.id,
                }
                response = self.client.post(url, payload, format="multipart")
                self.assertIn(response.status_code, allowed_statuses, response.content)
                self.assertEqual(ProductosModel.objects.count(), expected_count)

    def test_product_patch_requires_all_mapped_capabilities_without_mutation(self):
        worker = _create_worker(
            "product-patch@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=True,
            can_edit_prices=False,
            can_apply_discounts=False,
        )
        product = _create_product(worker, "Patch Product")
        discount = _create_discount("Especial patch")
        url = f"/api/worker/productos/{product.id}/"
        self.client.force_authenticate(user=worker)

        response = self.client.patch(
            url,
            {"nombre": "Mutated name", "precio": "150.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        product.refresh_from_db()
        self.assertEqual(product.nombre, "Patch Product")
        self.assertEqual(product.precio, Decimal("100.00"))

        worker.can_edit_prices = True
        worker.save(update_fields=["can_edit_prices"])
        response = self.client.patch(
            url,
            {"nombre": "Mutated name", "precio": "150.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        product.refresh_from_db()
        self.assertEqual(product.nombre, "Mutated name")
        self.assertEqual(product.precio, Decimal("150.00"))

        response = self.client.patch(
            url,
            {"descuento_especial": discount.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        product.refresh_from_db()
        self.assertIsNone(product.descuento_especial)

    def test_variant_create_and_image_upload_require_can_edit_products(self):
        worker = _create_worker(
            "variant-create@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=False,
        )
        product = _create_product(worker, "Variant Product")
        color = _create_color("Variant Blue", "#0000FF")
        variant_url = f"/api/worker/productos/{product.id}/variantes/"
        image_url = f"/api/worker/productos/{product.id}/imagenes/"
        self.client.force_authenticate(user=worker)

        response = self.client.post(
            variant_url,
            {
                "item": "SKU-NEW",
                "color": color.id,
                "stock": 5,
                "codigo_barras": "7501234567001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ProductoVariantesModel.objects.count(), 0)

        response = self.client.post(
            image_url,
            {"imagen": _gif_file("gallery.gif"), "orden": 0, "es_principal": True},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ProductosImagenesModel.objects.count(), 0)

        worker.can_edit_products = True
        worker.save(update_fields=["can_edit_products"])
        response = self.client.post(
            variant_url,
            {
                "item": "SKU-NEW",
                "color": color.id,
                "stock": 5,
                "codigo_barras": "7501234567001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        response = self.client.post(
            image_url,
            {"imagen": _gif_file("gallery.gif"), "orden": 0, "es_principal": True},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(ProductosImagenesModel.objects.count(), 1)

    def test_public_product_image_gets_stay_open(self):
        owner = _create_worker("public-image-owner@test.com", UsuariosModel.WorkerRole.TOTAL)
        product = _create_product(owner, "Public Image Product")
        image = _create_product_image(product)

        list_response = self.client.get(reverse("productos-imagenes-list-create"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data), 1)

        detail_response = self.client.get(reverse("productos-imagenes-detail", args=[image.id]))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], image.id)

    def test_public_product_image_post_requires_authenticated_editor(self):
        owner = _create_worker("image-owner@test.com", UsuariosModel.WorkerRole.TOTAL)
        product = _create_product(owner, "Image Product")
        list_url = reverse("productos-imagenes-list-create")
        payload = {
            "producto_id": product.id,
            "imagen": _gif_file("public-post.gif"),
            "orden": 0,
            "es_principal": True,
        }

        response = self.client.post(list_url, payload, format="multipart")
        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
            response.content,
        )
        self.assertEqual(ProductosImagenesModel.objects.count(), 0)

    def test_product_image_post_permissions_follow_capability_and_product_ownership(self):
        owner = _create_worker("image-owner-2@test.com", UsuariosModel.WorkerRole.TOTAL)
        product = _create_product(owner, "Image Permission Product")
        list_url = reverse("productos-imagenes-list-create")
        denied_worker = _create_worker(
            "image-denied@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=False,
        )
        allowed_partial = _create_worker(
            "image-partial-ok@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=True,
        )
        own_product = _create_product(allowed_partial, "Owned Image Product")
        total_worker = _create_worker("image-total-ok@test.com", UsuariosModel.WorkerRole.TOTAL)

        scenarios = [
            (denied_worker, product, status.HTTP_403_FORBIDDEN, 0),
            (allowed_partial, product, status.HTTP_403_FORBIDDEN, 0),
            (allowed_partial, own_product, status.HTTP_201_CREATED, 1),
            (total_worker, product, status.HTTP_201_CREATED, 2),
        ]

        for worker, target_product, expected_status, expected_count in scenarios:
            with self.subTest(worker=worker.correo, product_id=target_product.id):
                self.client.force_authenticate(user=worker)
                response = self.client.post(
                    list_url,
                    {
                        "producto_id": target_product.id,
                        "imagen": _gif_file(f"{worker.worker_role}-{expected_count}.gif"),
                        "orden": expected_count,
                        "es_principal": expected_count == 0,
                    },
                    format="multipart",
                )
                self.assertEqual(response.status_code, expected_status, response.data)
                self.assertEqual(ProductosImagenesModel.objects.count(), expected_count)

    def test_product_image_patch_and_delete_require_can_edit_products(self):
        owner = _create_worker("image-owner-3@test.com", UsuariosModel.WorkerRole.TOTAL)
        product = _create_product(owner, "Image Mutation Product")
        image = _create_product_image(product, orden=1)
        detail_url = reverse("productos-imagenes-detail", args=[image.id])
        denied_worker = _create_worker(
            "image-mutation-denied@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=False,
        )

        self.client.force_authenticate(user=denied_worker)

        patch_response = self.client.patch(detail_url, {"orden": 9}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        image.refresh_from_db()
        self.assertEqual(image.orden, 1)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ProductosImagenesModel.objects.filter(id=image.id).exists())

    def test_partial_worker_cannot_patch_or_delete_foreign_legacy_image(self):
        owner = _create_worker("image-owner-4@test.com", UsuariosModel.WorkerRole.TOTAL)
        foreign_product = _create_product(owner, "Foreign Image Product")
        foreign_image = _create_product_image(foreign_product, orden=1)
        partial_worker = _create_worker(
            "image-partial-mutation@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=True,
        )
        own_product = _create_product(partial_worker, "Own Image Product")
        own_image = _create_product_image(own_product, orden=2)

        self.client.force_authenticate(user=partial_worker)

        foreign_detail_url = reverse("productos-imagenes-detail", args=[foreign_image.id])
        patch_response = self.client.patch(foreign_detail_url, {"orden": 9}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        foreign_image.refresh_from_db()
        self.assertEqual(foreign_image.orden, 1)

        delete_response = self.client.delete(foreign_detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ProductosImagenesModel.objects.filter(id=foreign_image.id).exists())

        own_detail_url = reverse("productos-imagenes-detail", args=[own_image.id])
        own_patch_response = self.client.patch(own_detail_url, {"orden": 7}, format="json")
        self.assertEqual(own_patch_response.status_code, status.HTTP_200_OK, own_patch_response.data)
        own_image.refresh_from_db()
        self.assertEqual(own_image.orden, 7)

        own_delete_response = self.client.delete(own_detail_url)
        self.assertEqual(own_delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductosImagenesModel.objects.filter(id=own_image.id).exists())

    def test_variant_patch_requires_edit_products_and_edit_prices_without_mutation(self):
        worker = _create_worker(
            "variant-patch@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_edit_products=True,
            can_edit_prices=False,
        )
        product = _create_product(worker, "Variant Patch Product")
        variant = _create_variant(product, _create_color("Variant Red", "#FF0000"))
        url = f"/api/worker/variants/{variant.id}/"
        self.client.force_authenticate(user=worker)

        response = self.client.patch(url, {"stock": 8}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 8)

        response = self.client.patch(url, {"precio": "180.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        variant.refresh_from_db()
        self.assertEqual(variant.precio, Decimal("120.00"))

        response = self.client.patch(
            url,
            {"stock": 6, "precio": "180.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 8)
        self.assertEqual(variant.precio, Decimal("120.00"))

        worker.can_edit_prices = True
        worker.save(update_fields=["can_edit_prices"])
        response = self.client.patch(
            url,
            {"stock": 6, "precio": "180.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 6)
        self.assertEqual(variant.precio, Decimal("180.00"))

    def test_discount_endpoints_require_manage_discount_codes_but_get_stays_open(self):
        existing = _create_discount("Existing discount")
        list_url = reverse("worker-descuentos")
        detail_url = reverse("worker-descuentos-detail", args=[existing.id])
        tipos_url = reverse("worker-descuentos-tipos")
        denied_worker = _create_worker(
            "discount-denied@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_discount_codes=False,
        )
        allowed_worker = _create_worker(
            "discount-allowed@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_discount_codes=True,
        )

        self.client.force_authenticate(user=denied_worker)
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(tipos_url).status_code, status.HTTP_200_OK)

        create_payload = {
            "nombre": "Created discount",
            "tipo": DescuentosModel.DescuentoType.GENERAL,
            "porcentaje": "12.00",
            "activo": True,
            "fecha_inicio": (timezone.now() - timedelta(days=1)).isoformat(),
            "fecha_fin": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        response = self.client.post(list_url, create_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.patch(detail_url, {"nombre": "Blocked update"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.nombre, "Existing discount")

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(DescuentosModel.objects.filter(id=existing.id).exists())

        self.client.force_authenticate(user=allowed_worker)
        response = self.client.post(list_url, create_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created_id = response.data["id"]
        created_detail_url = reverse("worker-descuentos-detail", args=[created_id])

        response = self.client.patch(created_detail_url, {"nombre": "Updated discount"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        response = self.client.delete(created_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DescuentosModel.objects.filter(id=created_id).exists())

    def test_banner_offer_endpoints_require_manage_offers_but_get_stays_open(self):
        banner = _create_banner(orden=1)
        list_url = reverse("worker-banner-ofertas")
        detail_url = reverse("worker-banner-ofertas-detail", args=[banner.id])
        denied_worker = _create_worker(
            "banner-denied@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_offers=False,
        )
        allowed_worker = _create_worker(
            "banner-allowed@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_offers=True,
        )

        self.client.force_authenticate(user=denied_worker)
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

        response = self.client.post(
            list_url,
            {"tipo": "imagen", "archivo": _jpeg_file("new-banner.jpg"), "orden": 2, "activo": True},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.patch(detail_url, {"orden": 9}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        banner.refresh_from_db()
        self.assertEqual(banner.orden, 1)

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(BannerOfertaModel.objects.filter(id=banner.id).exists())

        self.client.force_authenticate(user=allowed_worker)
        response = self.client.post(
            list_url,
            {"tipo": "imagen", "archivo": _jpeg_file("allowed-banner.jpg"), "orden": 3, "activo": True},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created_id = response.data["id"]
        created_detail_url = reverse("worker-banner-ofertas-detail", args=[created_id])

        response = self.client.patch(created_detail_url, {"orden": 7}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        response = self.client.delete(created_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BannerOfertaModel.objects.filter(id=created_id).exists())

    def test_worker_order_endpoints_remain_available_to_partial_without_flags(self):
        customer = _create_customer()
        worker = _create_worker("orders@test.com", UsuariosModel.WorkerRole.PARCIAL)
        pedido = PedidosModel.objects.create(
            cliente=customer,
            clave="PED-001",
            estado=PedidosModel.EstadoPedido.APROBADO,
            subtotal_snapshot=100,
            precio_total=120,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        pedido.comprobante_pago.save("comprobante.pdf", _pdf_file(), save=True)

        self.client.force_authenticate(user=worker)
        self.assertEqual(self.client.get(reverse("worker-pedidos")).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(reverse("worker-pedido-detail", args=[pedido.id])).status_code,
            status.HTTP_200_OK,
        )
        resp = self.client.get(reverse("worker-pedido-comprobante", args=[pedido.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp.close()

        pedido.estado = PedidosModel.EstadoPedido.PENDIENTE
        pedido.comprobante_pago.delete(save=False)
        pedido.comprobante_pago = None
        pedido.save(update_fields=["estado", "comprobante_pago", "updated_at"])

        with patch("api.views.workerViews.send_bukis_email"):
            response = self.client.patch(
                reverse("worker-cambiar-estado", args=[pedido.id]),
                {"estado": PedidosModel.EstadoPedido.APROBADO, "nota_worker": "Approved"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidosModel.EstadoPedido.APROBADO)

    def test_legacy_discount_endpoints_public_read_but_protected_mutations(self):
        """Legacy /api/descuentos/ must keep GET public (used by public catalog UI)
        while POST/PUT/PATCH/DELETE require `IsAuthenticated + CanManageDiscountCodes`.

        This closes a pre-existing bypass where the legacy endpoints inherited
        DRF's `AllowAny` default and allowed unauthenticated discount mutations,
        even after `/api/worker/descuentos/` was gated. See PR #68 review.
        """
        existing = _create_discount("Legacy existing discount")
        list_url = reverse("descuentos-list-create")
        detail_url = reverse("descuentos-detail", args=[existing.id])

        create_payload = {
            "nombre": "Legacy created discount",
            "tipo": DescuentosModel.DescuentoType.GENERAL,
            "porcentaje": "15.00",
            "activo": True,
            "fecha_inicio": (timezone.now() - timedelta(days=1)).isoformat(),
            "fecha_fin": (timezone.now() + timedelta(days=1)).isoformat(),
        }

        # Anonymous reads stay public (public catalog UI depends on this).
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

        # Anonymous mutations must be rejected AND must not mutate.
        pre_count = DescuentosModel.objects.count()
        response = self.client.post(list_url, create_payload, format="json")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertEqual(DescuentosModel.objects.count(), pre_count)

        response = self.client.patch(detail_url, {"nombre": "Blocked anon patch"}, format="json")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        existing.refresh_from_db()
        self.assertEqual(existing.nombre, "Legacy existing discount")

        response = self.client.delete(detail_url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertTrue(DescuentosModel.objects.filter(id=existing.id).exists())

        # Partial worker without the flag is rejected AND must not mutate.
        denied_worker = _create_worker(
            "legacy-discount-denied@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_discount_codes=False,
        )
        self.client.force_authenticate(user=denied_worker)

        response = self.client.post(list_url, create_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(DescuentosModel.objects.count(), pre_count)

        response = self.client.put(
            detail_url,
            {
                **create_payload,
                "nombre": "Blocked partial put",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.nombre, "Legacy existing discount")

        response = self.client.patch(detail_url, {"nombre": "Blocked partial patch"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        existing.refresh_from_db()
        self.assertEqual(existing.nombre, "Legacy existing discount")

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(DescuentosModel.objects.filter(id=existing.id).exists())

        # Partial worker with the flag can mutate.
        allowed_worker = _create_worker(
            "legacy-discount-allowed@test.com",
            UsuariosModel.WorkerRole.PARCIAL,
            can_manage_discount_codes=True,
        )
        self.client.force_authenticate(user=allowed_worker)

        response = self.client.post(list_url, create_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created_id = response.data["datos"]["id"]
        created_detail_url = reverse("descuentos-detail", args=[created_id])

        response = self.client.patch(created_detail_url, {"nombre": "Updated legacy discount"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            DescuentosModel.objects.get(id=created_id).nombre,
            "Updated legacy discount",
        )

        response = self.client.put(
            created_detail_url,
            {
                **create_payload,
                "nombre": "Put updated legacy discount",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            DescuentosModel.objects.get(id=created_id).nombre,
            "Put updated legacy discount",
        )

        response = self.client.delete(created_detail_url)
        # RetrieveUpdateDestroy delete override returns 200 with a message, keep parity.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(DescuentosModel.objects.filter(id=created_id).exists())
