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
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.db.models import Q
from datetime import date

from .forms import LoginFormulario
from .models import Usuario, Empresa, UsuarioEmpresa
from .models_planes import Plan, EmpresaPlan, HistorialPlan


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
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Se generará automáticamente desde el RUC (personas naturales usan su cédula sin el 001)"
    )
    email = forms.EmailField()
    password = forms.CharField(required=False, widget=forms.PasswordInput)
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(activo=True),
        required=False,
        help_text="Plan de facturación para esta empresa (define el límite de documentos).",
    )

    class Meta:
        model = Empresa
        fields = "__all__"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # En creación: exigir plan (si hay planes activos); en edición permitir dejar en blanco
        if not getattr(self.instance, 'pk', None):
            self.fields['plan'].required = Plan.objects.filter(activo=True).exists()
        else:
            self.fields['plan'].required = False
            try:
                self.fields['plan'].initial = self.instance.plan_activo.plan
            except Exception:
                pass
        
        # Si hay RUC en el formulario, prellenar el username automáticamente
        if 'ruc' in self.data:
            ruc = self.data.get('ruc', '')
            if ruc and len(ruc) == 13:
                # Si es persona natural (termina en 001), extraer cédula
                if ruc.endswith('001'):
                    self.fields['username'].initial = ruc[:10]  # Primeros 10 dígitos = cédula
                    self.fields['username'].help_text = f"Cédula extraída del RUC: {ruc[:10]}"
                else:
                    # Para empresas, usar el RUC completo
                    self.fields['username'].initial = ruc
                    self.fields['username'].help_text = f"RUC completo: {ruc}"
    
    def clean_username(self):
        """Valida que el username sea único"""
        username = self.cleaned_data.get('username')

        # En edición, este campo solo aplica a la creación de usuario; no validar ni autogenerar
        if getattr(self.instance, 'pk', None):
            return username
        
        # Si viene vacío, generar automáticamente desde RUC
        if not username:
            ruc = self.cleaned_data.get('ruc', '')
            if ruc and len(ruc) == 13:
                if ruc.endswith('001'):
                    username = ruc[:10]  # Cédula
                else:
                    username = ruc  # RUC completo
        
        # Validar que no exista
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                f'Ya existe un usuario con username {username}'
            )
        
        return username
    
    def clean_email(self):
        """Valida que el email sea único"""
        email = self.cleaned_data.get('email')

        # En edición, este campo solo aplica a la creación de usuario; no validar unicidad
        if getattr(self.instance, 'pk', None):
            return email
        if email:
            User = get_user_model()
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError(
                    f'Ya existe un usuario con el email {email}'
                )
        return email


