"""
Image resolution helpers for product/variant displays.

Single canonical fallback chain for variants (do NOT replicate this logic inline):

  1. Variant principal image (es_principal=True, ordered by orden/id)
  2. Variant any image (first image associated to the variant)
  3. Product principal image (image row with variante=None and es_principal=True)
  4. producto.imagen (the product's legacy single-image field)

Product displays reuse the same gallery logic by delegating to an active variant
when the legacy producto.imagen field is missing.

Returns a URL string, or None if no image is available anywhere.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models import ProductosModel
    from api.models import ProductoVariantesModel


def _get_exists_cache(owner) -> dict[tuple[int, str], bool]:
    cache = getattr(owner, "_cached_image_exists", None)
    if cache is None:
        cache = {}
        setattr(owner, "_cached_image_exists", cache)
    return cache


def _file_exists(img_field, *, exists_cache: dict[tuple[int, str], bool] | None = None) -> bool:
    if not img_field:
        return False

    name = getattr(img_field, "name", None) or str(img_field) or None
    storage = getattr(img_field, "storage", None)
    if not name or storage is None:
        return False

    cache_key = (id(storage), name)
    if exists_cache is not None and cache_key in exists_cache:
        return exists_cache[cache_key]

    exists = storage.exists(name)
    if exists_cache is not None:
        exists_cache[cache_key] = exists
    return exists


def _url(img_field, *, exists_cache: dict[tuple[int, str], bool] | None = None) -> str | None:
    if not _file_exists(img_field, exists_cache=exists_cache):
        return None
    return img_field.url if hasattr(img_field, "url") else (str(img_field) or None)


def _first_existing_image(
    image_rows,
    *,
    principal_only: bool = False,
    exists_cache: dict[tuple[int, str], bool] | None = None,
):
    for image in image_rows:
        if principal_only and not image.es_principal:
            continue
        if _file_exists(image.imagen, exists_cache=exists_cache):
            return image
    return None


def get_existing_product_images(
    image_rows,
    *,
    exists_cache: dict[tuple[int, str], bool] | None = None,
):
    return [image for image in image_rows if _file_exists(image.imagen, exists_cache=exists_cache)]


def get_variante_imagen(
    variante: "ProductoVariantesModel", exists_cache: dict[tuple[int, str], bool] | None = None
) -> str | None:
    """Return the display image URL for *variante* using the canonical fallback chain."""

    producto = variante.producto
    exists_cache = exists_cache or _get_exists_cache(producto)

    # Step 1: variant principal image.
    if hasattr(variante, "_cached_variante_imagenes"):
        variante_imagenes = variante._cached_variante_imagenes
    else:
        variante_imagenes = list(variante.imagenes.order_by("orden", "id"))

    img = _first_existing_image(
        variante_imagenes,
        principal_only=True,
        exists_cache=exists_cache,
    )
    if img:
        return _url(img.imagen, exists_cache=exists_cache)

    # Step 2: any variant image.
    img = _first_existing_image(variante_imagenes, exists_cache=exists_cache)
    if img:
        return _url(img.imagen, exists_cache=exists_cache)

    # Step 3: product principal image (not tied to a specific variant).
    if hasattr(producto, "_cached_prod_imagenes"):
        producto_imagenes = producto._cached_prod_imagenes
    else:
        producto_imagenes = list(
            producto.imagenes.filter(variante__isnull=True).order_by("orden", "id")
        )

    img = _first_existing_image(
        producto_imagenes,
        principal_only=True,
        exists_cache=exists_cache,
    )
    if img:
        return _url(img.imagen, exists_cache=exists_cache)

    # Step 4: product.imagen fallback field.
    return _url(producto.imagen, exists_cache=exists_cache)


def get_producto_imagen(producto: "ProductosModel") -> str | None:
    """Return the public display image for *producto* while preserving legacy compatibility."""

    exists_cache = _get_exists_cache(producto)

    legacy_image = _url(producto.imagen, exists_cache=exists_cache)
    if legacy_image:
        return legacy_image

    variantes = getattr(producto, "_cached_display_variantes", None)
    if variantes is None:
        variantes = (
            producto.producto_colores.filter(activo=True)
            .select_related("producto")
            .order_by("color__nombre", "id")
        )

    for variante in variantes:
        imagen = get_variante_imagen(variante, exists_cache=exists_cache)
        if imagen:
            return imagen

    if hasattr(producto, "_cached_prod_imagenes"):
        producto_imagenes = producto._cached_prod_imagenes
    else:
        producto_imagenes = list(
            producto.imagenes.filter(variante__isnull=True).order_by("orden", "id")
        )

    principal = _first_existing_image(
        producto_imagenes,
        principal_only=True,
        exists_cache=exists_cache,
    )
    fallback = _first_existing_image(producto_imagenes, exists_cache=exists_cache)

    if principal:
        return _url(principal.imagen, exists_cache=exists_cache)
    if fallback:
        return _url(fallback.imagen, exists_cache=exists_cache)

    return None
