from django.contrib import admin
from django.contrib.admin import AdminSite
from django.apps import apps
from django.contrib.auth.admin import UserAdmin

from .forms import LoginFormulario
from .models import Usuario


class TenantAdminSite(AdminSite):
    """Admin site that removes the ``tenant`` kwarg from admin views."""

    def admin_view(self, view, cacheable=False):  # type: ignore[override]
        base_view = super().admin_view(view, cacheable)

        def inner(request, *args, **kwargs):
            kwargs.pop("tenant", None)
            return base_view(request, *args, **kwargs)

        return inner


tenant_admin_site = TenantAdminSite(name="tenant_admin")


class TenantModelAdmin(admin.ModelAdmin):
    list_filter = ("empresa",)
    search_fields = ("empresa__razon_social",)

    def get_queryset(self, request):  # type: ignore[override]
        qs = super().get_queryset(request)
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return qs.none()
        return qs.filter(empresa=tenant)


class UsuarioAdmin(UserAdmin):
    add_form = LoginFormulario
    model = Usuario
    list_display = ["email", "username"]
    list_filter = ("empresas",)
    search_fields = ("empresas__razon_social",)

    def get_queryset(self, request):  # type: ignore[override]
        qs = super().get_queryset(request)
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return qs.none()
        return qs.filter(empresas=tenant)


tenant_admin_site.register(Usuario, UsuarioAdmin)


for model in apps.get_app_config("inventario").get_models():
    if model is Usuario:
        continue
    if any(f.name == "empresa" for f in model._meta.fields):
        admin_class = type(f"{model.__name__}Admin", (TenantModelAdmin,), {})
        try:
            tenant_admin_site.register(model, admin_class)
        except admin.sites.AlreadyRegistered:
            pass
