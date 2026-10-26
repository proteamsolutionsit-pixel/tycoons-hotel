"""Role-based access control.

Every admin endpoint declares the permission it needs (see api/deps.require).
What a user may do comes from their access role (models.role.Role), which
administrators define in Admin > Roles & access: the Administrator role has
every permission; any other role has the permissions ticked for it.

ROLE_PERMISSIONS below is the original fixed two-role mapping. It seeds the
built-in roles and is the fallback for a user with no access role assigned:

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
    DATA_EXPORT = "data.export"                # CSV downloads of bookings, payments, guest requests, content
    ROLES_MANAGE = "roles.manage"              # define roles; Administrator only (never grantable)


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


# Never ticked on a custom role: whoever could edit roles could grant themselves anything
NON_ASSIGNABLE = frozenset({Permission.ROLES_MANAGE})
ASSIGNABLE = tuple(p for p in Permission if p not in NON_ASSIGNABLE)

# Granting an action also grants seeing what it acts on
IMPLIES: dict[Permission, frozenset[Permission]] = {
    Permission.BOOKINGS_MANAGE: frozenset({Permission.BOOKINGS_VIEW}),
    Permission.PAYMENTS_RECONCILE: frozenset({Permission.PAYMENTS_VIEW, Permission.BOOKINGS_VIEW}),
    Permission.PAYMENTS_REFUND: frozenset({Permission.PAYMENTS_VIEW, Permission.BOOKINGS_VIEW, Permission.BOOKINGS_MANAGE}),
    Permission.SUBMISSIONS_MANAGE: frozenset({Permission.SUBMISSIONS_VIEW}),
    Permission.CATALOG_MANAGE: frozenset({Permission.CATALOG_VIEW}),
    Permission.CONTENT_MANAGE: frozenset({Permission.CATALOG_VIEW}),
    Permission.SETTINGS_MANAGE: frozenset({Permission.CATALOG_VIEW}),
}

# (group, label, description) for the role editor, in display order
PERMISSION_INFO: dict[Permission, tuple[str, str, str]] = {
    Permission.DASHBOARD_VIEW: ("Operations", "Dashboard", "Key figures, alerts and new guest requests."),
    Permission.BOOKINGS_VIEW: ("Operations", "View bookings & occupancy", "Booking list, details and the occupancy calendar."),
    Permission.BOOKINGS_MANAGE: ("Operations", "Manage bookings", "Cancel bookings without a refund; confirm bookings held for review."),
    Permission.PAYMENTS_VIEW: ("Operations", "View payments", "Razorpay orders, captures and refunds."),
    Permission.PAYMENTS_RECONCILE: ("Operations", "Re-check payments", "Ask Razorpay again for a payment's status."),
    Permission.PAYMENTS_REFUND: ("Operations", "Issue refunds", "Refund a captured payment when cancelling a booking."),
    Permission.SUBMISSIONS_VIEW: ("Operations", "View guest requests", "Reservations, spa bookings, enquiries, applications, newsletter."),
    Permission.SUBMISSIONS_MANAGE: ("Operations", "Handle guest requests", "Change status and notes; unsubscribe newsletter readers."),
    Permission.CATALOG_VIEW: ("Property", "View rooms, content & settings", "Read-only access to rooms & rates, content and site settings."),
    Permission.CATALOG_MANAGE: ("Property", "Edit rooms & rates", "Room types, rates and inventory."),
    Permission.CONTENT_MANAGE: ("Property", "Edit content", "Spa treatments, cards, gallery, job openings and image uploads."),
    Permission.SETTINGS_MANAGE: ("Property", "Edit site settings", "Contact details, hours, policies and other site text."),
    Permission.PAYMENTS_SETTINGS: ("Administration", "Payment gateway", "Switch payment mode and change the Razorpay keys."),
    Permission.USERS_MANAGE: ("Administration", "Manage staff users", "Create users, assign roles, reset passwords (up to their own access)."),
    Permission.AUDIT_VIEW: ("Administration", "Audit log", "Who did what, when."),
    Permission.DATA_EXPORT: ("Administration", "Export CSV", "Download lists that include guests' personal details."),
    Permission.ROLES_MANAGE: ("Administration", "Roles & access", "Define roles. Administrator role only."),
}


def normalise(values) -> list[str]:
    """Known, grantable permissions plus everything they imply, in catalogue order."""
    chosen = {p for p in ASSIGNABLE if p.value in set(values or [])}
    for p in list(chosen):
        chosen |= IMPLIES.get(p, frozenset())
    return [p.value for p in PERMISSION_INFO if p in chosen]


def user_permissions(user) -> frozenset[Permission]:
    """What this user may do right now (read on every request, so role changes apply at once)."""
    role = getattr(user, "access_role", None)
    if role is None:
        return permissions_for(user.role)
    if role.is_system:
        return frozenset(Permission)
    return frozenset(Permission(v) for v in normalise(role.permissions))


def user_can(user, permission: Permission) -> bool:
    return permission in user_permissions(user)
