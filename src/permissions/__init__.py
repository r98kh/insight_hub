"""
Permissions app for centralized permission management.
All permission classes are in views.py for easy access.
"""

from .views import (
    IsOwnerOrSuperuser,
    IsSuperuserOrReadOnly,
    IsSuperuserOnly,
    IsAuthenticatedOnly,
    IsOwnerOrReadOnly,
    HasSpecificPermission,
    IsOwnerOrHasPermission,
    JobLimitPermission,
    PermissionMixin,
)

__all__ = [
    'IsOwnerOrSuperuser',
    'IsSuperuserOrReadOnly',
    'IsSuperuserOnly',
    'IsAuthenticatedOnly',
    'IsOwnerOrReadOnly',
    'HasSpecificPermission',
    'IsOwnerOrHasPermission',
    'JobLimitPermission',
    'PermissionMixin',
]