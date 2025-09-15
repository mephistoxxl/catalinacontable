from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.apps import apps
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django import forms
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, reverse
from django.utils.text import capfirst
from django.conf import settings
from django.core.mail import send_mail

from .forms import LoginFormulario
from .models import Usuario, Empresa, UsuarioEmpresa


class RootAdminSite(AdminSite):
    def has_permission(self, request):  # type: ignore[override]
        return request.user.is_active and request.user.is_superuser


root_admin_site = RootAdminSite(name="root_admin")


class TenantAdminSite(AdminSite):
    """Admin site that removes the ``tenant`` kwarg from admin views."""

    def has_permission(self, request):  # type: ignore[override]
        user = request.user
        tenant = getattr(request, "tenant", None)
        return user.is_active and user.is_staff and (
            user.is_superuser or tenant in user.empresas.all()
        )

    def admin_view(self, view, cacheable=False):  # type: ignore[override]
        base_view = super().admin_view(view, cacheable)

        def inner(request, *args, **kwargs):
            kwargs.pop("tenant", None)
            return base_view(request, *args, **kwargs)

        return inner

    def _build_app_dict(self, request, label=None):  # type: ignore[override]
        """
        Build the app dictionary. The optional `label` parameter filters models
        of a specific app.
        """
        tenant = getattr(request, "tenant", None)
        app_dict = {}

        if label:
            models = {
                m: m_a
                for m, m_a in self._registry.items()
                if m._meta.app_label == label
            }
        else:
            models = self._registry

        for model, model_admin in models.items():
            app_label = model._meta.app_label

            has_module_perms = model_admin.has_module_permission(request)
            if not has_module_perms:
                continue

            perms = model_admin.get_model_perms(request)

            # Check whether user has any perm for this module.
            # If so, add the module to the model_list.
            if True not in perms.values():
                continue

            info = (app_label, model._meta.model_name)
            model_dict = {
                "model": model,
                "name": capfirst(model._meta.verbose_name_plural),
                "object_name": model._meta.object_name,
                "perms": perms,
                "admin_url": None,
                "add_url": None,
            }
            if perms.get("change") or perms.get("view"):
                model_dict["view_only"] = not perms.get("change")
                try:
                    model_dict["admin_url"] = reverse(
                        "admin:%s_%s_changelist" % info,
                        kwargs={"tenant": tenant.ruc},
                        current_app=self.name,
                    )
                except NoReverseMatch:
                    pass
            if perms.get("add"):
                try:
                    model_dict["add_url"] = reverse(
                        "admin:%s_%s_add" % info,
                        kwargs={"tenant": tenant.ruc},
                        current_app=self.name,
                    )
                except NoReverseMatch:
                    pass

            if app_label in app_dict:
                app_dict[app_label]["models"].append(model_dict)
            else:
                app_dict[app_label] = {
                    "name": apps.get_app_config(app_label).verbose_name,
                    "app_label": app_label,
                    "app_url": reverse(
                        "admin:app_list",
                        kwargs={"app_label": app_label, "tenant": tenant.ruc},
                        current_app=self.name,
                    ),
                    "has_module_perms": has_module_perms,
                    "models": [model_dict],
                }

        return app_dict

    def get_app_list(self, request, app_label=None):  # type: ignore[override]
        app_dict = self._build_app_dict(request, app_label)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())

        # Sort the models alphabetically within each app.
        for app in app_list:
            app["models"].sort(key=lambda x: x["name"])

        return app_list

    def index(self, request, extra_context=None):  # type: ignore[override]
        app_list = self.get_app_list(request)

        context = {
            **self.each_context(request),
            "title": self.index_title,
            "subtitle": None,
            "app_list": app_list,
            **(extra_context or {}),
        }

        request.current_app = self.name

        return TemplateResponse(
            request, self.index_template or "admin/index.html", context
        )


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


class EmpresaAdminForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(required=False, widget=forms.PasswordInput)

    class Meta:
        model = Empresa
        fields = "__all__"


