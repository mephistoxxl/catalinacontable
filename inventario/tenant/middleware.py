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
        if header_value:
            return (
                Empresa.objects.filter(id=header_value).first()
                or Empresa.objects.filter(ruc=header_value).first()
            )
        return None
