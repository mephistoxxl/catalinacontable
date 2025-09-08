from threading import local
from django.db import models


_thread_locals = local()


def set_current_tenant(tenant):
    """Store the current tenant in thread-local storage."""
    _thread_locals.tenant = tenant


def get_current_tenant():
    return getattr(_thread_locals, "tenant", None)


class TenantQuerySet(models.QuerySet):
    """QuerySet aware of the active tenant."""

    def for_tenant(self, tenant):
        if tenant is None:
            return self.none()
        return self.filter(empresa=tenant)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Manager that automatically restricts queries to the current tenant."""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is None:
            return qs.none()
        return qs.filter(empresa=tenant)

    def for_tenant(self, tenant):
        return super().get_queryset().filter(empresa=tenant)
