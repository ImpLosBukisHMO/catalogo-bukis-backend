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


def _url(img_field) -> str | None:
    if not img_field:
        return None
    return img_field.url if hasattr(img_field, "url") else (str(img_field) or None)


def get_variante_imagen(variante: "ProductoVariantesModel") -> str | None:
    """Return the display image URL for *variante* using the canonical fallback chain."""

    # Step 1: variant principal image.
    if hasattr(variante, "_cached_variante_imagenes"):
        # Prefetched + pre-ordered by (orden, id); filter es_principal in Python.
        img = next(
            (i for i in variante._cached_variante_imagenes if i.es_principal),
            None,
        )
    else:
        img = variante.imagenes.filter(es_principal=True).order_by("orden", "id").first()
    if img:
        return _url(img.imagen)

    # Step 2: any variant image.
    if hasattr(variante, "_cached_variante_imagenes"):
        img = variante._cached_variante_imagenes[0] if variante._cached_variante_imagenes else None
    else:
        img = variante.imagenes.order_by("orden", "id").first()
    if img:
        return _url(img.imagen)

    # Step 3: product principal image (not tied to a specific variant).
    producto = variante.producto
    if hasattr(producto, "_cached_prod_imagenes"):
        # Prefetched + pre-ordered by (orden, id); filter es_principal in Python.
        img = next(
            (i for i in producto._cached_prod_imagenes if i.es_principal),
            None,
        )
    else:
        img = (
            producto.imagenes.filter(variante__isnull=True, es_principal=True)
            .order_by("orden", "id")
            .first()
        )
    if img:
        return _url(img.imagen)

    # Step 4: product.imagen fallback field.
    return _url(producto.imagen)


def get_producto_imagen(producto: "ProductosModel") -> str | None:
    """Return the public display image for *producto* while preserving legacy compatibility."""

    legacy_image = _url(producto.imagen)
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
        imagen = get_variante_imagen(variante)
        if imagen:
            return imagen

    if hasattr(producto, "_cached_prod_imagenes"):
        principal = next(
            (img for img in producto._cached_prod_imagenes if img.es_principal),
            None,
        )
        fallback = producto._cached_prod_imagenes[0] if producto._cached_prod_imagenes else None
    else:
        principal = (
            producto.imagenes.filter(variante__isnull=True, es_principal=True)
            .order_by("orden", "id")
            .first()
        )
        fallback = (
            producto.imagenes.filter(variante__isnull=True)
            .order_by("orden", "id")
            .first()
        )

    if principal:
        return _url(principal.imagen)
    if fallback:
        return _url(fallback.imagen)

    return None
