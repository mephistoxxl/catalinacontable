from django.conf import settings
from django.contrib.auth import get_user
from django.utils.deprecation import MiddlewareMixin

from inventario.models import Empresa

from .queryset import set_current_tenant


class TenantMiddleware(MiddlewareMixin):
    """Determines the active tenant based on subdomain or request header.

    The resolved :class:`~inventario.models.Empresa` instance is stored on
    ``request.tenant`` and also made available to the thread-local storage used
    by :class:`~inventario.tenant.queryset.TenantManager`.
    """

    header_name = "X-Tenant"

    def process_request(self, request):
        tenant = self._resolve_tenant(request)
        request.tenant = tenant
        set_current_tenant(tenant)

    def process_response(self, request, response):
        # Clean thread local after response
        set_current_tenant(None)
        return response

    def _resolve_tenant(self, request):
        path_parts = [p for p in request.path.strip("/").split("/") if p]
        if path_parts:
            slug = path_parts[0]
            tenant = None
            if slug.isdigit():
                tenant = (
                    Empresa.objects.filter(id=int(slug)).first()
                    or Empresa.objects.filter(ruc=slug).first()
                )
            if tenant:
                return tenant
        host = request.get_host().split(":")[0]
        subdomain = host.split(".")[0] if "." in host else None
        if subdomain and subdomain not in ("www", "localhost"):
            tenant = Empresa.objects.filter(ruc=subdomain).first()
            if tenant:
                return tenant
        header_value = request.headers.get(self.header_name)
        if header_value and self._is_header_allowed(request):
            return (
                Empresa.objects.filter(id=header_value).first()
                or Empresa.objects.filter(ruc=header_value).first()
            )
        empresa_id = request.session.get("empresa_activa")
        if empresa_id:
            return Empresa.objects.filter(id=empresa_id).first()
        return None

    def _is_header_allowed(self, request):
        """Return ``True`` when the X-Tenant header may be trusted."""

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            # ``AuthenticationMiddleware`` runs after this middleware, so
            # ``request.user`` might not be populated yet.
            try:
                user = get_user(request)
            except Exception:
                user = None

        if user is not None and getattr(user, "is_authenticated", False):
            if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
                return True

        remote_addr = request.META.get("REMOTE_ADDR")
        allowed_ips = getattr(settings, "TENANT_HEADER_ALLOWED_IPS", None)
        if allowed_ips is None:
            allowed_ips = getattr(settings, "INTERNAL_IPS", [])
        if remote_addr and remote_addr in allowed_ips:
            return True
        return False
