"""
Tests: 8 permission classes across role × flag × auth matrix.
Spec source: #2898 (R12–R21)
Design source: #2906 (D3)

Coverage:
- IsWorker: total, parcial, none, unauthenticated
- IsWorkerTotal: total, parcial
- WorkerCapabilityPermission subclasses (6): total (flag=False), parcial+flag=True,
  parcial+flag=False, none
"""

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from api.permissions import (
    CanAddProducts,
    CanApplyDiscounts,
    CanEditPrices,
    CanEditProducts,
    CanManageDiscountCodes,
    CanManageOffers,
    IsWorker,
    IsWorkerTotal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

factory = APIRequestFactory()


class _FakeUser:
    """
    Minimal stub user for permission unit tests.
    AbstractUser.is_authenticated is a read-only property, so we cannot
    set it on an unsaved model instance. Using a plain stub avoids that
    constraint while still exposing the exact attributes that the
    permission classes read (worker_role, capability flags, is_authenticated).
    """

    is_authenticated = True

    def __init__(self, role: str = "none", **flags):
        self.worker_role = role
        # Default all six flags to False, then apply overrides.
        self.can_add_products = False
        self.can_edit_products = False
        self.can_edit_prices = False
        self.can_manage_discount_codes = False
        self.can_apply_discounts = False
        self.can_manage_offers = False
        for attr, val in flags.items():
            setattr(self, attr, val)


def _fake_user(role: str = "none", **flags) -> _FakeUser:
    """Return a stub authenticated user with the given role + capability flags."""
    return _FakeUser(role=role, **flags)


def _anon_user():
    """Simulate anonymous (unauthenticated) user."""
    class AnonUser:
        is_authenticated = False
    return AnonUser()


def _request_with_user(user):
    req = factory.get("/")
    req.user = user
    return req


# ---------------------------------------------------------------------------
# IsWorker (R12)
# ---------------------------------------------------------------------------

class TestIsWorker(TestCase):
    """R12: IsWorker returns True when worker_role in ('total', 'parcial')."""

    def test_is_worker_allows_total(self):
        req = _request_with_user(_fake_user(role="total"))
        self.assertTrue(IsWorker().has_permission(req, view=None))

    def test_is_worker_allows_parcial(self):
        req = _request_with_user(_fake_user(role="parcial"))
        self.assertTrue(IsWorker().has_permission(req, view=None))

    def test_is_worker_rejects_none(self):
        req = _request_with_user(_fake_user(role="none"))
        self.assertFalse(IsWorker().has_permission(req, view=None))

    def test_is_worker_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(IsWorker().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# IsWorkerTotal (R13)
# ---------------------------------------------------------------------------

class TestIsWorkerTotal(TestCase):
    """R13: IsWorkerTotal returns True only for worker_role == 'total'."""

    def test_is_worker_total_allows_total(self):
        req = _request_with_user(_fake_user(role="total"))
        self.assertTrue(IsWorkerTotal().has_permission(req, view=None))

    def test_is_worker_total_rejects_parcial(self):
        req = _request_with_user(_fake_user(role="parcial"))
        self.assertFalse(IsWorkerTotal().has_permission(req, view=None))

    def test_is_worker_total_rejects_none(self):
        req = _request_with_user(_fake_user(role="none"))
        self.assertFalse(IsWorkerTotal().has_permission(req, view=None))

    def test_is_worker_total_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(IsWorkerTotal().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# Capability permission matrix helper
# ---------------------------------------------------------------------------

def _run_capability_matrix(test_case: TestCase, perm_class, flag_name: str):
    """
    Parametrised matrix for each capability permission class:
    - total + flag=False → True  (R14–R19: total is unconditional)
    - parcial + flag=True → True
    - parcial + flag=False → False
    - none → False  (R20)
    - unauthenticated → False  (R21)
    """
    # total regardless of flag
    req = _request_with_user(_fake_user(role="total", **{flag_name: False}))
    test_case.assertTrue(
        perm_class().has_permission(req, view=None),
        f"{perm_class.__name__}: total+{flag_name}=False should be True",
    )

    # parcial with flag=True
    req = _request_with_user(_fake_user(role="parcial", **{flag_name: True}))
    test_case.assertTrue(
        perm_class().has_permission(req, view=None),
        f"{perm_class.__name__}: parcial+{flag_name}=True should be True",
    )

    # parcial with flag=False
    req = _request_with_user(_fake_user(role="parcial", **{flag_name: False}))
    test_case.assertFalse(
        perm_class().has_permission(req, view=None),
        f"{perm_class.__name__}: parcial+{flag_name}=False should be False",
    )

    # none role
    req = _request_with_user(_fake_user(role="none", **{flag_name: True}))
    test_case.assertFalse(
        perm_class().has_permission(req, view=None),
        f"{perm_class.__name__}: none+{flag_name}=True should be False (R20)",
    )

    # unauthenticated
    req = _request_with_user(_anon_user())
    test_case.assertFalse(
        perm_class().has_permission(req, view=None),
        f"{perm_class.__name__}: unauthenticated should be False (R21)",
    )


# ---------------------------------------------------------------------------
# CanAddProducts (R14)
# ---------------------------------------------------------------------------

class TestCanAddProducts(TestCase):
    """R14: total OR (parcial AND can_add_products)."""

    def test_can_add_products_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_add_products=False))
        self.assertTrue(CanAddProducts().has_permission(req, view=None))

    def test_can_add_products_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_add_products=True))
        self.assertTrue(CanAddProducts().has_permission(req, view=None))

    def test_can_add_products_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_add_products=False))
        self.assertFalse(CanAddProducts().has_permission(req, view=None))

    def test_can_add_products_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_add_products=True))
        self.assertFalse(CanAddProducts().has_permission(req, view=None))

    def test_can_add_products_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanAddProducts().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# CanEditProducts (R15)
