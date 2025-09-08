import logging
from .queryset import get_current_tenant


class TenantContextFilter(logging.Filter):
    """Inserta tenant_id en cada registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        tenant = get_current_tenant()
        record.tenant_id = getattr(tenant, 'id', None)
        return True