class EmpresaAdmin(admin.ModelAdmin):
    form = EmpresaAdminForm
    readonly_fields = ("creada_en", "creada_por")
    list_display = (
        "razon_social",
        "ruc",
        "tipo_ambiente",
        "plan_nombre",
        "plan_uso",
        "creada_en",
        "documentos_emitidos",
        "total_usuarios",
    )
    list_filter = ("tipo_ambiente", "creada_en")
    search_fields = ("razon_social", "ruc")
    ordering = ("-creada_en",)

    def get_queryset(self, request):  # type: ignore[override]
        qs = super().get_queryset(request)
        return qs.select_related('plan_activo__plan')

    def plan_nombre(self, obj):
        ep = getattr(obj, 'plan_activo', None)
        return ep.plan.nombre if ep and getattr(ep, 'plan', None) else '—'
    plan_nombre.short_description = 'Plan'

    def plan_uso(self, obj):
        ep = getattr(obj, 'plan_activo', None)
        if not ep or not getattr(ep, 'plan', None):
            return '—'
        return f"{ep.documentos_autorizados}/{ep.plan.limite_documentos}"
    plan_uso.short_description = 'Uso'

    def documentos_emitidos(self, obj):
        """Muestra el total de DOCUMENTOS emitidos (autorizados).

        Nota: esto cuenta autorizados reales (por flags/campos SRI), independientemente
        de si la empresa tiene un plan asignado.
        """
        from inventario.models import Factura, GuiaRemision
        from inventario.nota_credito.models import NotaCredito
        from inventario.nota_debito.models import NotaDebito
        from inventario.liquidacion_compra.models import LiquidacionCompra

        def _mgr(model_cls):
            return getattr(model_cls, '_unsafe_objects', model_cls.objects)

        factura_count = _mgr(Factura).filter(
            empresa=obj,
        ).filter(
            Q(numero_autorizacion__isnull=False, fecha_autorizacion__isnull=False)
            | Q(estado_sri__in=['AUTORIZADA', 'AUTORIZADO'])
        ).count()

        nc_count = _mgr(NotaCredito).filter(
            empresa=obj,
        ).filter(
            Q(numero_autorizacion__isnull=False, fecha_autorizacion__isnull=False)
            | Q(estado_sri__in=['AUTORIZADA', 'AUTORIZADO'])
        ).count()

        nd_count = _mgr(NotaDebito).filter(
            empresa=obj,
        ).filter(
            Q(numero_autorizacion__isnull=False, fecha_autorizacion__isnull=False)
            | Q(estado_sri__in=['AUTORIZADA', 'AUTORIZADO'])
        ).count()

        guia_count = _mgr(GuiaRemision).filter(
            empresa=obj,
        ).filter(
            Q(numero_autorizacion__isnull=False, fecha_autorizacion__isnull=False)
            | Q(estado='autorizada')
        ).count()

        liq_count = _mgr(LiquidacionCompra).filter(
            empresa=obj,
        ).filter(
            Q(numero_autorizacion__isnull=False, fecha_autorizacion__isnull=False)
            | Q(estado_sri__in=['AUTORIZADA', 'AUTORIZADO'])
        ).count()

        return factura_count + nc_count + nd_count + guia_count + liq_count
    documentos_emitidos.short_description = 'Documentos'
    
    def total_usuarios(self, obj):
        """Muestra el total de usuarios de la empresa"""
        return obj.usuarios.count()
    total_usuarios.short_description = "Usuarios"
    
    def get_deleted_objects(self, objs, request):
        """
        Personaliza el mensaje de eliminación para mostrar un resumen claro
        de todo lo que se eliminará con la empresa
        """
        from django.contrib.admin.utils import NestedObjects
        from django.utils.encoding import force_str
        
        collector = NestedObjects(using='default')
        collector.collect(objs)
        
        def format_callback(obj):
            opts = obj._meta
            no_edit_link = f"{force_str(opts.verbose_name)}: {force_str(obj)}"
            return no_edit_link
        
        to_delete = collector.nested(format_callback)
        
        # Contar objetos por tipo
        protected = []
        model_count = {}
        
        for model, instances in collector.model_objs.items():
            count = len(instances)
            model_count[model._meta.verbose_name_plural] = count
        
        # Crear resumen personalizado
        perms_needed = set()
        
        return to_delete, model_count, perms_needed, protected

    def delete_queryset(self, request, queryset):
        """Elimina múltiples empresas con TODOS sus datos relacionados"""
        for empresa in queryset:
            self._delete_empresa_completa(empresa)
        
        messages.success(request, f"Se eliminaron {queryset.count()} empresas y TODOS sus datos relacionados.")

    def delete_model(self, request, obj):
        """Elimina una empresa individual con TODOS sus datos"""
        empresa_nombre = obj.razon_social
        
        # Contar algunos elementos antes de eliminar
        from inventario.models import Factura, Cliente, Producto
        facturas_count = Factura._unsafe_objects.filter(empresa=obj).count()
        clientes_count = Cliente._unsafe_objects.filter(empresa=obj).count()
        productos_count = Producto._unsafe_objects.filter(empresa=obj).count()
        usuarios_count = obj.usuarios.exclude(is_superuser=True).count()
        
        # Eliminar todo
        self._delete_empresa_completa(obj)
        
        messages.success(
            request,
            f'Empresa "{empresa_nombre}" eliminada exitosamente junto con '
            f'{facturas_count} facturas, {clientes_count} clientes, {productos_count} productos, '
            f'{usuarios_count} usuarios y TODOS los datos relacionados.'
        )
    
    def _delete_empresa_completa(self, empresa):
        """Método privado que elimina ABSOLUTAMENTE TODO de una empresa"""
        from inventario.models import (
            # Modelos principales
            Factura, Cliente, Producto, Banco, Servicio, Proforma,
            Almacen, Opciones,
            # Modelos de pedidos
            Proveedor, Pedido, DetallePedido,
            # Modelos de configuración
            Notificaciones, Secuencia, Caja, MaquinaFiscal,
            # Modelos de guías de remisión
            GuiaRemision, DetalleGuiaRemision, DestinatarioGuia, 
            DetalleDestinatarioGuia, ConfiguracionGuiaRemision, Transportista,
            # Otros
            TipoNegociable
        )
        
        # ELIMINAR TODO EN ORDEN (los CASCADE se encargarán de relaciones)
        # 1. Facturas y todo lo relacionado (detalles, impuestos, formas pago, etc se borran en CASCADE)
        Factura._unsafe_objects.filter(empresa=empresa).delete()
        
        # 2. Proformas y detalles (CASCADE)
        Proforma._unsafe_objects.filter(empresa=empresa).delete()
        
        # 3. Guías de remisión (CASCADE eliminará DestinatarioGuia automáticamente)
        GuiaRemision._unsafe_objects.filter(empresa=empresa).delete()
        
        # 4. Pedidos y detalles (CASCADE)
        Pedido._unsafe_objects.filter(empresa=empresa).delete()
        
        # 5. Clientes, Productos, Servicios
        Cliente._unsafe_objects.filter(empresa=empresa).delete()
        Producto._unsafe_objects.filter(empresa=empresa).delete()
        Servicio._unsafe_objects.filter(empresa=empresa).delete()
        
        # 6. Proveedores y Transportistas
        Proveedor._unsafe_objects.filter(empresa=empresa).delete()
        Transportista._unsafe_objects.filter(empresa=empresa).delete()
        
        # 7. Configuraciones
        Banco._unsafe_objects.filter(empresa=empresa).delete()
        Almacen._unsafe_objects.filter(empresa=empresa).delete()
        Caja._unsafe_objects.filter(empresa=empresa).delete()
        MaquinaFiscal._unsafe_objects.filter(empresa=empresa).delete()
        Secuencia._unsafe_objects.filter(empresa=empresa).delete()
        TipoNegociable._unsafe_objects.filter(empresa=empresa).delete()
        
        # 8. Notificaciones y Opciones
        Notificaciones._unsafe_objects.filter(empresa=empresa).delete()
        Opciones._unsafe_objects.filter(empresa=empresa).delete()
        
        # 9. Eliminar usuarios asociados (solo si no son superusuarios y solo pertenecen a esta empresa)
        usuarios_empresa = empresa.usuarios.all()
        for usuario in usuarios_empresa:
            if not usuario.is_superuser and usuario.empresas.count() == 1:
                # Eliminar cualquier dato del usuario primero
                try:
                    usuario.delete()
                except Exception as e:
                    # Si falla, intentar eliminar relaciones protegidas manualmente
                    from inventario.models import Caja
                    Caja._unsafe_objects.filter(creado_por=usuario).delete()
                    usuario.delete()
        
        # 10. Finalmente eliminar la empresa
        empresa.delete()

    def get_form(self, request, obj=None, **kwargs):  # type: ignore[override]
        form = super().get_form(request, obj, **kwargs)
        if obj is not None:
            for field in ["username", "email", "password"]:
                form.base_fields[field].required = False
        return form

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        creating = not change
        if creating and not obj.creada_por_id:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)

        # Sincronizar plan seleccionado (creación y edición)
        selected_plan = form.cleaned_data.get('plan')
        if selected_plan:
            self._sync_empresa_plan(obj, selected_plan, actor=request.user)
        if creating:
            User = get_user_model()
            
            # Obtener username (ya validado y generado en clean_username)
            username = form.cleaned_data.get("username")
            
            # Si viene vacío, generar automáticamente desde RUC
            if not username:
                ruc = obj.ruc
                if ruc and len(ruc) == 13:
                    if ruc.endswith('001'):
                        username = ruc[:10]  # Persona natural: cédula sin 001
                    else:
                        username = ruc  # Empresa: RUC completo
            
            email = form.cleaned_data.get("email")
            raw_password = form.cleaned_data.get("password")
            
            usuario = User.objects.create_user(
                username=username,
                email=email,
                password=raw_password,
            )
            # Ajustar nivel y flags (ADMIN empresa, no root)
            if hasattr(usuario, 'nivel'):
                usuario.nivel = getattr(usuario, 'ADMIN', 1)
            usuario.is_staff = True  # Puede acceder al admin tenant
            usuario.is_superuser = False  # No es superusuario global
            usuario.save(update_fields=["nivel", "is_staff", "is_superuser"])
            
            # Vincular usuario con empresa
            UsuarioEmpresa.objects.create(usuario=usuario, empresa=obj)
            
            # Crear Opciones automáticamente
            from inventario.models import Opciones
            if not Opciones.objects.filter(empresa=obj).exists():
                Opciones.objects.create(
                    empresa=obj,
                    identificacion=obj.ruc,
                    razon_social=obj.razon_social,
                    tipo_ambiente=obj.tipo_ambiente,
                    direccion_establecimiento='[POR CONFIGURAR]',
                    correo=email,
                    telefono='0000000000',
                )
            
            # Enviar correo con credenciales de bienvenida (pasar email explícitamente)
            from inventario.email_service import enviar_credenciales_nueva_empresa
            enviar_credenciales_nueva_empresa(obj, usuario, raw_password, email_destino=email)
            
            self._send_password_setup_email(request, usuario, email)
            
            # Mensaje informativo según tipo de RUC
            if obj.ruc.endswith('001'):
                mensaje_login = f"El usuario podrá iniciar sesión con su cédula: {username}"
            else:
                mensaje_login = f"El usuario podrá iniciar sesión con su RUC: {username}"
            
            messages.success(
                request,
                f"Empresa '{obj.razon_social}' creada exitosamente.\n"
                f"Usuario {username} creado. {mensaje_login}\n"
                f"Se envió un enlace a {email} para establecer la contraseña."
            )

    def _sync_empresa_plan(self, empresa: Empresa, new_plan: Plan, actor=None) -> None:
        """Crea o actualiza el plan activo de una empresa y registra historial al cambiar."""
        empresa_plan, created = EmpresaPlan.objects.get_or_create(
            empresa=empresa,
            defaults={
                'plan': new_plan,
                'activo': True,
            },
        )

        if created:
            return

        if empresa_plan.plan_id == new_plan.id:
            return

        # Registrar historial del plan previo
        HistorialPlan.objects.create(
            empresa=empresa,
            plan=empresa_plan.plan,
            fecha_inicio=empresa_plan.fecha_inicio,
            fecha_fin=empresa_plan.fecha_fin or date.today(),
            documentos_autorizados=empresa_plan.documentos_autorizados,
            observaciones=(
                f"Cambio de plan vía admin por {getattr(actor, 'username', 'sistema')}" if actor else None
            ),
        )

        # Activar nuevo plan y resetear contador para el nuevo periodo
        empresa_plan.plan = new_plan
        empresa_plan.fecha_inicio = date.today()
        empresa_plan.fecha_fin = None
        empresa_plan.documentos_autorizados = 0
        empresa_plan.ultimo_reset = date.today()
        empresa_plan.notificacion_enviada = False
        empresa_plan.notificacion_limite_enviada = False
        empresa_plan.activo = True
        empresa_plan.save()

    def _send_password_setup_email(self, request, usuario, email):
        if not email:
            return
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        reset_path = reverse(
            "inventario:password_reset_confirm",
            kwargs={"uidb64": uid, "token": token},
        )
        reset_url = request.build_absolute_uri(reset_path)
        subject = "Configura tu contraseña"
        message = (
            "Se creó un usuario administrador para tu empresa.\n\n"
            "Para establecer tu contraseña inicial, abre el siguiente enlace "
            "(solo válido una vez):\n"
            f"{reset_url}\n\n"
            "Si no solicitaste este acceso, ignora este correo."
        )
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            [email],
            fail_silently=True,
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
    
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser", "nivel_str", "empresas_asociadas")
    list_filter = ("is_staff", "is_superuser", "nivel", "empresas")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    
    def nivel_str(self, obj):
        """Muestra el nivel del usuario de forma legible"""
        niveles = {0: "Usuario", 1: "Admin", 2: "Root"}
        return niveles.get(obj.nivel, "Desconocido")
    nivel_str.short_description = "Nivel"
    
    def empresas_asociadas(self, obj):
        """Muestra las empresas asociadas al usuario"""
        empresas = obj.empresas.all()
        if empresas:
            return ", ".join([e.razon_social[:30] for e in empresas])
        return "Ninguna"
    empresas_asociadas.short_description = "Empresas"

    def _is_root(self, obj):
        return obj and (
            getattr(obj, "is_protected", False)
            or getattr(obj, "username", "") == "root"
        )

    def has_delete_permission(self, request, obj=None):  # type: ignore[override]
        if self._is_root(obj):
            messages.warning(request, "El usuario root está protegido y no puede ser eliminado.")
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        if self._is_root(obj):
            messages.warning(request, "El usuario root está protegido y no puede ser modificado.")
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


# Registrar administración de planes
from .admin_planes import PlanAdmin, EmpresaPlanAdmin, HistorialPlanAdmin