class EmpresaAdmin(admin.ModelAdmin):
    form = EmpresaAdminForm

    def get_form(self, request, obj=None, **kwargs):  # type: ignore[override]
        form = super().get_form(request, obj, **kwargs)
        if obj is not None:
            for field in ["username", "email", "password"]:
                form.base_fields[field].required = False
        return form

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        creating = not change
        super().save_model(request, obj, form, change)
        if creating:
            User = get_user_model()
            username = form.cleaned_data.get("username")
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password") or User.objects.make_random_password()
            usuario = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            # Ajustar nivel y flags (ADMIN empresa, no root)
            if hasattr(usuario, 'nivel'):
                usuario.nivel = getattr(usuario, 'ADMIN', 1)
            usuario.is_staff = True  # Puede acceder al admin tenant
            usuario.is_superuser = False  # No es superusuario global
            usuario.save(update_fields=["nivel", "is_staff", "is_superuser"])
            UsuarioEmpresa.objects.create(usuario=usuario, empresa=obj)
            send_mail(
                "Credenciales de acceso",
                f"Usuario: {username}\nContraseña: {password}",
                getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
                [email],
                fail_silently=True,
            )
            messages.info(
                request,
                f"Usuario {username} creado. Se enviaron las credenciales a {email}.",
            )


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
        return (
            qs.filter(empresas=tenant, is_superuser=False)
            .exclude(is_staff=True)
            .exclude(groups__name="Administrador")
        )

    def get_form(self, request, obj=None, **kwargs):  # type: ignore[override]
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            for field in ["is_superuser", "groups", "user_permissions"]:
                if field in form.base_fields:
                    form.base_fields.pop(field)
        return form

    def formfield_for_manytomany(self, db_field, request, **kwargs):  # type: ignore[override]
        if db_field.name == "empresas":
            tenant = getattr(request, "tenant", None)
            if tenant is not None:
                kwargs["queryset"] = Empresa.objects.filter(pk=tenant.pk)
                kwargs["initial"] = [tenant]
                form_field = super().formfield_for_manytomany(db_field, request, **kwargs)
                if not request.user.is_superuser:
                    form_field.disabled = True
                return form_field
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        super().save_model(request, obj, form, change)
        if not obj.is_superuser:
            tenant = getattr(request, "tenant", None)
            if tenant is not None:
                obj.empresas.set([tenant])

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        has_perm = super().has_change_permission(request, obj)
        if not has_perm:
            return False
        if obj is not None and not request.user.is_superuser:
            if obj.is_staff or obj.is_superuser:
                return False
            tenant = getattr(request, "tenant", None)
            if tenant is not None and tenant not in obj.empresas.all():
                return False
        return True

    def has_delete_permission(self, request, obj=None):  # type: ignore[override]
        has_perm = super().has_delete_permission(request, obj)
        if not has_perm:
            return False
        if obj is not None and not request.user.is_superuser:
            if obj.is_staff or obj.is_superuser:
                return False
            tenant = getattr(request, "tenant", None)
            if tenant is not None and tenant not in obj.empresas.all():
                return False
        return True


tenant_admin_site.register(Usuario, UsuarioAdmin)
class RootUserAdmin(UserAdmin):
    """User admin for the root site protecting the root user."""

    def _is_root(self, obj):
        return obj and (
            getattr(obj, "is_protected", False)
            or getattr(obj, "username", "") == "root"
        )

    def has_delete_permission(self, request, obj=None):  # type: ignore[override]
        if self._is_root(obj):
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        if self._is_root(obj):
            return False
        return super().has_change_permission(request, obj)


root_admin_site.register(Usuario, RootUserAdmin)
root_admin_site.register(Empresa, EmpresaAdmin)


for model in apps.get_app_config("inventario").get_models():
    if model in (Usuario, Empresa):
        continue
    if any(f.name == "empresa" for f in model._meta.fields):
        admin_class = type(f"{model.__name__}Admin", (TenantModelAdmin,), {})
        try:
            tenant_admin_site.register(model, admin_class)
        except admin.sites.AlreadyRegistered:
            pass
    else:
        try:
            root_admin_site.register(model)
        except admin.sites.AlreadyRegistered:
            pass