# ---------------------------------------------------------------------------

class TestCanEditProducts(TestCase):
    """R15: total OR (parcial AND can_edit_products)."""

    def test_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_edit_products=False))
        self.assertTrue(CanEditProducts().has_permission(req, view=None))

    def test_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_edit_products=True))
        self.assertTrue(CanEditProducts().has_permission(req, view=None))

    def test_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_edit_products=False))
        self.assertFalse(CanEditProducts().has_permission(req, view=None))

    def test_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_edit_products=True))
        self.assertFalse(CanEditProducts().has_permission(req, view=None))

    def test_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanEditProducts().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# CanEditPrices (R16)
# ---------------------------------------------------------------------------

class TestCanEditPrices(TestCase):
    """R16: total OR (parcial AND can_edit_prices)."""

    def test_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_edit_prices=False))
        self.assertTrue(CanEditPrices().has_permission(req, view=None))

    def test_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_edit_prices=True))
        self.assertTrue(CanEditPrices().has_permission(req, view=None))

    def test_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_edit_prices=False))
        self.assertFalse(CanEditPrices().has_permission(req, view=None))

    def test_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_edit_prices=True))
        self.assertFalse(CanEditPrices().has_permission(req, view=None))

    def test_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanEditPrices().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# CanManageDiscountCodes (R17)
# ---------------------------------------------------------------------------

class TestCanManageDiscountCodes(TestCase):
    """R17: total OR (parcial AND can_manage_discount_codes)."""

    def test_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_manage_discount_codes=False))
        self.assertTrue(CanManageDiscountCodes().has_permission(req, view=None))

    def test_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_manage_discount_codes=True))
        self.assertTrue(CanManageDiscountCodes().has_permission(req, view=None))

    def test_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_manage_discount_codes=False))
        self.assertFalse(CanManageDiscountCodes().has_permission(req, view=None))

    def test_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_manage_discount_codes=True))
        self.assertFalse(CanManageDiscountCodes().has_permission(req, view=None))

    def test_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanManageDiscountCodes().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# CanApplyDiscounts (R18)
# ---------------------------------------------------------------------------

class TestCanApplyDiscounts(TestCase):
    """R18: total OR (parcial AND can_apply_discounts)."""

    def test_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_apply_discounts=False))
        self.assertTrue(CanApplyDiscounts().has_permission(req, view=None))

    def test_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_apply_discounts=True))
        self.assertTrue(CanApplyDiscounts().has_permission(req, view=None))

    def test_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_apply_discounts=False))
        self.assertFalse(CanApplyDiscounts().has_permission(req, view=None))

    def test_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_apply_discounts=True))
        self.assertFalse(CanApplyDiscounts().has_permission(req, view=None))

    def test_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanApplyDiscounts().has_permission(req, view=None))


# ---------------------------------------------------------------------------
# CanManageOffers (R19)
# ---------------------------------------------------------------------------

class TestCanManageOffers(TestCase):
    """R19: total OR (parcial AND can_manage_offers)."""

    def test_allows_total_regardless_of_flag(self):
        req = _request_with_user(_fake_user(role="total", can_manage_offers=False))
        self.assertTrue(CanManageOffers().has_permission(req, view=None))

    def test_allows_parcial_with_flag_true(self):
        req = _request_with_user(_fake_user(role="parcial", can_manage_offers=True))
        self.assertTrue(CanManageOffers().has_permission(req, view=None))

    def test_rejects_parcial_with_flag_false(self):
        req = _request_with_user(_fake_user(role="parcial", can_manage_offers=False))
        self.assertFalse(CanManageOffers().has_permission(req, view=None))

    def test_rejects_none(self):
        req = _request_with_user(_fake_user(role="none", can_manage_offers=True))
        self.assertFalse(CanManageOffers().has_permission(req, view=None))

    def test_rejects_unauthenticated(self):
        req = _request_with_user(_anon_user())
        self.assertFalse(CanManageOffers().has_permission(req, view=None))
