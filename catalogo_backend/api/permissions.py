from rest_framework.permissions import BasePermission


PRODUCT_FIELD_CAPABILITY = {
    "nombre": "can_edit_products",
    "imagen": "can_edit_products",
    "descripcion": "can_edit_products",
    "peso": "can_edit_products",
    "medidas": "can_edit_products",
    "capacidad": "can_edit_products",
    "disponible": "can_edit_products",
    "estado": "can_edit_products",
    "categoria_id": "can_edit_products",
    "precio": "can_edit_prices",
    "descuento_especial": "can_apply_discounts",
}


VARIANT_FIELD_CAPABILITY = {
    "item": "can_edit_products",
    "stock": "can_edit_products",
    "activo": "can_edit_products",
    "codigo_barras": "can_edit_products",
    "precio": "can_edit_prices",
}


class IsWorker(BasePermission):
    """
    Grants access when the authenticated user has worker_role in ('total', 'parcial').
    Replaces the previous is_staff check (Spec R12).
    Behaviour-equivalent post-migration: every former is_staff=True user was
    back-filled to worker_role='total'.
    """

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        return getattr(u, "worker_role", "none") in ("total", "parcial")


class IsWorkerTotal(BasePermission):
    """
    Grants access only when worker_role == 'total' (Spec R13).
    Used for admin-level worker operations.
    """

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        return getattr(u, "worker_role", "none") == "total"


class WorkerCapabilityPermission(BasePermission):
    """
    Base class for granular capability permissions (Design D3).
    Subclasses set `capability` to the corresponding BooleanField name on UsuariosModel.

    Grant logic (Spec R14–R19):
    - total → always granted (unconditional)
    - parcial → granted only when the specific capability flag is True
    - none/unauthenticated → denied
    """

    capability = None  # Subclasses MUST override this

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        role = getattr(u, "worker_role", "none")
        if role == "total":
            return True
        if role == "parcial":
            return bool(getattr(u, self.capability, False))
        return False


class _FieldPermissionBase(BasePermission):
    field_map = {}

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False

        role = getattr(u, "worker_role", "none")
        if role == "none":
            return False
        if role == "total":
            return True

        if role != "parcial":
            return False

        for field in (request.data or {}).keys():
            capability = self.field_map.get(field)
            if capability is None:
                continue
            if not getattr(u, capability, False):
                return False
        return True


class ProductFieldPermission(_FieldPermissionBase):
    field_map = PRODUCT_FIELD_CAPABILITY


class VariantFieldPermission(_FieldPermissionBase):
    field_map = VARIANT_FIELD_CAPABILITY


class CanAddProducts(WorkerCapabilityPermission):
    """R14: total OR (parcial AND can_add_products)."""
    capability = "can_add_products"


class CanEditProducts(WorkerCapabilityPermission):
    """R15: total OR (parcial AND can_edit_products)."""
    capability = "can_edit_products"


class CanEditPrices(WorkerCapabilityPermission):
    """R16: total OR (parcial AND can_edit_prices)."""
    capability = "can_edit_prices"


class CanManageDiscountCodes(WorkerCapabilityPermission):
    """R17: total OR (parcial AND can_manage_discount_codes)."""
    capability = "can_manage_discount_codes"


class CanApplyDiscounts(WorkerCapabilityPermission):
    """R18: total OR (parcial AND can_apply_discounts)."""
    capability = "can_apply_discounts"


class CanManageOffers(WorkerCapabilityPermission):
    """R19: total OR (parcial AND can_manage_offers)."""
    capability = "can_manage_offers"
