"""Role-based access control.

Every admin endpoint declares the permission it needs (see api/deps.require).
Roles map to permission sets here, in one place. The two roles are the ones
the application already had; their effective rights are unchanged:

* staff - front-desk work: read bookings/payments, handle guest requests,
          read (not change) rates, content and settings.
* admin - everything, including refunds, payment gateway keys, rates,
          content, settings, users and the audit log.
"""
from __future__ import annotations

import enum

from app.models.enums import AdminRole


class Permission(str, enum.Enum):
    DASHBOARD_VIEW = "dashboard.view"
    BOOKINGS_VIEW = "bookings.view"
    BOOKINGS_MANAGE = "bookings.manage"        # cancel without refund, confirm after review
    PAYMENTS_VIEW = "payments.view"
    PAYMENTS_RECONCILE = "payments.reconcile"
    PAYMENTS_REFUND = "payments.refund"
    PAYMENTS_SETTINGS = "payments.settings"    # gateway mode and Razorpay keys
    SUBMISSIONS_VIEW = "submissions.view"
    SUBMISSIONS_MANAGE = "submissions.manage"
    CATALOG_VIEW = "catalog.view"              # rooms & rates, content, settings (read)
    CATALOG_MANAGE = "catalog.manage"          # rooms & rates
    CONTENT_MANAGE = "content.manage"          # treatments, cards, gallery, openings, uploads
    SETTINGS_MANAGE = "settings.manage"
    USERS_MANAGE = "users.manage"
    AUDIT_VIEW = "audit.view"


ROLE_PERMISSIONS: dict[AdminRole, frozenset[Permission]] = {
    AdminRole.STAFF: frozenset({
        Permission.DASHBOARD_VIEW, Permission.BOOKINGS_VIEW, Permission.PAYMENTS_VIEW,
        Permission.SUBMISSIONS_VIEW, Permission.SUBMISSIONS_MANAGE, Permission.CATALOG_VIEW,
    }),
    AdminRole.ADMIN: frozenset(Permission),
}


def permissions_for(role: AdminRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: AdminRole, permission: Permission) -> bool:
    return permission in permissions_for(role)
