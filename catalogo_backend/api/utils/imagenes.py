"""
Image resolution helper for product variants.

Single canonical fallback chain (do NOT replicate this logic inline):

  1. Variant principal image (es_principal=True, ordered by orden/id)
  2. Variant any image (first image associated to the variant)
  3. Product principal image (image row with variante=None and es_principal=True)
  4. producto.imagen (the product's legacy single-image field)

Returns a URL string, or None if no image is available anywhere.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models import ProductoVariantesModel


def get_variante_imagen(variante: "ProductoVariantesModel") -> str | None:
    """Return the display image URL for *variante* using the canonical fallback chain."""

    def _url(img_field) -> str | None:
        if not img_field:
            return None
        return img_field.url if hasattr(img_field, "url") else (str(img_field) or None)

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
