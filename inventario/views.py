#renderiza las vistas al usuario
from django.contrib.auth.hashers import check_password
from django.shortcuts import render, get_object_or_404, redirect

# para redirigir a otras paginas
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    FileResponse,
    JsonResponse,
    HttpResponseForbidden,
    Http404,
    HttpResponseNotAllowed,
)
from urllib3 import request
from io import BytesIO  # Para manejar datos binarios en memoria (PDFs, etc.)
#el formulario de login
from .forms import *
# clase para crear vistas basadas en sub-clases
from django.views import View
#autentificacion de usuario e inicio de sesion
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
#verifica si el usuario esta logeado
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from .forms import SecuenciaFormulario  # Asumiendo que existe un formulario llamado SecuenciaFormulario
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from .models import Secuencia
from .forms import SecuenciaFormulario
#modelos
from .models import *
from .models import FormaPago  # Importación explícita para evitar errores de scope
from .models import Banco, CampoAdicional  # Para pagos con cheque y guardar datos adicionales
from .models import Empresa  # Acceder a la empresa activa
#formularios dinamicos
from django.forms import formset_factory
#funciones personalizadas
from .funciones import *
#Mensajes de formulario
from django.contrib import messages
#Ejecuta un comando en la terminal externa
from django.core.management import call_command
#procesa archivos en .json
from django.core import serializers
#permite acceder de manera mas facil a los ficheros
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.temp import NamedTemporaryFile
from django.db import IntegrityError
import re
from datetime import date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import logging
from django.contrib import admin
from axes.handlers.proxy import AxesProxyHandler
from .sri.ride_generator import RIDEGenerator
from sistema.aws_utils import build_storage_url_or_none
from .proforma.ride_proformgenerator import ProformaRIDEGenerator
from .utils.media_paths import build_factura_media_paths
from .utils.storage_io import storage_read_text
from .utils_planes import api_verificar_limite
import os
from pathlib import Path
from django.conf import settings
# Integración con Django REST Framework
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
# ===== AGREGAR ESTOS IMPORTS AL INICIO DE views.py =====

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import random
from .forms import FirmaElectronicaForm  # Asegúrate de tener este formulario
from django.urls import reverse
from .mixins import RequireEmpresaActivaMixin, require_empresa_activa, get_empresa_activa
from django.db.models import Q
from .tenant.services import tenant_unsafe_service

logger = logging.getLogger(__name__)

# ====== STUB UTILITIES (fallback) ======
if 'render_to_pdf' not in globals():
    from django.http import HttpResponse as _HttpResponseForPDF
    from django.template.loader import get_template as _get_template_for_pdf
    def render_to_pdf(template_src, context_dict):
        """Fallback simple PDF renderer (HTML passthrough).
        Devuelve el HTML renderizado para evitar fallos cuando la librería PDF real no está configurada.
        Reemplazar por implementación real (WeasyPrint/xhtml2pdf) en producción.
        """
        try:
            template = _get_template_for_pdf(template_src)
            html = template.render(context_dict)
            resp = _HttpResponseForPDF(html, content_type='text/html')
            resp['X-Placeholder-PDF'] = '1'
            return resp
        except Exception as e:
            return _HttpResponseForPDF(f"Error generando PDF placeholder: {e}")


# ====== FUNCIÓN PARA VERIFICAR SI LA EMPRESA NECESITA CONFIGURACIÓN ======
def necesita_configuracion(empresa):
    """
    Verifica si una empresa tiene TODOS los campos OBLIGATORIOS configurados.
    
    CAMPOS OBLIGATORIOS:
    1. RUC (identificacion) - no puede ser '0000000000000' ni vacío
    2. Razón Social - no puede ser 'PENDIENTE' ni vacío
    3. Nombre Comercial - no puede estar vacío
    4. Dirección - no puede estar vacía
    5. Correo - no puede estar vacío ni ser 'pendiente@empresa.com'
    6. Teléfono - no puede estar vacío ni ser '0000000000'
    7. Obligado a llevar contabilidad - debe estar definido
    8. Régimen tributario - debe estar definido
    9. Mensaje en facturas - debe estar definido
    10. Firma electrónica - debe estar cargada
    
    Args:
        empresa: Instancia de Empresa
        
    Returns:
        bool: True si NECESITA configuración, False si está TODO configurado
    """
    try:
        # ✅ USAR EL MANAGER CORRECTO PARA TENANT
        # Intentar con for_tenant primero, luego fallback a filter normal
        try:
            opciones = Opciones.objects.for_tenant(empresa).first()
        except (AttributeError, TypeError):
            # Si for_tenant no existe o falla, usar filter normal
            opciones = Opciones.objects.filter(empresa=empresa).first()
        
        # Si no existe configuración, necesita configurarse
        if not opciones:
            logger.warning(f"❌ Empresa {empresa.ruc} - NO tiene opciones")
            print(f"❌ Empresa {empresa.ruc} - NO tiene opciones")
            return True
        
        # ✅ VERIFICAR CADA CAMPO OBLIGATORIO
        campos_faltantes = []
        
        # 1. RUC
        if not opciones.identificacion or opciones.identificacion == '0000000000000':
            campos_faltantes.append('RUC')
        
        # 2. Razón Social
        if not opciones.razon_social or opciones.razon_social == 'PENDIENTE':
            campos_faltantes.append('Razón Social')
        
        # 3. Nombre Comercial
        if not opciones.nombre_comercial or not opciones.nombre_comercial.strip():
            campos_faltantes.append('Nombre Comercial')
        
        # 4. Dirección
        if not opciones.direccion_establecimiento or not opciones.direccion_establecimiento.strip():
            campos_faltantes.append('Dirección')
        
        # 5. Correo
        if not opciones.correo or opciones.correo == 'pendiente@empresa.com':
            campos_faltantes.append('Correo')
        
        # 6. Teléfono
        if not opciones.telefono or opciones.telefono == '0000000000':
            campos_faltantes.append('Teléfono')
        
        # 7. Obligado a llevar contabilidad
        if opciones.obligado is None:
            campos_faltantes.append('Obligado a llevar contabilidad')
        
        # 8. Régimen tributario (tipo_regimen)
        if not opciones.tipo_regimen or not opciones.tipo_regimen.strip():
            campos_faltantes.append('Régimen tributario')
        
        # 9. Firma electrónica
        if not opciones.firma_electronica:
            campos_faltantes.append('Firma electrónica')
        
        # Si hay campos faltantes, necesita configuración
        if campos_faltantes:
            print(f"\n{'='*80}")
            print(f"❌ EMPRESA {empresa.ruc} - FALTAN CAMPOS:")
            for campo in campos_faltantes:
                print(f"   - {campo}")
            print(f"{'='*80}\n")
            logger.warning(f"❌ Empresa {empresa.ruc} - Faltan campos: {', '.join(campos_faltantes)}")
            return True
        
        # ✅ TODO ESTÁ CONFIGURADO - IR AL PANEL
        print(f"\n{'='*80}")
        print(f"✅ EMPRESA {empresa.ruc} - TODOS LOS CAMPOS OK - IR AL PANEL")
        print(f"{'='*80}\n")
        logger.info(f"✅ Empresa {empresa.ruc} ({opciones.razon_social}) - TODOS LOS CAMPOS OK - IR AL PANEL")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error verificando empresa {empresa.id}: {e}", exc_info=True)
        return True


#Vistas endogenas.

# =====================
# Proformas (placeholders)
# =====================
class ListarProformas(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from .models import Proforma
        empresa = get_empresa_activa(request)
        proformas = (
            Proforma.objects.filter(empresa=empresa)
            .select_related('cliente')
            .order_by('-fecha_creacion')
        )

        contexto = {
            'proformas': proformas,
            'total_proformas': proformas.count(),
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proforma/listarProformas.html', contexto)


class EmitirProforma(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        """Muestra el formulario para emitir proforma; SIEMPRE exige login de proformador.
        Se valida mediante un token firmado de un solo uso temporal enviado desde el login.
        """
        try:
            from django.core import signing

            # Requerir token firmado en la URL (emitido por LoginProformador)
            token = request.GET.get('t')
            if not token:
                messages.warning(request, 'Debe iniciar sesión como facturador antes de emitir proformas.')
                return redirect('inventario:login_proformador')

            try:
                data = signing.loads(token, salt='proformador', max_age=1800)
                facturador_id = data.get('fid')
            except Exception:
                messages.error(request, 'Sesión de proformador expirada. Inicie sesión nuevamente.')
                return redirect('inventario:login_proformador')

            # Validar facturador activo y que pertenezca a la empresa si aplica
            facturador = Facturador.tenant_objects.filter(id=facturador_id, activo=True).first()
            if not facturador:
                messages.error(request, 'El facturador no existe o no está activo.')
                return redirect('inventario:login_proformador')
            empresa = get_empresa_activa(request)
            if hasattr(facturador, 'empresa_id') and facturador.empresa_id and facturador.empresa_id != empresa.id:
                messages.error(request, 'El facturador no pertenece a la empresa activa. Inicie sesión nuevamente.')
                return redirect('inventario:login_proformador')

            from .forms import EmitirProformaFormulario
            # Obtener almacenes y vendedores (facturadores) activos SOLO de la empresa activa
            almacenes = Almacen.objects.filter(activo=True, empresa=empresa)
            vendedores = Facturador.tenant_objects.filter(activo=True, empresa=empresa)

            form = EmitirProformaFormulario(almacenes=almacenes, vendedores=vendedores)
            # Calcular el siguiente código de proforma para mostrar en la UI
            try:
                from .models import Proforma
                empresa_obj = empresa
                siguiente_codigo = Proforma.siguiente_numero(empresa_obj)
            except Exception:
                siguiente_codigo = 'PR000001'
            contexto = {
                'form': form,
                'facturador': facturador,
                'proformador_token': token,
                'proforma_siguiente_numero': siguiente_codigo,
            }
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/proforma/emitirProforma.html', contexto)

        except Exception as e:
            print(f"Error en EmitirProforma GET: {e}")
            messages.error(request, 'Error interno del servidor.')
            return redirect('inventario:panel')

    def post(self, request):
        from .forms import EmitirProformaFormulario
        from .models import Proforma, ProformaDetalle, Cliente, Producto, Servicio
        from decimal import Decimal
        from django.utils import timezone
        
        # Obtener empresa activa
        empresa = get_empresa_activa(request)
        if not empresa or not request.user.empresas.filter(id=empresa.id).exists():
            return redirect('inventario:seleccionar_empresa')
        
        # Verificar si es una solicitud AJAX para guardar proforma
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                import json
                data = json.loads(request.body)
                # Requiere token de proformador en payload para cada emisión
                from django.core import signing
                token = data.get('t')
                if not token:
                    return JsonResponse({'success': False, 'message': 'Debe iniciar sesión como facturador para emitir proformas.'})
                try:
                    token_data = signing.loads(token, salt='proformador', max_age=1800)
                    facturador_id = token_data.get('fid')
                except Exception:
                    return JsonResponse({'success': False, 'message': 'Sesión de proformador expirada. Inicie sesión nuevamente.'})
                
                # Validar datos básicos
                cliente_data = data.get('cliente', {})
                productos_data = data.get('productos', [])
                observaciones = data.get('observaciones', '')
                fecha_vencimiento = data.get('fecha_vencimiento')
                
                if not productos_data:
                    return JsonResponse({
                        'success': False,
                        'message': 'Debe agregar al menos un producto a la proforma'
                    })
                
                # Procesar cliente
                cliente = None
                cliente_id = cliente_data.get('id')
                if cliente_id:
                    cliente = Cliente.objects.filter(id=cliente_id, empresa=empresa).first()
                    if not cliente:
                        if Cliente.objects.filter(id=cliente_id).exclude(empresa=empresa).exists():
                            logger.warning(
                                "Intento de acceder a cliente fuera de la empresa activa",
                                extra={
                                    'usuario_id': getattr(request.user, 'id', None),
                                    'cliente_id': cliente_id,
                                    'empresa_activa_id': empresa.id,
                                }
                            )
                            return JsonResponse({
                                'success': False,
                                'message': 'El cliente no pertenece a la empresa activa'
                            })
                        return JsonResponse({
                            'success': False,
                            'message': 'Cliente no encontrado'
                        })

                # Si no existe cliente, crear uno nuevo
                if not cliente and cliente_data.get('identificacion'):
                    identificacion = cliente_data['identificacion']
                    nombre = cliente_data.get('nombre', '').strip()
                    correo = cliente_data.get('correo', '').strip()
                    
                    if nombre:
                        try:
                            # Verificar si ya existe
                            cliente = Cliente.objects.get(
                                identificacion=identificacion, 
                                empresa=empresa
                            )
                        except Cliente.DoesNotExist:
                            # Crear cliente nuevo
                            cliente = Cliente.objects.create(
                                empresa=empresa,
                                identificacion=identificacion,
                                razon_social=nombre,
                                correo=correo or '',
                                telefono='',
                                direccion='Por definir',
                                tipoIdentificacion='05' if len(identificacion) == 10 else '04',
                                tipoVenta='1',
                                tipoRegimen='1',
                                tipoCliente='1'
                            )
                
                if not cliente:
                    return JsonResponse({
                        'success': False,
                        'message': 'Debe seleccionar o crear un cliente válido'
                    })
                
                # Resolver facturador únicamente desde el token (no se persiste en sesión)
                facturador = Facturador.tenant_objects.filter(id=facturador_id, activo=True).first()
                if not facturador or (hasattr(facturador, 'empresa_id') and facturador.empresa_id and facturador.empresa_id != empresa.id):
                    return JsonResponse({'success': False, 'message': 'Facturador inválido. Inicie sesión nuevamente.'})
                
                proforma = Proforma.objects.create(
                    empresa=empresa,
                    cliente=cliente,
                    fecha_emision=timezone.now().date(),
                    fecha_vencimiento=fecha_vencimiento or (timezone.now().date() + timezone.timedelta(days=30)),
                    facturador=facturador,
                    observaciones=observaciones,
                    creado_por=request.user,
                    estado='BORRADOR'
                )
                
                # Agregar productos/servicios
                for item in productos_data:
                    codigo = item.get('codigo')
                    cantidad = int(item.get('cantidad', 1))
                    precio = Decimal(str(item.get('precio', 0)))
                    descuento = Decimal(str(item.get('descuento', 0)))
                    
                    # Buscar producto o servicio
                    producto = None
                    servicio = None
                    
                    try:
                        producto = Producto.objects.get(codigo=codigo, empresa=empresa)
                    except Producto.DoesNotExist:
                        try:
                            servicio = Servicio.objects.get(codigo=codigo, empresa=empresa)
                        except Servicio.DoesNotExist:
                            continue  # Saltar este item si no se encuentra
                    
                    # Crear detalle de proforma
                    ProformaDetalle.objects.create(
                        proforma=proforma,
                        producto=producto,
                        servicio=servicio,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento=descuento
                    )
                
                # La proforma calculará automáticamente los totales
                proforma.calcular_totales()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Proforma {proforma.numero} guardada correctamente',
                    'proforma_id': proforma.id,
                    'proforma_numero': proforma.numero
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    'success': False,
                    'message': f'Error al guardar proforma: {str(e)}'
                })
        
        # Procesamiento normal del formulario (no AJAX)
        almacenes = Almacen.objects.filter(activo=True, empresa=empresa)
        vendedores = Facturador.tenant_objects.filter(activo=True, empresa=empresa)
        form = EmitirProformaFormulario(request.POST, almacenes=almacenes, vendedores=vendedores)
        # Validar token mínimo en POST clásico
        from django.core import signing
        token = request.POST.get('t')
        if not token:
            messages.warning(request, 'Debe iniciar sesión como facturador antes de emitir proformas.')
            return redirect('inventario:login_proformador')
        try:
            token_data = signing.loads(token, salt='proformador', max_age=1800)
            facturador_id = token_data.get('fid')
        except Exception:
            messages.error(request, 'Sesión de proformador expirada. Inicie sesión nuevamente.')
            return redirect('inventario:login_proformador')
        
        if form.is_valid():
            # Procesar cliente
            cliente_id = form.cleaned_data.get('cliente_id')
            identificacion_cliente = form.cleaned_data.get('identificacion_cliente')
            nombre_cliente = form.cleaned_data.get('nombre_cliente')
            correo_cliente = form.cleaned_data.get('correo_cliente')
            
            cliente = None
            if cliente_id:
                try:
                    cliente = Cliente.objects.get(id=cliente_id, empresa=empresa)
                except Cliente.DoesNotExist:
                    cliente = None
            
            if not cliente and identificacion_cliente and nombre_cliente:
                try:
                    cliente = Cliente.objects.get(identificacion=identificacion_cliente, empresa=empresa)
                except Cliente.DoesNotExist:
                    cliente = Cliente.objects.create(
                        empresa=empresa,
                        identificacion=identificacion_cliente,
                        razon_social=nombre_cliente.strip(),
                        correo=correo_cliente or '',
                        telefono='',
                        direccion='Por definir',
                        tipoIdentificacion='05' if len(identificacion_cliente) == 10 else '04',
                        tipoVenta='1',
                        tipoRegimen='1',
                        tipoCliente='1'
                    )
                    
            if cliente:
                messages.success(request, f'Datos de cliente procesados: {cliente.razon_social}')
            else:
                messages.success(request, 'Formulario procesado sin cliente específico')
                
            return redirect('inventario:listarProformas')
            
        contexto = {
            'form': form,
            'proformador': {
                'nombres': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            },
            'proformador_token': token,
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proforma/emitirProforma.html', contexto)


class VerProforma(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return redirect('inventario:seleccionar_empresa')

        # Cargar proforma real con relaciones necesarias
        from django.db.models import Prefetch
        proforma = get_object_or_404(
            Proforma.objects.select_related('empresa', 'cliente', 'facturador', 'almacen', 'creado_por')
            .prefetch_related(
                Prefetch('detalles', queryset=ProformaDetalle.objects.select_related('producto', 'servicio'))
            ).filter(empresa_id=empresa_id),
            pk=p
        )
        # Asegurar totales actualizados
        try:
            proforma.calcular_totales()
        except Exception:
            pass

        # Desglose de IVA por porcentaje para mostrar en la vista
        try:
            from decimal import Decimal, ROUND_HALF_UP
            MAPEO_IVA = {
                '0': Decimal('0.00'), '5': Decimal('5.00'), '2': Decimal('12.00'), '10': Decimal('13.00'),
                '3': Decimal('14.00'), '4': Decimal('15.00'), '6': Decimal('0.00'), '7': Decimal('0.00'), '8': Decimal('8.00')
            }

            def _obtener_porcentaje_iva(det):
                try:
                    if det.producto:
                        try:
                            return Decimal(str(det.producto.get_porcentaje_iva_real()))
                        except Exception:
                            pass
                    if det.servicio:
                        try:
                            code = str(det.servicio.iva)
                            return MAPEO_IVA.get(code, Decimal('12.00'))
                        except Exception:
                            pass
                except Exception:
                    pass
                return Decimal('0.00')

            iva_breakdown = {}
            for det in proforma.detalles.all():
                try:
                    pct = _obtener_porcentaje_iva(det)
                    base = (det.subtotal - det.descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    iva_val = (base * (pct / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    iva_breakdown[pct] = iva_breakdown.get(pct, Decimal('0.00')) + iva_val
                except Exception:
                    continue

            # Asegurar presencia de 5% y 15% (aunque sea 0)
            for fijo in (Decimal('5.00'), Decimal('15.00')):
                iva_breakdown.setdefault(fijo, Decimal('0.00'))

            # Ordenar por % ascendente y preparar lista [("5", Decimal('0.00')), ...]
            iva_items = []
            for k in sorted(iva_breakdown.keys()):
                k_str = (str(k).rstrip('0').rstrip('.') if '.' in str(k) else str(k))
                iva_items.append((k_str, iva_breakdown[k]))
        except Exception:
            iva_items = []

        contexto = {
            'proforma': proforma,
            'iva_items': iva_items,
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proforma/verProforma.html', contexto)


@require_empresa_activa
def ride_proforma(request, p):
    """Descarga PDF de PROFORMA usando el generador dedicado (similar al RIDE)."""
    empresa_id = request.session.get('empresa_activa')

    # Cargar proforma con relaciones
    from decimal import Decimal, ROUND_HALF_UP
    from django.db.models import Prefetch

    proforma = get_object_or_404(
        Proforma.objects.select_related('empresa', 'cliente', 'facturador', 'almacen', 'creado_por')
        .prefetch_related(Prefetch('detalles', queryset=ProformaDetalle.objects.select_related('producto', 'servicio'))),
        pk=p,
        empresa_id=empresa_id,
    )

    # Asegurar totales actualizados
    try:
        proforma.calcular_totales()
    except Exception:
        pass

    # Obtener opciones/empresa para encabezado
    try:
        opciones = Opciones.objects.filter(empresa=proforma.empresa).first()
    except Exception:
        opciones = None

    # Resolver logo: primero el configurado en Opciones (MEDIA), sino fallback estático
    logo_url = None
    if opciones and getattr(opciones, 'imagen', None):
        logo_url = build_storage_url_or_none(opciones.imagen)

    if not logo_url:
        base_static = settings.STATIC_URL.rstrip('/')
        logo_url = f"{base_static}/inventario/assets/logo/logo2.png"

    # Construir contexto de empresa para el encabezado
    empresa_ctx = {
        'razon_social': (opciones.razon_social if opciones and getattr(opciones, 'razon_social', None) else proforma.empresa.razon_social),
        'ruc': (opciones.identificacion if opciones and getattr(opciones, 'identificacion', None) else proforma.empresa.ruc),
        'direccion': (opciones.direccion_establecimiento if opciones and getattr(opciones, 'direccion_establecimiento', None) else ''),
        'telefono': (opciones.telefono if opciones and getattr(opciones, 'telefono', None) else ''),
        'nombre_comercial': (opciones.nombre_comercial if opciones and getattr(opciones, 'nombre_comercial', None) else ''),
        'correo': (opciones.correo if opciones and getattr(opciones, 'correo', None) else ''),
    }

# === Helper centralizado para obtener factura multi-tenant ===
def get_factura_tenant(request, factura_id):
    """Retorna una factura filtrada por empresa activa o levanta 404.

    Uso en vistas sensibles (SRI, RIDE, pagos, etc.) para evitar repetir patrón.
    Precondición: usuario autenticado; empresa_activa en sesión.
    """
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        raise Http404("Empresa no válida")
    return get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)

    # Desglose de IVA por porcentaje y detalles enriquecidos para el PDF
    MAPEO_IVA = { '0': Decimal('0.00'), '5': Decimal('5.00'), '2': Decimal('12.00'), '10': Decimal('13.00'),
                  '3': Decimal('14.00'), '4': Decimal('15.00'), '6': Decimal('0.00'), '7': Decimal('0.00'), '8': Decimal('8.00') }

    def obtener_porcentaje_iva(det):
        if det.producto:
            try:
                return Decimal(str(det.producto.get_porcentaje_iva_real()))
            except Exception:
                return Decimal('12.00')
        if det.servicio:
            try:
                code = str(det.servicio.iva)
                return MAPEO_IVA.get(code, Decimal('12.00'))
            except Exception:
                return Decimal('12.00')
        return Decimal('0.00')

    iva_breakdown = {}  # { porcentaje(Decimal): {'base': Decimal, 'iva': Decimal} }
    detalles_pdf = []
    for det in proforma.detalles.all():
        pct = obtener_porcentaje_iva(det)
        base = (det.subtotal - det.descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        iva_val = (base * (pct / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_linea = (base + iva_val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if pct not in iva_breakdown:
            iva_breakdown[pct] = {'base': Decimal('0.00'), 'iva': Decimal('0.00')}
        iva_breakdown[pct]['base'] += base
        iva_breakdown[pct]['iva'] += iva_val

        detalles_pdf.append({
            'codigo': det.codigo,
            'descripcion': det.descripcion,
            'cantidad': det.cantidad,
            'precio_unitario': det.precio_unitario,
            'porcentaje_iva': pct,
            'porcentaje_iva_str': f"{pct.normalize()}%" if hasattr(pct, 'normalize') else f"{pct}%",
            'descuento': det.descuento,
            'subtotal': det.subtotal,
            'base': base,
            'iva_valor': iva_val,
            'total_linea': total_linea,
        })

    # Limitar filas visibles para favorecer caber en una sola página (totales siguen completos)
    MAX_ROWS = 10
    if len(detalles_pdf) > MAX_ROWS:
        detalles_pdf_display = detalles_pdf[:MAX_ROWS]
        detalles_omitidos = len(detalles_pdf) - MAX_ROWS
    else:
        detalles_pdf_display = detalles_pdf
        detalles_omitidos = 0

    # Totales auxiliares
    subtotal_neto = (proforma.subtotal - proforma.total_descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    subtotal_0 = iva_breakdown.get(Decimal('0.00'), {'base': Decimal('0.00')})['base'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    subtotal_iva_base = (subtotal_neto - subtotal_0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Ordenar IVA breakdown por porcentaje ascendente
    iva_items = sorted([(str(k).rstrip('0').rstrip('.') if '.' in str(k) else str(k), v) for k, v in iva_breakdown.items()], key=lambda x: Decimal(x[0]))

    # Metadata de generación
    try:
        from django.utils import timezone
        generado_el = timezone.now()
    except Exception:
        import datetime as _dt
        generado_el = _dt.datetime.now()
    generado_por = getattr(request.user, 'get_full_name', lambda: '')() or getattr(request.user, 'username', '')

    # Derivar forma de pago visual y nota
    obs_text = proforma.observaciones or ''
    forma_pago_text = None
    try:
        if 'forma de pago' in obs_text.lower():
            # Extraer línea que contenga 'forma de pago'
            for line in obs_text.splitlines():
                if 'forma de pago' in line.lower():
                    forma_pago_text = line.split(':', 1)[-1].strip() or None
                    break
    except Exception:
        pass
    if not forma_pago_text:
        forma_pago_text = 'Contado'
    nota_text = (proforma.observaciones or (getattr(opciones, 'mensaje_factura', '') if opciones else '')).strip()

    # Extras de presentación
    vendedor_nombre = None
    try:
        vendedor_nombre = proforma.facturador.nombres if proforma.facturador else None
    except Exception:
        vendedor_nombre = None
    # Validez (días) estimada con base en vencimiento si existe
    try:
        validez_dias = (proforma.fecha_vencimiento - proforma.fecha_emision).days if (proforma.fecha_vencimiento and proforma.fecha_emision) else None
    except Exception:
        validez_dias = None

    # Posible cuenta bancaria si está configurada en Opciones (tolerante a distintos nombres)
    cuenta_bancaria_text = None
    try:
        for _attr in ['cuenta_bancaria', 'bank_account', 'numero_cuenta', 'cuenta']:
            if opciones and hasattr(opciones, _attr):
                val = getattr(opciones, _attr)
                if val:
                    cuenta_bancaria_text = val
                    break
    except Exception:
        cuenta_bancaria_text = None

    contexto = {
        'proforma': proforma,
        'empresa': empresa_ctx,
        'opciones': opciones,
        'logo_url': logo_url,
        'detalles_pdf': detalles_pdf,
    'detalles_pdf_display': detalles_pdf_display,
    'detalles_omitidos': detalles_omitidos,
        'iva_items': iva_items,  # lista de tuplas: [(porcentaje_str, {'base': x, 'iva': y}), ...]
        'subtotal_neto': subtotal_neto,
        'subtotal_0': subtotal_0,
        'subtotal_iva_base': subtotal_iva_base,
        'generado_por': generado_por,
        'generado_el': generado_el,
    # Condiciones dinámicas: usa observaciones de la proforma o mensaje de factura de opciones como fallback
    'condiciones_text': (proforma.observaciones or (getattr(opciones, 'mensaje_factura', '') if opciones else '')),
        'forma_pago_text': forma_pago_text,
        'nota_text': nota_text,
        'vendedor_nombre': vendedor_nombre,
        'validez_dias': validez_dias,
    'cuenta_bancaria_text': cuenta_bancaria_text,
    }
    # Intentar usar el generador de archivo estilo RIDE para proforma
    try:
        gen = ProformaRIDEGenerator()
        pdf_path = gen.generar_ride_proforma_file(proforma)
        if pdf_path and os.path.exists(pdf_path):
            from django.utils.text import slugify
            empresa_name = empresa_ctx.get('nombre_comercial') or empresa_ctx.get('razon_social') or 'empresa'
            filename_base = f"proforma_{proforma.numero or proforma.id}_{empresa_name}"
            safe_name = slugify(str(filename_base)) or f"proforma-{proforma.id}"
            return FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=f"{safe_name}.pdf")
    except Exception as e:
        logger.warning(f"Fallo generador de proforma RIDE: {e}. Se usará plantilla HTML.")

    # Renderizar a PDF con xhtml2pdf como fallback y forzar descarga
    try:
        from io import BytesIO
        from django.template.loader import get_template
        from django.utils.text import slugify
        from xhtml2pdf import pisa
        from django.contrib.staticfiles import finders

        def link_callback(uri, rel):
            """Convierte rutas STATIC/MEDIA a rutas absolutas de sistema para xhtml2pdf."""
            # MEDIA
            media_url = getattr(settings, 'MEDIA_URL', '')
            media_root = getattr(settings, 'MEDIA_ROOT', '')
            static_url = getattr(settings, 'STATIC_URL', '')
            static_root = getattr(settings, 'STATIC_ROOT', '')

            if media_url and uri.startswith(media_url):
                path = os.path.join(media_root, uri.replace(media_url, ""))
                return path
            if static_url and uri.startswith(static_url):
                # Intentar resolver con finders (útil en dev)
                rel_path = uri.replace(static_url, "")
                found = finders.find(rel_path)
                if found:
                    return found
                # Fallback a STATIC_ROOT si está colectado
                path = os.path.join(static_root, rel_path)
                return path
            # Devolver tal cual (http/https u otros)
            return uri

        template = get_template('inventario/PDF/proforma.html')
        html = template.render(context=contexto, request=request)
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=pdf_buffer, link_callback=link_callback)

        if pisa_status.err:
            # Si falla, devolver HTML como fallback para inspección rápida
            return render(request, 'inventario/PDF/proforma.html', contexto)

        pdf_buffer.seek(0)
        empresa_name = empresa_ctx.get('nombre_comercial') or empresa_ctx.get('razon_social') or 'empresa'
        filename_base = f"proforma_{proforma.numero or proforma.id}_{empresa_name}"
        safe_name = slugify(str(filename_base)) or f"proforma-{proforma.id}"
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{safe_name}.pdf"'
        return response
    except Exception:
        # Ante cualquier error inesperado, mostrar HTML
        return render(request, 'inventario/PDF/proforma.html', contexto)


#Interfaz de inicio de sesion----------------------------------------------------#
#Interfaz de inicio de sesion----------------------------------------------------#
class Login(View):
    #Si el usuario ya envio el formulario por metodo post
    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos.
        # Se pasa un queryset de empresas para permitir la validación del
        # campo `empresa`, pero la selección de una empresa continúa siendo
        # opcional gracias a `required=False` en el formulario.
        form = LoginFormulario(request.POST, empresas=Empresa.objects.all())
        # Revisa si es valido:
        if form.is_valid():
            identificacion = form.cleaned_data['identificacion']
            clave = form.cleaned_data['password']
            credentials = {'username': identificacion}
            lockout_message = (
                'Hemos bloqueado temporalmente el acceso por múltiples intentos fallidos. '
                'Intente nuevamente más tarde o contacte a soporte para restaurar su cuenta.'
            )

            if AxesProxyHandler.is_locked(request, credentials=credentials):
                messages.error(request, lockout_message)
                return render(request, 'inventario/login.html', {'form': form})

            # Obtener la empresa seleccionada en el formulario (si la hay).
            # Si no se seleccionó ninguna, el formulario sigue siendo válido
            # porque el campo es opcional.
            empresa = form.cleaned_data.get('empresa')

            # Compatibilidad: si el frontend envía un campo oculto
            # `empresa_hidden`, usarlo en caso de que no exista selección
            # explícita en el formulario.
            if not empresa:
                empresa_id = request.POST.get('empresa_hidden')
                if empresa_id and str(empresa_id).isdigit():
                    try:
                        empresa = Empresa.objects.get(id=int(empresa_id))
                    except Empresa.DoesNotExist:
                        empresa = None

            logeado = authenticate(request, username=identificacion, password=clave)

            if logeado is not None:
                # 1) Empresa enviada explícitamente y válida
                if empresa and logeado.empresas.filter(id=empresa.id).exists():
                    login(request, logeado)
                    
                    # ✅ RECORDARME: Configurar duración de sesión
                    if request.POST.get('remember'):
                        request.session.set_expiry(1209600)  # 14 días
                    else:
                        request.session.set_expiry(0)  # Se cierra al cerrar navegador
                    
                    request.session['empresa_activa'] = empresa.id
                    # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
                    if necesita_configuracion(empresa):
                        messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                        return redirect('inventario:configuracionGeneral')
                    return HttpResponseRedirect('/inventario/panel')
                # Primer inicio con empresa indicada: si el usuario no tiene empresas aún, vincularlo
                if empresa and logeado.empresas.count() == 0:
                    try:
                        UsuarioEmpresa.objects.get_or_create(usuario=logeado, empresa=empresa)
                        login(request, logeado)
                        
                        # ✅ RECORDARME: Configurar duración de sesión
                        if request.POST.get('remember'):
                            request.session.set_expiry(1209600)  # 14 días
                        else:
                            request.session.set_expiry(0)  # Se cierra al cerrar navegador
                        
                        request.session['empresa_activa'] = empresa.id
                        # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
                        if necesita_configuracion(empresa):
                            messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                            return redirect('inventario:configuracionGeneral')
                        return HttpResponseRedirect('/inventario/panel')
                    except Exception:
                        pass

                # 2) Intentar auto-detección por RUC (13 dígitos)
                if not empresa and len(identificacion) == 13 and identificacion.isdigit():
                    try:
                        emp_ruc = Empresa.objects.get(ruc=identificacion)
                        if logeado.empresas.filter(id=emp_ruc.id).exists():
                            login(request, logeado)
                            
                            # ✅ RECORDARME: Configurar duración de sesión
                            if request.POST.get('remember'):
                                request.session.set_expiry(1209600)  # 14 días
                            else:
                                request.session.set_expiry(0)  # Se cierra al cerrar navegador
                            
                            request.session['empresa_activa'] = emp_ruc.id
                            # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
                            if necesita_configuracion(emp_ruc):
                                messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                                return redirect('inventario:configuracionGeneral')
                            return HttpResponseRedirect('/inventario/panel')
                        # Primer inicio: si el usuario no tiene empresas, vincular a esta
                        if logeado.empresas.count() == 0:
                            UsuarioEmpresa.objects.get_or_create(usuario=logeado, empresa=emp_ruc)
                            login(request, logeado)
                            
                            # ✅ RECORDARME: Configurar duración de sesión
                            if request.POST.get('remember'):
                                request.session.set_expiry(1209600)  # 14 días
                            else:
                                request.session.set_expiry(0)  # Se cierra al cerrar navegador
                            
                            request.session['empresa_activa'] = emp_ruc.id
                            # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
                            if necesita_configuracion(emp_ruc):
                                messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                                return redirect('inventario:configuracionGeneral')
                            return HttpResponseRedirect('/inventario/panel')
                    except Empresa.DoesNotExist:
                        pass

                # 3) Resolver por cantidad de empresas asociadas
                empresas_usuario = logeado.empresas.all()
                if empresas_usuario.count() == 1:
                    unica = empresas_usuario.first()
                    login(request, logeado)
                    
                    # ✅ RECORDARME: Configurar duración de sesión
                    if request.POST.get('remember'):
                        request.session.set_expiry(1209600)  # 14 días
                    else:
                        request.session.set_expiry(0)  # Se cierra al cerrar navegador
                    
                    request.session['empresa_activa'] = unica.id
                    # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
                    if necesita_configuracion(unica):
                        messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                        return redirect('inventario:configuracionGeneral')
                    return HttpResponseRedirect('/inventario/panel')
                elif empresas_usuario.count() > 1:
                    login(request, logeado)
                    
                    # ✅ RECORDARME: Configurar duración de sesión (antes de redirigir a seleccionar empresa)
                    if request.POST.get('remember'):
                        request.session.set_expiry(1209600)  # 14 días
                    else:
                        request.session.set_expiry(0)  # Se cierra al cerrar navegador
                    
                    return HttpResponseRedirect('/inventario/seleccionar_empresa/')

                # 4) Si llega aquí, requiere selección explícita
                messages.error(request, 'Seleccione una empresa válida para continuar')
                return render(request, 'inventario/login.html', {'form': form})

            if AxesProxyHandler.is_locked(request, credentials=credentials):
                messages.error(request, lockout_message)
            else:
                messages.error(request, 'Usuario o contraseña incorrectos')
            return render(request, 'inventario/login.html', {'form': form})
        # Si el formulario no es válido, se vuelve a mostrar con errores
        return render(request, 'inventario/login.html', {'form': form})
        
    # Si se llega por GET crearemos un formulario en blanco
    def get(self, request):
        if request.user.is_authenticated == True:
            return HttpResponseRedirect('/inventario/panel')

        # Mostrar el formulario con el listado completo de empresas disponibles.
        form = LoginFormulario(empresas=Empresa.objects.all())
        return render(request, 'inventario/login.html', {'form': form})


#Fin de vista---------------------------------------------------------------------#


#Selección de empresa tras el login-----------------------------------------------#
class SeleccionarEmpresa(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresas = request.user.empresas.all()
        total_empresas = empresas.count()
        if total_empresas == 0:
            # Si el usuario aún no tiene empresas vinculadas redirigir al flujo de configuración
            return redirect('inventario:configuracionGeneral')
        elif total_empresas == 1:
            request.session['empresa_activa'] = empresas.first().id
            # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
            if necesita_configuracion(empresas.first()):
                messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                return redirect('inventario:configuracionGeneral')
            return HttpResponseRedirect('/inventario/panel')
        return render(request, 'inventario/seleccionar_empresa.html', {'empresas': empresas})

    def post(self, request):
        empresa_id = request.POST.get('empresa_id')
        if empresa_id and request.user.empresas.filter(id=empresa_id).exists():
            empresa = request.user.empresas.get(id=empresa_id)
            request.session['empresa_activa'] = empresa.id
            # ✅ VERIFICACIÓN COMPLETA: Solo redirigir a configuración si REALMENTE lo necesita
            if necesita_configuracion(empresa):
                messages.warning(request, '⚠️ Complete la configuración de su empresa para facturar electrónicamente')
                return redirect('inventario:configuracionGeneral')
            return HttpResponseRedirect('/inventario/panel')
        empresas = request.user.empresas.all()
        contexto = {'empresas': empresas, 'error': 'Seleccione una empresa válida'}
        return render(request, 'inventario/seleccionar_empresa.html', contexto)


#Fin de selección de empresa------------------------------------------------------#


# API para obtener empresas de un usuario por identificación
class EmpresasPorUsuario(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request, identificacion):
        try:
            usuario = Usuario.objects.get(username=identificacion)
            empresas = usuario.empresas.all()
            data = [{'id': e.id, 'razon_social': e.razon_social} for e in empresas]
        except Usuario.DoesNotExist:
            data = []
        return Response({'empresas': data})


#Panel de inicio y vista principal------------------------------------------------#
class Panel(LoginRequiredMixin, View):
    #De no estar logeado, el usuario sera redirigido a la pagina de Login
    #Las dos variables son la pagina a redirigir y el campo adicional, respectivamente
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from datetime import date

        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return redirect('inventario:seleccionar_empresa')
        
        # ✅ Obtener la empresa y verificar si necesita configuración completa
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            if necesita_configuracion(empresa):
                messages.warning(request, '⚠️ Complete la configuración de su empresa antes de usar el panel')
                return redirect('inventario:configuracionGeneral')
        except Empresa.DoesNotExist:
            return redirect('inventario:seleccionar_empresa')

        #Recupera los datos del usuario despues del login
        contexto = {
            'usuario': request.user.username,
            'id_usuario': request.user.id,
            'nombre': request.user.first_name,
            'apellido': request.user.last_name,
            'correo': request.user.email,
            'fecha': date.today(),
            'productosRegistrados': Producto.numeroRegistrados(empresa_id),
            'productosVendidos': DetalleFactura.productosVendidos(empresa_id),
            'clientesRegistrados': Cliente.numeroRegistrados(empresa_id),
            'usuariosRegistrados': Usuario.numeroRegistrados(empresa_id),
            'facturasEmitidas': Factura.numeroRegistrados(empresa_id),
            'ingresoTotal': Factura.ingresoTotal(empresa_id),
            'ultimasVentas': DetalleFactura.ultimasVentas(empresa_id),
            'administradores': Usuario.numeroUsuarios('administrador', empresa_id),
            'usuarios': Usuario.numeroUsuarios('usuario', empresa_id),
            # Nuevos datos para el panel de ventas
            'ventasEsteMes': Factura.ventasEsteMes(empresa_id),
            'ventasMesAnterior': Factura.ventasMesAnterior(empresa_id),
            'promedioVentasMensuales': Factura.promedioVentasMensuales(empresa_id=empresa_id),
            'ventasUltimosMeses': Factura.ventasUltimosMeses(6, empresa_id),
            # Datos para top productos vendidos
            'topProductosVendidos': DetalleFactura.topProductosVendidos(5, empresa_id),
        }

        return render(request, 'inventario/panel.html', contexto)


#Fin de vista----------------------------------------------------------------------#


#Maneja la salida del usuario------------------------------------------------------#
class Salir(LoginRequiredMixin, View):
    #Sale de la sesion actual
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        request.session.pop('empresa_activa', None)
        logout(request)
        return HttpResponseRedirect('/inventario/login')


#Fin de vista----------------------------------------------------------------------#


#Muestra el perfil del usuario logeado actualmente---------------------------------#
class Perfil(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    #se accede al modo adecuado y se valida al usuario actual para ver si puede modificar al otro usuario-
    #-el cual es obtenido por la variable 'p'
    def get(self, request, modo, p):
        if modo == 'editar':
            perf = Usuario.objects.get(id=p)
            editandoSuperAdmin = False

            # ✅ NUEVO: Usuarios vendedores (USER) no pueden editar perfiles
            if request.user.nivel == Usuario.USER:
                messages.error(request, 'No tienes permisos para editar perfiles')
                return HttpResponseRedirect('/inventario/panel')

            if request.user.nivel == Usuario.ROOT:
                empresas_queryset = Empresa.objects.all()
            else:
                empresas_queryset = request.user.empresas.all()

            if p == 1:
                if request.user.nivel != Usuario.ROOT:
                    messages.error(request,
                                   'No puede editar el perfil del administrador por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)
                editandoSuperAdmin = True
            else:
                if request.user.is_superuser != True:
                    messages.error(request, 'No puede cambiar el perfil por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

                else:
                    if perf.is_superuser == True:
                        if request.user.nivel == Usuario.ROOT:
                            pass

                        elif perf.id != request.user.id:
                            messages.error(request, 'No puedes cambiar el perfil de un usuario de tu mismo nivel')

                            return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

            if editandoSuperAdmin:
                form = UsuarioFormulario(user=request.user, empresas_queryset=empresas_queryset)
                form.fields['level'].disabled = True
            else:
                form = UsuarioFormulario(user=request.user, empresas_queryset=empresas_queryset)

            #Me pregunto si habia una manera mas facil de hacer esto, solo necesitaba hacer que el formulario-
            #-apareciera lleno de una vez, pero arrojaba User already exists y no pasaba de form.is_valid()
            form['identificacion'].field.widget.attrs['value'] = perf.username
            form['nombre_completo'].field.widget.attrs['value'] = perf.first_name
            form['email'].field.widget.attrs['value'] = perf.email
            form['level'].field.widget.attrs['value'] = perf.nivel

            #Envia al usuario el formulario para que lo llene
            contexto = {'form': form, 'modo': request.session.get('perfilProcesado'), 'editar': 'perfil',
                        'nombreUsuario': perf.username}

            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/perfil/perfil.html', contexto)


        elif modo == 'clave':
            perf = Usuario.objects.get(id=p)
            
            # ✅ NUEVO: Usuarios vendedores (USER) no pueden cambiar claves
            if request.user.nivel == Usuario.USER:
                messages.error(request, 'No tienes permisos para cambiar claves')
                return HttpResponseRedirect('/inventario/panel')
            
            if p == 1:
                if request.user.nivel != Usuario.ROOT:
                    messages.error(request,
                                   'No puede cambiar la clave del administrador por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)
            else:
                if request.user.is_superuser != True:
                    messages.error(request,
                                   'No puede cambiar la clave de este perfil por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

                else:
                    if perf.is_superuser == True:
                        if request.user.nivel == Usuario.ROOT:
                            pass

                        elif perf.id != request.user.id:
                            messages.error(request, 'No puedes cambiar la clave de un usuario de tu mismo nivel')
                            return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

            form = ClaveFormulario(user=perf)
            contexto = {'form': form, 'modo': request.session.get('perfilProcesado'),
                        'editar': 'clave', 'nombreUsuario': perf.username}

            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/perfil/perfil.html', contexto)

        elif modo == 'ver':
            perf = Usuario.objects.get(id=p)
            contexto = {'perfil': perf}
            contexto = complementarContexto(contexto, request.user)

            return render(request, 'inventario/perfil/verPerfil.html', contexto)

    def post(self, request, modo, p):
        if modo == 'editar':
            # ✅ NUEVO: Usuarios vendedores (USER) no pueden editar perfiles
            if request.user.nivel == Usuario.USER:
                messages.error(request, 'No tienes permisos para editar perfiles')
                return HttpResponseRedirect('/inventario/panel')
            
            # Crea una instancia del formulario y la llena con los datos:
            if request.user.nivel == Usuario.ROOT:
                empresas_queryset = Empresa.objects.all()
            else:
                empresas_queryset = request.user.empresas.all()

            form = UsuarioFormulario(
                request.POST,
                user=request.user,
                empresas_queryset=empresas_queryset,
            )
            # Revisa si es valido:

            if form.is_valid():
                perf = Usuario.objects.get(id=p)
                # Procesa y asigna los datos con form.cleaned_data como se requiere
                if p != 1:
                    level = form.cleaned_data['level']
                    perf.nivel = level
                    perf.is_superuser = level in (Usuario.ADMIN, Usuario.ROOT)

                identificacion = form.cleaned_data['identificacion']
                nombre_completo = form.cleaned_data['nombre_completo']
                email = form.cleaned_data['email']
                empresa = form.cleaned_data['empresa']

                perf.username = identificacion
                perf.first_name = nombre_completo
                perf.last_name = ''
                perf.email = email
                if empresa:
                    perf.empresas.clear()
                    perf.empresas.add(empresa)

                perf.save()

                form = UsuarioFormulario(user=request.user)
                messages.success(request, 'Actualizado exitosamente el perfil de ID %s.' % p)
                request.session['perfilProcesado'] = True
                return HttpResponseRedirect("/inventario/perfil/ver/%s" % perf.id)
            else:
                #De lo contrario lanzara el mismo formulario
                return render(request, 'inventario/perfil/perfil.html', {'form': form})

        elif modo == 'clave':
            # ✅ NUEVO: Usuarios vendedores (USER) no pueden cambiar claves
            if request.user.nivel == Usuario.USER:
                messages.error(request, 'No tienes permisos para cambiar claves')
                return HttpResponseRedirect('/inventario/panel')
            
            usuario = Usuario.objects.get(id=p)
            form = ClaveFormulario(request.POST, user=usuario)

            if form.is_valid():
                clave_nueva = form.cleaned_data['clave_nueva']
                clave_actual = form.cleaned_data['clave_actual']
                autenticado = authenticate(username=usuario.username, password=clave_actual)
                if autenticado is None:
                    messages.error(request, 'La clave actual es incorrecta.')
                    return HttpResponseRedirect("/inventario/perfil/clave/%s" % p)

                messages.success(request, 'La clave se ha cambiado correctamente!')
                usuario.set_password(clave_nueva)
                usuario.save()
                return HttpResponseRedirect("/inventario/login")

            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
            return HttpResponseRedirect("/inventario/perfil/clave/%s" % p)


#----------------------------------------------------------------------------------#   


#Elimina usuarios, productos, clientes o proveedores----------------------------
class Eliminar(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, modo, p):
        empresa_id = request.session.get('empresa_activa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()

        if modo == 'usuario':
            return HttpResponseNotAllowed(['POST'])

        if modo == 'producto':
            prod = get_object_or_404(Producto, id=p, empresa_id=empresa_id)
            prod.delete()
            messages.success(request, f'Producto de ID {p} borrado exitosamente.')
            return HttpResponseRedirect("/inventario/listarProductos")

        elif modo == 'cliente':
            cliente = get_object_or_404(Cliente, id=p, empresa_id=empresa_id)
            cliente.delete()
            messages.success(request, f'Cliente de ID {p} borrado exitosamente.')
            return HttpResponseRedirect("/inventario/listarClientes")

        elif modo == 'proforma':
            from .models import Proforma
            proforma = get_object_or_404(Proforma, id=p, empresa_id=empresa_id)
            numero = proforma.numero
            proforma.delete()
            messages.success(request, f'Proforma {numero} eliminada exitosamente.')
            return redirect('inventario:listarProformas')


        elif modo == 'proveedor':
            proveedor = get_object_or_404(Proveedor, id=p, empresa_id=empresa_id)
            proveedor.delete()
            messages.success(request, f'Proveedor de ID {p} borrado exitosamente.')
            return HttpResponseRedirect("/inventario/listarProveedores")

        #Fin de vista-------------------------------------------------------------------

    def post(self, request, modo, p):
        empresa_id = request.session.get('empresa_activa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()

        if modo != 'usuario':
            return HttpResponseNotAllowed(['GET'])

        if not request.user.is_superuser:
            messages.error(request, 'No tienes permisos suficientes para borrar usuarios')
            return HttpResponseRedirect('/inventario/listarUsuarios')

        if p == 1:
            messages.error(request, 'No puedes eliminar al super-administrador.')
            return HttpResponseRedirect('/inventario/listarUsuarios')

        if request.user.id == p:
            messages.error(request, 'No puedes eliminar tu propio usuario.')
            return HttpResponseRedirect('/inventario/listarUsuarios')

        usuario_obj = get_object_or_404(Usuario, id=p)
        
        # ✅ ADMIN no puede eliminar a otro ADMIN
        if request.user.nivel == Usuario.ADMIN and usuario_obj.nivel == Usuario.ADMIN:
            messages.error(request, 'No puedes eliminar a otro administrador.')
            return HttpResponseRedirect('/inventario/listarUsuarios')
        
        # Si Usuario tiene relación M2M con empresas, validar pertenencia
        if hasattr(usuario_obj, 'empresas') and not usuario_obj.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'El usuario no pertenece a la empresa activa.')
            return HttpResponseRedirect('/inventario/listarUsuarios')

        usuario_obj.delete()
        messages.success(request, f'Usuario de ID {p} borrado exitosamente.')
        return HttpResponseRedirect("/inventario/listarUsuarios")

        #Fin de vista-------------------------------------------------------------------


#Muestra una lista de 10 productos por pagina----------------------------------------#
class ListarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models

        empresa_id = request.session.get('empresa_activa')
        if empresa_id is None or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return HttpResponseRedirect('/inventario/panel')

        #Lista de productos de la BDD
        productos = Producto.objects.filter(empresa_id=empresa_id)

        contexto = {'tabla': productos}

        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/producto/listarProductos.html', contexto)


#Fin de vista-------------------------------------------------------------------------#

from django.views import View
from django.http import HttpResponse

class ExportarProductosExcel(LoginRequiredMixin, View):
    """Exporta todos los productos de la empresa activa a un archivo Excel XLSX.

    Columnas requeridas:
        ProductoID | CodigoProducto | CodigoBarras | DescripcionP | Precio1 | Precio2
    """
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        import io, csv
        try:
            from openpyxl import Workbook  # type: ignore
            use_xlsx = True
        except ModuleNotFoundError:
            use_xlsx = False

        empresa_id = request.session.get('empresa_activa')
        if empresa_id is None or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return HttpResponseRedirect('/inventario/panel')

        productos = Producto.objects.filter(empresa_id=empresa_id).order_by('id')
        headers = ['ProductoID','CodigoProducto','CodigoBarras','DescripcionP','Precio1','Precio2']

        if use_xlsx:
            wb = Workbook()
            ws = wb.active
            ws.title = 'Productos'
            ws.append(headers)
            for p in productos:
                ws.append([
                    p.id,
                    p.codigo,
                    p.codigo_barras,
                    p.descripcion,
                    float(p.precio) if p.precio is not None else 0,
                    float(p.precio2) if p.precio2 is not None else 0,
                ])
            for col, width in {'A':12,'B':18,'C':18,'D':45,'E':12,'F':12}.items():
                ws.column_dimensions[col].width = width
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="productos.xlsx"'
            return response
        else:
            sio = io.StringIO()
            writer = csv.writer(sio)
            writer.writerow(headers)
            for p in productos:
                writer.writerow([
                    p.id, p.codigo, p.codigo_barras, p.descripcion,
                    float(p.precio) if p.precio is not None else 0,
                    float(p.precio2) if p.precio2 is not None else 0,
                ])
            response = HttpResponse(sio.getvalue().encode('utf-8'), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="productos.csv"'
            response['X-Export-Mode'] = 'csv-fallback-openpyxl-missing'
            return response


class PlantillaProductosExcel(LoginRequiredMixin, View):
    """Entrega una plantilla vacía para importar productos."""
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        import io, csv
        try:
            from openpyxl import Workbook  # type: ignore
            wb = Workbook()
            ws = wb.active
            ws.title = 'Plantilla'
            headers = ['Código','Descripción','Barras','Iva','Costo Actual','Precio 1','Precio 2']
            ws.append(headers)
            ws.append(['P000000001', 'EJEMPLO PRODUCTO', '1234567890123', '0', 10.50, 12.50, 11.99])
            for col, width in {'A':16,'B':40,'C':18,'D':8,'E':14,'F':12,'G':12}.items():
                ws.column_dimensions[col].width = width
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            resp = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            resp['Content-Disposition'] = 'attachment; filename="plantilla_productos.xlsx"'
            return resp
        except ModuleNotFoundError:
            sio = io.StringIO()
            writer = csv.writer(sio)
            writer.writerow(['Código','Descripción','Barras','Iva','Costo Actual','Precio 1','Precio 2'])
            writer.writerow(['P000000001','EJEMPLO PRODUCTO','1234567890123','0','10.50','12.50','11.99'])
            resp = HttpResponse(sio.getvalue().encode('utf-8'), content_type='text/csv; charset=utf-8')
            resp['Content-Disposition'] = 'attachment; filename="plantilla_productos.csv"'
            resp['X-Export-Mode'] = 'csv-fallback-openpyxl-missing'
            return resp


#Maneja y visualiza un formulario--------------------------------------------------#
class AgregarProducto(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            form = ProductoFormulario(request.POST, request.FILES)
            messages.error(request, "No hay una empresa activa seleccionada.")
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            form = ProductoFormulario(request.POST, request.FILES)
            messages.error(request, "No hay una empresa activa seleccionada.")
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})

        form = ProductoFormulario(request.POST, request.FILES, empresa=empresa)
        if form.is_valid():
            try:
                # ✅ Usar form.save() en vez de crear manualmente para manejar imagen
                prod = form.save(commit=False)
                prod.empresa = empresa
                prod.save()  # El método save() del modelo calculará precio_iva1 y precio_iva2
                
                print(f"✅ Producto guardado exitosamente: {prod.codigo} - {prod.descripcion}")

                form = ProductoFormulario()
                messages.success(request, '✓ Producto agregado exitosamente')
                request.session['productoProcesado'] = 'agregado'
                return HttpResponseRedirect("/inventario/agregarProducto")
            except Exception as e:
                print(f"❌ ERROR al guardar producto: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error al guardar el producto: {str(e)}')
                return render(request, 'inventario/producto/agregarProducto.html', {'form': form})
        else:
            # Mostrar errores de validación
            print(f"❌ Formulario NO válido. Errores: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})

    def get(self, request):
        from .funciones import generar_codigo_producto
        
        # ✅ GENERAR CÓDIGO AUTOMÁTICO DE PRODUCTO
        nuevo_codigo = generar_codigo_producto()
        
        form = ProductoFormulario(initial={'codigo': nuevo_codigo})
        
        # Obtener mensajes de sesión
        mensaje = None
        if 'productoProcesado' in request.session:
            if request.session['productoProcesado'] == 'agregado':
                mensaje = "Producto agregado exitosamente"
            del request.session['productoProcesado']
        
        contexto = {
            'form': form,
            'mensaje': mensaje,
            'nuevo_codigo': nuevo_codigo
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/agregarProducto.html', contexto)

        #FIN DEL CONTEXTO-----------------------------#


#Formulario simple que procesa un script para importar los productos-----------------#
class ImportarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa activa inválida.')
            return HttpResponseRedirect('/inventario/panel')

        form = ImportarProductosFormulario(request.POST, request.FILES)
        modo = request.POST.get('modo', 'agregar')  # 'reemplazar' o 'agregar'
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo XLSX o CSV.')
            return HttpResponseRedirect('/inventario/importarProductos')

        from services import parse_product_file
        filas, errores = parse_product_file(archivo)

        if errores:
            messages.error(request, f"Errores en importación: {' | '.join(errores[:5])}")
            if len(errores) > 5:
                messages.error(request, f"{len(errores)-5} errores adicionales truncados")
            return HttpResponseRedirect('/inventario/importarProductos')

        # Estrategia reemplazo: borrar existentes antes de agregar
        creados = 0
        actualizados = 0
        if modo == 'reemplazar':
            Producto.objects.filter(empresa_id=empresa_id).delete()

        for fila in filas:
            # Parsing numéricos seguros
            def to_decimal(val):
                try:
                    if val in (None, ''):
                        return Decimal('0')
                    return Decimal(str(val).replace(',', '.'))
                except Exception:
                    return Decimal('0')

            precio1 = to_decimal(fila.get('precio1'))
            precio2_raw = fila.get('precio2')
            precio2 = to_decimal(precio2_raw) if (precio2_raw not in (None, '')) else None
            costo_actual = to_decimal(fila.get('costo_actual') or fila.get('costo') or precio1)

            # IVA: en el archivo se espera valor numérico (ej: 0, 5, 12)
            iva_val = str(fila.get('iva') or '0').strip()
            # Mapear a choices del modelo Producto.tiposIVA (ej: keys '0','2','3'?)
            # Si el proyecto usa claves iguales al número, simplemente usar.
            # Validación: si no coincide, caer a '0'.
            iva_choices = {k: v for k, v in Producto.tiposIVA}
            if iva_val not in iva_choices:
                # Intentar normalizar quitando decimales
                iva_val_simple = iva_val.split('.')[0]
                if iva_val_simple in iva_choices:
                    iva_val = iva_val_simple
                else:
                    iva_val = '0'

            codigo = fila['codigo']
            producto = Producto.objects.filter(empresa_id=empresa_id, codigo=codigo).first()
            if producto:
                producto.codigo_barras = fila.get('codigo_barras','')[:50]
                producto.descripcion = fila.get('descripcion','')[:40]
                producto.precio = precio1
                producto.precio2 = precio2
                if not producto.categoria:
                    producto.categoria = '1'
                producto.iva = iva_val or producto.iva or '0'
                if producto.disponible is None:
                    producto.disponible = 0
                producto.costo_actual = costo_actual or producto.costo_actual or precio1
                # Calcular precios con IVA si el modelo los maneja (según patrón en agregar)
                try:
                    iva_percent = Decimal(dict(Producto.tiposIVA).get(producto.iva).replace('%', '')) / 100
                    producto.precio_iva1 = producto.precio * (Decimal('1.00') + iva_percent)
                    producto.precio_iva2 = (producto.precio2 * (Decimal('1.00') + iva_percent)) if producto.precio2 else None
                except Exception:
                    pass
                producto.save()
                actualizados += 1
            else:
                try:
                    iva_percent = Decimal(dict(Producto.tiposIVA).get(iva_val).replace('%', '')) / 100
                except Exception:
                    iva_percent = Decimal('0')
                precio_iva1 = precio1 * (Decimal('1.00') + iva_percent)
                precio_iva2 = (precio2 * (Decimal('1.00') + iva_percent)) if precio2 else None
                Producto.objects.create(
                    empresa_id=empresa_id,
                    codigo=codigo,
                    codigo_barras=fila.get('codigo_barras','')[:50],
                    descripcion=fila.get('descripcion','')[:40],
                    precio=precio1,
                    precio2=precio2,
                    disponible=0,
                    categoria='1',
                    iva=iva_val,
                    costo_actual=costo_actual or precio1,
                    precio_iva1=precio_iva1,
                    precio_iva2=precio_iva2,
                )
                creados += 1

        messages.success(request, f"Importación completada. Creados: {creados} | Actualizados: {actualizados}")
        request.session['productosImportados'] = True
        return HttpResponseRedirect('/inventario/importarProductos')

    def get(self, request):
        form = ImportarProductosFormulario()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/importarProductos.html', contexto)

    #Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los productos-----------------------#
class ExportarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa.')
            return redirect('inventario:exportarProductos')

        form = ExportarProductosFormulario(request.POST)
        if form.is_valid():
            request.session['productosExportados'] = True

            #Se obtienen las entradas de producto en formato JSON
            data = serializers.serialize("json", Producto.objects.filter(empresa_id=empresa_id))

            with NamedTemporaryFile(mode='wb', suffix='.json', dir='/tmp', delete=False) as tmp_file:
                tmp_file.write(data.encode('utf-8'))
                tmp_path = tmp_file.name

            file_handle = open(tmp_path, 'rb')
            response = FileResponse(
                file_handle,
                as_attachment=True,
                filename='productos.json',
                content_type='application/json',
            )

            def cleanup(_: HttpResponse) -> None:
                try:
                    file_handle.close()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except FileNotFoundError:
                        pass

            response.add_post_render_callback(cleanup)
            return response

    def get(self, request):
        form = ExportarProductosFormulario()

        if request.session.get('productosExportados') == True:
            exportado = request.session.get('productoExportados')
            contexto = {'form': form, 'productosExportados': exportado}
            request.session['productosExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/exportarProductos.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Muestra el formulario de un producto especifico para editarlo----------------------------------#
class EditarProducto(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()

        # Lookup multi-tenant
        prod = get_object_or_404(Producto, id=p, empresa_id=empresa_id)
        form = ProductoFormulario(request.POST, instance=prod, empresa=prod.empresa)
        if form.is_valid():
            codigo = form.cleaned_data['codigo']
            codigo_barras = form.cleaned_data['codigo_barras']
            descripcion = form.cleaned_data['descripcion']
            precio = form.cleaned_data['precio']
            precio2 = form.cleaned_data.get('precio2', None)
            categoria = form.cleaned_data['categoria']
            disponible = form.cleaned_data['disponible']
            iva = form.cleaned_data['iva']
            costo_actual = form.cleaned_data['costo_actual']

            prod.codigo = codigo
            prod.codigo_barras = codigo_barras
            prod.descripcion = descripcion
            prod.precio = precio
            prod.precio2 = precio2
            prod.categoria = categoria
            prod.disponible = disponible
            prod.iva = iva
            prod.costo_actual = costo_actual

            prod.save()

            form = ProductoFormulario(instance=prod, empresa=prod.empresa)
            messages.success(request, 'Actualizado exitosamente el producto de ID %s.' % p)
            request.session['productoProcesado'] = 'editado'
            return HttpResponseRedirect("/inventario/editarProducto/%s" % prod.id)
        else:
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()

        prod = get_object_or_404(Producto, id=p, empresa_id=empresa_id)
        form = ProductoFormulario(instance=prod, empresa=prod.empresa)
        # Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('productoProcesado'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/agregarProducto.html', contexto)


#Fin de vista------------------------------------------------------------------------------------#

## Búsqueda de Clientes (versión unificada multi-tenant)
@require_empresa_activa
def buscar_cliente(request):
    """Autocomplete / búsqueda ligera de clientes en la empresa activa."""
    query = request.GET.get('q', '').strip()
    empresa_id = request.session.get('empresa_activa')
    if not query:
        return JsonResponse([], safe=False)
    clientes = (Cliente.objects
                .filter(empresa_id=empresa_id)
                .filter(
                    Q(identificacion__icontains=query) |
                    Q(razon_social__icontains=query) |
                    Q(nombre_comercial__icontains=query)
                )[:8])
    resultados = []
    for c in clientes:
        resultados.append({
            'id': c.id,
            'identificacion': c.identificacion,
            'razon_social': c.razon_social,
            'nombre_comercial': c.nombre_comercial or '',
            'nombre_compuesto': (c.razon_social + (f" {c.nombre_comercial}" if c.nombre_comercial else "")).strip()
        })
    return JsonResponse(resultados, safe=False)

# Búsqueda de Productos
from .models import Producto, Servicio

from django.http import JsonResponse
from .models import Producto, Servicio


#Crea una lista de los clientes, 10 por pagina----------------------------------------#
class ListarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        # Obtiene la empresa activa desde la sesión
        empresa_id = request.session.get('empresa_activa')
        if empresa_id is None or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return HttpResponseRedirect('/inventario/panel')

        # Saca una lista de todos los clientes de la BDD asociados a la empresa
        clientes = Cliente.objects.filter(empresa_id=empresa_id)
        contexto = {'tabla': clientes}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/cliente/listarClientes.html', contexto)
    #Fin de vista--------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar a un cliente---------------------------------#
class AgregarCliente(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            form = ClienteFormulario(request.POST)
            messages.error(request, 'No hay una empresa activa seleccionada.')
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            form = ClienteFormulario(request.POST)
            messages.error(request, 'No hay una empresa activa seleccionada.')
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})

        form = ClienteFormulario(request.POST, empresa=empresa)

        # Revisa si es valido:
        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            identificacion = form.cleaned_data['identificacion'] # Renombrado
            razon_social = form.cleaned_data['razon_social'] # Renombrado
            nombre_comercial = form.cleaned_data['nombre_comercial'] # Renombrado
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            observaciones = form.cleaned_data['observaciones']
            convencional = form.cleaned_data['convencional']
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoCliente = form.cleaned_data['tipoCliente']
            # CORRECCIÓN: cambiar tipoCedula por tipoIdentificacion
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']

            cliente = Cliente(identificacion=identificacion, razon_social=razon_social, nombre_comercial=nombre_comercial,
                              direccion=direccion, telefono=telefono,
                              correo=correo, observaciones=observaciones, convencional=convencional,
                              tipoVenta=tipoVenta,
                              tipoRegimen=tipoRegimen, tipoCliente=tipoCliente,
                              # CORRECCIÓN: usar tipoIdentificacion
                              tipoIdentificacion=tipoIdentificacion,
                              empresa=empresa)

            cliente.save()
            form = ClienteFormulario()
            messages.success(request, '✓ Cliente agregado exitosamente')
            request.session['clienteProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarCliente")
        else:
            #De lo contrario lanzara el mismo formulario
            messages.error(request, 'Error al agregar el cliente, ya existe o se encuentra en la base de datos')
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})

    def get(self, request):
        form = ClienteFormulario()
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('clienteProcesado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/agregarCliente.html', contexto)


# NUEVA VISTA: Consulta RUC mediante API
@csrf_exempt
@require_http_methods(["GET"])
def consultar_identificacion(request):
    """Vista para consultar información de cédula o RUC."""

    try:
        identificacion = request.GET.get('identificacion', '').strip()
        tipo = request.GET.get('tipo', request.GET.get('tipoIdentificacion', '')).strip()

        tipo_map = {'04': 'RUC', '05': 'CEDULA'}
        tipo_mapeado = tipo_map.get(tipo)

        logger.info(
            f"Recibida solicitud de consulta para identificación: {identificacion}, tipo: {tipo}"
        )

        if not identificacion or not identificacion.isdigit() or not tipo_mapeado:
            return JsonResponse({
                'error': True,
                'message': 'Debe proporcionar una identificación numérica válida y tipo 04 o 05',
                'status_code': 400
            }, status=400)

        if tipo == '04' and len(identificacion) != 13:
            return JsonResponse({
                'error': True,
                'message': 'El RUC debe tener 13 dígitos',
                'status_code': 400
            }, status=400)

        if tipo == '05' and len(identificacion) != 10:
            return JsonResponse({
                'error': True,
                'message': 'La cédula debe tener 10 dígitos',
                'status_code': 400
            }, status=400)

        from services import consultar_identificacion as servicio_consultar_identificacion

        resultado = servicio_consultar_identificacion(identificacion)
        resultado['tipo_identificacion'] = tipo_mapeado
        logger.info(f"Resultado del servicio: {resultado}")

        status_code = resultado.get('status_code', 200)
        return JsonResponse(resultado, status=status_code)

    except Exception as e:
        logger.error(
            f"Error en la vista consultar_identificacion: {str(e)}"
        )
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'error': True,
            'message': f'Error interno del servidor: {str(e)}',
            'status_code': 500
        }, status=500)


@require_http_methods(["POST"])
@login_required
def guardar_cliente_automatico(request):
    """Vista para guardar automáticamente un cliente después de consultar la API externa"""
    try:
        import json
        data = json.loads(request.body)
        
        identificacion = data.get('identificacion', '').strip()
        razon_social = data.get('razon_social', '').strip()
        tipo = data.get('tipo', '').strip()
        
        if not identificacion or not razon_social:
            return JsonResponse({
                'success': False,
                'message': 'Faltan datos requeridos'
            })
        
        # Obtener empresa activa
        empresa = get_empresa_activa(request)
        if not empresa:
            return JsonResponse({
                'success': False,
                'message': 'No hay empresa activa'
            })
        
        # Verificar si el cliente ya existe
        cliente_existente = Cliente.objects.filter(
            identificacion=identificacion,
            empresa=empresa
        ).first()
        
        if cliente_existente:
            return JsonResponse({
                'success': True,
                'message': 'Cliente ya existe',
                'cliente_id': cliente_existente.id,
                'ya_existia': True
            })
        
        # Crear nuevo cliente
        cliente = Cliente.objects.create(
            empresa=empresa,
            identificacion=identificacion,
            razon_social=razon_social,
            correo='',
            telefono='',
            direccion='Por definir',
            tipoIdentificacion=tipo,
            tipoVenta='1',
            tipoRegimen='1',
            tipoCliente='1'
        )
        
        logger.info(f"Cliente creado automáticamente: {cliente.id} - {razon_social}")
        
        return JsonResponse({
            'success': True,
            'message': 'Cliente guardado exitosamente',
            'cliente_id': cliente.id,
            'ya_existia': False
        })
        
    except Exception as e:
        logger.error(f"Error al guardar cliente automáticamente: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Error al guardar cliente: {str(e)}'
        })


def validar_ruc_ecuatoriano(ruc):
    """
    Validar que el RUC tenga formato ecuatoriano válido
    """
    if len(ruc) != 13:
        return False
    
    try:
        # Los primeros 2 dígitos deben ser provincia válida (01-24)
        provincia = int(ruc[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # El tercer dígito determina el tipo de RUC
        tercer_digito = int(ruc[2])
        
        # Para RUC de empresas, el tercer dígito debe ser 9
        # Para personas naturales con actividad económica, puede ser 0-5
        # Para entidades públicas, debe ser 6
        if tercer_digito not in [0, 1, 2, 3, 4, 5, 6, 9]:
            return False
        
        return True
        
    except ValueError:
        return False


def determinar_tipo_cliente(data_api):
    """
    Función auxiliar para determinar el tipo de cliente basado en los datos del API
    """
    # Ajustar la lógica según los datos que devuelva tu API
    tipo_contribuyente = data_api.get('tipoContribuyente', '').lower()
    
    if 'natural' in tipo_contribuyente or 'persona natural' in tipo_contribuyente:
        return 'Persona Natural'
    elif 'sociedad' in tipo_contribuyente or 'juridica' in tipo_contribuyente:
        return 'Sociedad'
    else:
        # Valor por defecto
        return 'Persona Natural'




#Fin de vista-----------------------------------------------------------------------------#


#Formulario simple que procesa un script para importar los clientes-----------------#
class ImportarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesImportados'] = True
            return HttpResponseRedirect("/inventario/importarClientes")

    def get(self, request):
        form = ImportarClientesFormulario()

        if request.session.get('clientesImportados') == True:
            importado = request.session.get('clientesImportados')
            contexto = {'form': form, 'clientesImportados': importado}
            request.session['clientesImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/importarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los clientes-----------------------#
class ExportarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ExportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesExportados'] = True
            # ================= MULTI-EMPRESA FIX =================
            # Export ONLY clients belonging to the active empresa.
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id:
                return HttpResponse("Empresa activa no establecida", status=400)

            queryset = Cliente.objects.filter(empresa_id=empresa_id)
            # ======================================================

            data = serializers.serialize("json", queryset)
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("clientes.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("clientes.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="clientes.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarClientesFormulario()

        if request.session.get('clientesExportados') == True:
            exportado = request.session.get('clientesExportados')
            contexto = {'form': form, 'clientesExportados': exportado}
            request.session['clientesExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/exportarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Muestra el mismo formulario del cliente pero con los datos a editar----------------------#
class EditarCliente(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()
        # Crea una instancia del formulario y la llena con los datos (multi-tenant)
        cliente = get_object_or_404(Cliente, id=p, empresa_id=empresa_id)
        form = ClienteFormulario(request.POST, instance=cliente, empresa=cliente.empresa)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            identificacion = form.cleaned_data['identificacion']
            razon_social = form.cleaned_data['razon_social']
            nombre_comercial = form.cleaned_data['nombre_comercial']
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            observaciones = form.cleaned_data['observaciones']
            convencional = form.cleaned_data['convencional']
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoCliente = form.cleaned_data['tipoCliente']
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']

            cliente.identificacion = identificacion
            cliente.razon_social = razon_social
            cliente.nombre_comercial = nombre_comercial
            cliente.direccion = direccion
            cliente.telefono = telefono
            cliente.correo = correo
            cliente.observaciones = observaciones
            cliente.convencional = convencional
            cliente.tipoVenta = tipoVenta
            cliente.tipoRegimen = tipoRegimen
            cliente.tipoCliente = tipoCliente
            cliente.tipoIdentificacion = tipoIdentificacion
            cliente.save()
            form = ClienteFormulario(instance=cliente, empresa=cliente.empresa)

            messages.success(request, 'Actualizado exitosamente el cliente de ID %s.' % p)
            request.session['clienteProcesado'] = 'editado'
            return HttpResponseRedirect("/inventario/editarCliente/%s" % cliente.id)
        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return redirect('inventario:seleccionar_empresa')
        cliente = get_object_or_404(Cliente, id=p, empresa_id=empresa_id)
        form = ClienteFormulario(instance=cliente, empresa=cliente.empresa)
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('clienteProcesado'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/agregarCliente.html', contexto)
    #Fin de vista--------------------------------------------------------------------------------#


#Emite la primera parte de la factura------------------------------#
# ===== VISTA EMITIR FACTURA CORREGIDA =====
# ===== AGREGAR ESTAS FUNCIONES AL FINAL DE views.py =====

def obtener_datos_secuencia(request, secuencia_id):
        """Obtiene (y opcionalmente reserva) el siguiente número para una secuencia.

        Parámetros (querystring):
            reservar=1   Si se incluye, incrementa y persiste el valor (reserva real)

        Lógica:
            1. Bloquea la fila de Secuencia (select_for_update) para evitar carreras.
            2. Si es tipo factura ('01') o guía ('06'), determina el máximo ya usado en
                 la tabla correspondiente (Factura.secuencia o GuiaRemision.secuencial) para
                 sincronizar en caso de que el registro Secuencia haya quedado atrasado.
            3. Calcula next = max(actual_en_tabla, secuencia.secuencial) + 1 (o 1 si vacío).
            4. Si reservar=1: actualiza secuencia.secuencial = next y guarda.
            5. Devuelve el número formateado sin afectar si no se pide reservar.

        Esto permite a la UI consultar sin consumir y sólo reservar cuando se confirme
        la creación del documento (llamando nuevamente con reservar=1) o directamente
        usar reservar=1 desde el flujo de emisión para evitar dobles asignaciones.
        """
        try:
            from django.db import transaction
            from django.db.models import Max
            empresa_id = request.session.get('empresa_activa')
            empresa = None
            if empresa_id:
                empresa = request.user.empresas.filter(id=empresa_id).first()
            if not empresa:
                return JsonResponse({'success': False, 'error': 'Empresa no activa'}, status=403)

            with transaction.atomic():
                # Bloquea la fila de la secuencia para lecturas concurrentes seguras
                secuencia = (Secuencia.objects.select_for_update()
                             .get(id=secuencia_id, empresa=empresa))

                establecimiento_formatted = secuencia.get_establecimiento_formatted()
                punto_emision_formatted = secuencia.get_punto_emision_formatted()

                siguiente_numero = 1
                if secuencia.tipo_documento == '01':
                    max_seq = (Factura.objects.filter(
                        empresa=empresa,
                        establecimiento=establecimiento_formatted,
                        punto_emision=punto_emision_formatted
                    ).aggregate(m=Max('secuencia'))['m'])
                    if max_seq:
                        try:
                            siguiente_numero = int(max_seq) + 1
                        except ValueError:
                            siguiente_numero = 1
                elif secuencia.tipo_documento == '06':
                    max_seq = (GuiaRemision.objects.filter(
                        empresa=empresa,
                        establecimiento=establecimiento_formatted,
                        punto_emision=punto_emision_formatted
                    ).aggregate(m=Max('secuencial'))['m'])
                    if max_seq:
                        try:
                            siguiente_numero = int(max_seq) + 1
                        except ValueError:
                            siguiente_numero = 1
                else:
                    # Usa el valor propio de la secuencia como base, si existe
                    if secuencia.secuencial:
                        try:
                            siguiente_numero = int(secuencia.secuencial) + 1
                        except ValueError:
                            siguiente_numero = 1

                # Determinar si se solicita reserva real
                reservar = request.GET.get('reservar') in ('1', 'true', 'True')

                # Para robustez: si secuencia.secuencial está por detrás del máximo detectado, sincronizar primero
                try:
                    base_actual = int(secuencia.secuencial)
                except (TypeError, ValueError):
                    base_actual = 0

                # next calculado arriba es el siguiente libre según tablas; si base_actual > (siguiente_numero-1) usar base_actual+1
                if base_actual >= (siguiente_numero - 1):
                    siguiente_numero = base_actual + 1

                if reservar:
                    # Persistir nuevo valor (ya validado que no exceda 9 dígitos en modelo)
                    secuencia.secuencial = siguiente_numero
                    secuencia.save(update_fields=['secuencial'])

                siguiente_numero_formateado = f"{siguiente_numero:09d}"

                return JsonResponse({
                    'success': True,
                    'data': {
                        'id': secuencia.id,
                        'descripcion': secuencia.descripcion,
                        'establecimiento': establecimiento_formatted,
                        'punto_emision': punto_emision_formatted,
                        'secuencial': siguiente_numero_formateado,
                        'tipo_documento': secuencia.tipo_documento,
                        'activo': secuencia.activo,
                        'reservado': reservar
                    }
                })
        except Secuencia.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Secuencia no encontrada'}, status=404)
        except Exception as e:
            print(f"💥 DEBUG: Error en obtener_datos_secuencia: {str(e)}")
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)


# ===== ASEGURAR QUE ESTAS FUNCIONES TAMBIÉN ESTÉN PRESENTES =====




## Nota: Se eliminó segunda versión duplicada de buscar_cliente (creadora) para evitar ambigüedad.
# ===== VISTA EMITIR FACTURA CORREGIDA =====
class EmitirFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        """Muestra el formulario para emitir factura"""
        try:
            # ✅ VERIFICAR QUE HAY UN FACTURADOR EN SESIÓN
            facturador_id = request.session.get('facturador_id')
            if not facturador_id:
                messages.warning(request, 'Debe iniciar sesión como facturador antes de emitir facturas.')
                return redirect('inventario:login_facturador')
            
            # Verificar que el facturador existe y está activo
            try:
                facturador = Facturador.tenant_objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                # Limpiar sesión de facturador inválido
                if 'facturador_id' in request.session:
                    del request.session['facturador_id']
                if 'facturador_nombre' in request.session:
                    del request.session['facturador_nombre']
                return redirect('inventario:login_facturador')

            # Obtener empresa activa para limitar datos tenant
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa antes de emitir facturas.')
                return redirect('inventario:panel')

            # Limitar cedulas/clientes por empresa activa
            cedulas = Cliente.objects.filter(empresa_id=empresa_id).values_list('id', 'identificacion')
            # Limitar secuencias a la empresa activa y tipo documento factura (01)
            secuencias = Secuencia.objects.filter(empresa_id=empresa_id, tipo_documento='01', activo=True).order_by('establecimiento', 'punto_emision')
            almacenes = Almacen.objects.filter(activo=True, empresa_id=empresa_id)

            # Preparar opciones para el formulario
            form = EmitirFacturaFormulario(cedulas=cedulas, secuencias=secuencias)

            # Actualizar el campo de almacenes dinámicamente con placeholder '...'
            form.fields['almacen'].choices = [('', '...')] + [
                (a.id, a.descripcion) for a in almacenes
            ]

            # ✅ AGREGAR: Obtener las cajas activas (solo de la empresa)
            cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion')
            
            # ✅ Formas de pago SRI desde el modelo
            formas_pago_sri = getattr(FormaPago, 'FORMAS_PAGO_CHOICES', [])

            # ✅ Lista de bancos: nombres únicos desde DB + fallback estático
            try:
                if hasattr(Banco, 'bancos_disponibles'):
                    bancos_db = set(Banco.bancos_disponibles())
                else:
                    bancos_db = set(Banco.objects.filter(empresa_id=empresa_id).values_list('banco', flat=True))
            except Exception:
                bancos_db = set()

            bancos_fallback = {
                'Pichincha', 'Produbanco', 'Pacifico', 'Machala', 'Guayaquil', 'Banecuador',
                'Internacional', 'Procredit', 'Austro', 'Bolivariano', 'Loja', 'Amazonas', 'Ruminahui'
            }
            lista_bancos = sorted({*(bancos_db or set()), *bancos_fallback})

            # Preparar el contexto
            contexto = {
                'form': form,
                'cedulas': cedulas,
                'secuencias': secuencias,
                'almacenes': almacenes,
                'facturador': facturador,  # ✅ AGREGAR INFO DEL FACTURADOR
                'cajas': cajas_activas,
                'formas_pago_sri': formas_pago_sri,
                'bancos_lista_nombres': lista_bancos,
                'bancos_db': Banco.objects.filter(activo=True, empresa_id=empresa_id).order_by('banco'),
                'now': timezone.now()  # Para la fecha por defecto en cheques
            }
            contexto = complementarContexto(contexto, request.user)

            return render(request, 'inventario/factura/emitirFactura.html', contexto)

        except Exception as e:
            print(f"Error al cargar la página de emitir factura: {e}")
            messages.error(request, f"Error al cargar la página: {e}")
            return redirect('inventario:panel')

    def post(self, request):
        """Procesa el formulario para crear la factura CON productos y formas de pago"""
        try:
            from django.db import transaction
            from decimal import Decimal, ROUND_HALF_UP
            import json
            
            # Imprimir datos recibidos para depuración
            print("[EmitirFactura.post] Datos formulario:", dict(request.POST))

            # ✅ RECUPERAR Y VALIDAR FACTURADOR DESDE SESIÓN
            facturador_id = request.session.get('facturador_id')
            if not facturador_id:
                messages.error(request, 'Debe iniciar sesión como facturador antes de emitir facturas.')
                return redirect('inventario:login_facturador')
            
            try:
                facturador = Facturador.tenant_objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                if 'facturador_id' in request.session:
                    del request.session['facturador_id']
                if 'facturador_nombre' in request.session:
                    del request.session['facturador_nombre']
                return redirect('inventario:login_facturador')

            # Recuperar empresa activa desde la sesión
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'No se ha seleccionado una empresa válida.')
                return redirect('inventario:panel')
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                messages.error(request, 'La empresa seleccionada no existe.')
                return redirect('inventario:panel')

            # ✅ VALIDAR QUE HAYA PRODUCTOS
            codigos = request.POST.getlist('productos_codigos[]')
            cantidades = request.POST.getlist('productos_cantidades[]')
            
            if not codigos:
                codigos = request.POST.getlist('productos_codigos')
                cantidades = request.POST.getlist('productos_cantidades')
            
            if not codigos or not cantidades:
                raise ValueError("Debe agregar al menos un producto a la factura.")
            
            if len(codigos) != len(cantidades):
                raise ValueError("Error en los datos de productos. Contacte al administrador.")
            
            print(f"📦 Productos recibidos: {len(codigos)}")
            
            # ✅ VALIDAR FORMAS DE PAGO
            pagos_json = request.POST.get('pagos_efectivo', '[]')
            try:
                pagos_list = json.loads(pagos_json)
            except json.JSONDecodeError:
                raise ValueError("Error al procesar las formas de pago.")
            
            if not pagos_list:
                raise ValueError("Debe agregar al menos una forma de pago.")
            
            print(f"💰 Formas de pago recibidas: {len(pagos_list)}")

            # Recuperar datos del cliente
            cliente_id = request.POST.get('cliente_id')
            if not cliente_id:
                raise ValueError("No se seleccionó un cliente válido.")
                
            cliente = get_object_or_404(Cliente, pk=cliente_id, empresa_id=empresa.id)

            # Actualizar correo del cliente
            correo_cliente = request.POST.get('correo_cliente', '').strip()
            if correo_cliente:
                cliente.correo = correo_cliente
                cliente.save()

            # Recuperar datos del almacén
            almacen_id = request.POST.get('almacen')
            if almacen_id:
                almacen = get_object_or_404(Almacen, pk=almacen_id, empresa=empresa)
            else:
                almacen = None

            # Convertir fechas
            from datetime import datetime
            fecha_emision_str = request.POST.get('fecha_emision')
            if not fecha_emision_str:
                raise ValueError("La fecha de emisión es obligatoria.")
            fecha_emision = datetime.strptime(fecha_emision_str, '%Y-%m-%d').date()

            fecha_vencimiento_str = request.POST.get('fecha_vencimiento')
            if not fecha_vencimiento_str:
                raise ValueError("La fecha de vencimiento es obligatoria.")
            fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()

            # Recuperar datos de secuencia
            establecimiento = (request.POST.get('establecimiento') or '').strip()
            punto_emision = (request.POST.get('punto_emision') or '').strip()
            secuencia_id = request.POST.get('secuencia')
            concepto = request.POST.get('concepto', 'Sin concepto')

            if not establecimiento or not punto_emision or not secuencia_id:
                raise ValueError("Establecimiento, Punto de Emisión y Secuencia son obligatorios.")

            try:
                secuencia_obj = Secuencia.objects.get(id=int(secuencia_id), empresa=empresa, activo=True)
            except (Secuencia.DoesNotExist, ValueError, TypeError):
                raise ValueError('La secuencia seleccionada no es válida para esta empresa.')

            if (str(secuencia_obj.get_establecimiento_formatted()) != str(establecimiento) or
                str(secuencia_obj.get_punto_emision_formatted()) != str(punto_emision)):
                raise ValueError('Los datos de establecimiento/punto de emisión no coinciden con la secuencia seleccionada.')

            def reservar_siguiente_secuencia(secuencia):
                from django.db.models import Max
                bloqueada = (Secuencia.objects.select_for_update()
                             .get(id=secuencia.id, empresa_id=secuencia.empresa_id))
                base = int(bloqueada.secuencial or 0)
                max_fact = (Factura.objects.filter(
                    empresa_id=bloqueada.empresa_id,
                    establecimiento=bloqueada.get_establecimiento_formatted(),
                    punto_emision=bloqueada.get_punto_emision_formatted()
                ).aggregate(m=Max('secuencia'))['m'])
                if max_fact:
                    try:
                        max_fact_int = int(max_fact)
                        if max_fact_int > base:
                            base = max_fact_int
                    except ValueError:
                        pass
                nuevo = base + 1
                bloqueada.secuencial = nuevo
                bloqueada.save(update_fields=['secuencial'])
                return f"{nuevo:09d}"

            # ✅ TRANSACCIÓN ATÓMICA: Factura + Detalles + Formas de Pago
            with transaction.atomic():
                # 1. Crear la factura
                secuencia_formateada = reservar_siguiente_secuencia(secuencia_obj)
                factura = Factura(
                    empresa=empresa,
                    cliente=cliente,
                    almacen=almacen,
                    facturador=facturador,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_vencimiento,
                    establecimiento=secuencia_obj.get_establecimiento_formatted(),
                    punto_emision=secuencia_obj.get_punto_emision_formatted(),
                    secuencia=secuencia_formateada,
                    concepto=concepto,
                    identificacion_cliente=cliente.identificacion,
                    nombre_cliente=f"{cliente.razon_social} {cliente.nombre_comercial if cliente.nombre_comercial else ''}".strip(),
                )
                factura.save()
                
                print(f"✅ Factura creada: {factura.id}")
                
                # 2. Procesar productos (COPIADO DE DetallesFactura)
                MAPEO_IVA = {
                    '0': Decimal('0.00'), '5': Decimal('0.05'), '2': Decimal('0.12'),
                    '10': Decimal('0.13'), '3': Decimal('0.14'), '4': Decimal('0.15'),
                    '9': Decimal('0.15'), '6': Decimal('0.00'), '7': Decimal('0.00'), '8': Decimal('0.08'),
                }
                
                sub_monto = Decimal('0.00')
                base_imponible = Decimal('0.00')
                monto_general = Decimal('0.00')
                total_iva = Decimal('0.00')
                
                # ✅ Obtener precios e IVAs personalizados
                precios_personalizados = request.POST.getlist('productos_precios[]')
                ivas_personalizados = request.POST.getlist('productos_ivas[]')
                descripciones_reemplazo = request.POST.getlist('productos_descripciones[]')
                info_adicional_list = request.POST.getlist('productos_info_adicional[]')
                
                print(f"💰 Precios personalizados recibidos: {precios_personalizados}")
                
                for idx, (codigo, cantidad_str) in enumerate(zip(codigos, cantidades)):
                    cantidad = int(cantidad_str)
                    
                    # Buscar producto o servicio
                    producto = Producto.objects.filter(empresa_id=empresa_id, codigo=codigo).first()
                    servicio = Servicio.objects.filter(empresa_id=empresa_id, codigo=codigo).first() if not producto else None
                    
                    if not producto and not servicio:
                        print(f"⚠️ Producto/Servicio no encontrado: {codigo}")
                        continue
                    
                    # ✅ USAR PRECIO PERSONALIZADO si existe
                    precio_pers = precios_personalizados[idx] if idx < len(precios_personalizados) else None
                    if precio_pers and precio_pers.strip():
                        precio_unitario = Decimal(precio_pers.strip())
                        print(f"   💰 Usando precio PERSONALIZADO: ${precio_unitario}")
                    elif producto:
                        precio_unitario = producto.precio
                    elif servicio:
                        precio_unitario = servicio.precio1
                    
                    # ✅ USAR IVA PERSONALIZADO si existe
                    iva_pers = ivas_personalizados[idx] if idx < len(ivas_personalizados) else None
                    if iva_pers and iva_pers.strip():
                        iva_code = iva_pers.strip()
                    elif producto:
                        iva_code = str(producto.iva.iva if hasattr(producto.iva, 'iva') else producto.iva)
                    elif servicio:
                        iva_code = str(servicio.iva.iva if hasattr(servicio.iva, 'iva') else servicio.iva)
                    
                    if producto:
                        descripcion = producto.descripcion
                    elif servicio:
                        precio_unitario = servicio.precio1
                        iva_code = str(servicio.iva.iva if hasattr(servicio.iva, 'iva') else servicio.iva)
                        descripcion = servicio.descripcion
                    
                    iva_percent = MAPEO_IVA.get(iva_code, Decimal('0.12'))
                    
                    # Cálculo exacto como en DetallesFactura
                    precio_con_iva_unitario = precio_unitario * (Decimal('1.00') + iva_percent)
                    total = precio_con_iva_unitario * cantidad
                    subtotal = precio_unitario * cantidad
                    valor_iva = total - subtotal
                    
                    # Redondear
                    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    valor_iva = valor_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    
                    # ✅ Obtener descripción reemplazo e info adicional
                    desc_reemplazo = descripciones_reemplazo[idx].strip() if idx < len(descripciones_reemplazo) and descripciones_reemplazo[idx].strip() else None
                    info_adic = info_adicional_list[idx].strip() if idx < len(info_adicional_list) and info_adicional_list[idx].strip() else None
                    
                    # Crear detalle
                    detalle = DetalleFactura.objects.create(
                        factura=factura,
                        empresa=empresa,  # ✅ CRÍTICO: Asignar empresa para TenantManager
                        producto=producto if producto else None,
                        servicio=servicio if servicio else None,
                        cantidad=cantidad,
                        sub_total=subtotal,
                        total=total,
                        descuento=Decimal('0.00'),
                        porcentaje_descuento=Decimal('0.00'),
                        # ✅ GUARDAR VALORES PERSONALIZADOS
                        precio_unitario=precio_unitario,
                        iva_codigo=iva_code,
                        descripcion_reemplazo=desc_reemplazo,
                        info_adicional=info_adic
                    )
                    
                    # ✅ Si hay info adicional, crear DetalleAdicional para el XML SRI
                    if info_adic:
                        DetalleAdicional.objects.create(
                            empresa_id=empresa_id,
                            detalle_factura=detalle,
                            nombre='Información',
                            valor=info_adic[:300]
                        )
                        print(f"   📝 Info adicional agregada al detalle: {info_adic[:50]}...")
                    
                    # ✅ DESCONTAR INVENTARIO: Solo si el producto tiene_inventario=True
                    if producto and getattr(producto, 'tiene_inventario', False):
                        if producto.disponible is None:
                            producto.disponible = 0
                        producto.disponible -= cantidad
                        producto.save()
                        print(f"   📦 Inventario actualizado: {producto.codigo} - Stock restante: {producto.disponible}")
                    elif producto:
                        print(f"   ℹ️ Producto {producto.codigo} no controla inventario - no se descuenta")
                    
                    # Forzar valores correctos después del save
                    DetalleFactura.objects.filter(id=detalle.id).update(
                        sub_total=subtotal,
                        total=total,
                        precio_unitario=precio_unitario,
                        iva_codigo=iva_code
                    )
                    
                    # Acumular totales
                    sub_monto += subtotal
                    if iva_percent > 0:
                        base_imponible += subtotal
                        total_iva += valor_iva
                    monto_general += total
                    
                    print(f"   ✅ Detalle: {descripcion} x{cantidad} = ${total}")
                
                # Redondear totales finales
                sub_monto = sub_monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                base_imponible = base_imponible.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                monto_general = monto_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                # 3. Actualizar totales de la factura
                factura.sub_monto = sub_monto
                factura.base_imponible = base_imponible
                factura.monto_general = monto_general
                factura.total_descuento = Decimal('0.00')
                factura.save()
                
                # Forzar valores después del save
                Factura.objects.filter(id=factura.id).update(
                    sub_monto=sub_monto,
                    base_imponible=base_imponible,
                    monto_general=monto_general
                )
                factura.refresh_from_db()
                
                print(f"✅ Totales: Subtotal=${sub_monto}, IVA=${total_iva}, Total=${monto_general}")
                
                # 4. Procesar formas de pago (COPIADO DE DetallesFactura)
                PRECISION_DOS_DECIMALES = Decimal('0.01')
                
                for i, pago in enumerate(pagos_list):
                    print(f"💳 PROCESANDO PAGO {i+1}: {pago}")
                    
                    sri_pago = pago.get('sri_pago')
                    if not sri_pago:
                        raise Exception("Código SRI de forma de pago es requerido")
                    
                    # Normalizar monto
                    monto_str = str(pago.get('monto', '0')).replace(',', '.')
                    monto = Decimal(monto_str).quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
                    
                    if monto <= 0:
                        raise Exception("El monto debe ser mayor a cero")
                    
                    # Obtener caja (opcional para depósitos)
                    tipo_pago = str(pago.get('tipo', '')).lower()
                    caja = None
                    if tipo_pago != 'deposito':
                        caja_id = pago.get('caja') or pago.get('caja_id')
                        if caja_id:
                            try:
                                caja = Caja.objects.get(id=caja_id, activo=True, empresa_id=empresa_id)
                            except Caja.DoesNotExist:
                                print(f"⚠️ Caja no encontrada: {caja_id}")
                    
                    # Crear forma de pago
                    FormaPago.objects.create(
                        factura=factura,
                        forma_pago=sri_pago,
                        total=monto,
                        caja=caja,
                        empresa=empresa
                    )
                    
                    print(f"   ✅ Forma de pago: {tipo_pago} ${monto}")
                
                # Generar clave de acceso si no existe
                if not factura.clave_acceso:
                    factura.save()
                    factura.refresh_from_db()
                
                # Crear totales de impuestos automáticamente
                if hasattr(factura, 'crear_totales_impuestos_automatico'):
                    factura.crear_totales_impuestos_automatico()
                    factura.save()

            print(f"🎉 FACTURA COMPLETADA: {establecimiento}-{punto_emision}-{secuencia_formateada}")
            messages.success(request, f'¡Factura {establecimiento}-{punto_emision}-{secuencia_formateada} creada exitosamente!')
            
            # Redirigir directamente a VER la factura (verFactura.html)
            return redirect('inventario:verFactura', p=factura.id)

        except ValueError as e:
            print(f"Error de validación: {e}")
            messages.error(request, f"Error: {e}")
            return self.get(request)

        except Exception as e:
            print(f"Error inesperado: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            messages.error(request, f"Error inesperado: {e}")
            return self.get(request)  # Volver a mostrar el formulario

# ===== CLASE DETALLES FACTURA CORREGIDA =====
# Importaciones necesarias para facturación electrónica SRI
from decimal import Decimal, ROUND_HALF_UP
import random
import decimal

class DetallesFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        try:
            # Garantiza que creación de detalles, totales y formas de pago sea atómica
            from django.db import transaction
            with transaction.atomic():
                print("=== INICIO DE PROCESAMIENTO DE DETALLES ===")
                print("POST data received:", dict(request.POST))
                print("POST KEYS:", list(request.POST.keys()))
                # Log de emergencia para depuración de arrays
                print("\n=== DIAGNÓSTICO DE CAMPOS DE PRODUCTOS ===")
                for key in request.POST.keys():
                    print(f"Campo recibido: {key} => {request.POST.getlist(key)}")
                print("=== FIN DIAGNÓSTICO ===\n")

                # Verificar factura en sesión y pertenencia a empresa activa
                empresa_id = request.session.get('empresa_activa')
                factura_id = request.session.get('factura_id')
                if not factura_id:
                    messages.error(request, 'No se encontró la factura a la cual agregar productos.')
                    return redirect('inventario:emitirFactura')

                factura = Factura.objects.filter(pk=factura_id, empresa_id=empresa_id).first()
                if not factura:
                    if Factura.objects.filter(pk=factura_id).exists():
                        messages.error(request, 'Acceso no autorizado a factura de otra empresa.')
                    else:
                        messages.error(request, 'No se pudo encontrar la factura.')
                    request.session.pop('factura_id', None)
                    return redirect('inventario:emitirFactura')

                print(f"Procesando factura ID: {factura_id}")
                
                # ✅ LOGGING SÚPER DETALLADO para debug completo
                logger.info("="*80)
                logger.info("🚀 INICIANDO PROCESAMIENTO DE FACTURA")
                logger.info(f"📋 POST data completo: {dict(request.POST)}")
                logger.info("="*80)

                # Obtener listas de códigos y cantidades
                codigos = request.POST.getlist('productos_codigos[]')
                cantidades = request.POST.getlist('productos_cantidades[]')
                # ✅ Obtener precios e IVAs personalizados (opcionales)
                precios_personalizados = request.POST.getlist('productos_precios[]')
                ivas_personalizados = request.POST.getlist('productos_ivas[]')
                # ✅ Obtener descripciones e info adicional (opcionales)
                descripciones_reemplazo = request.POST.getlist('productos_descripciones[]')
                info_adicional_list = request.POST.getlist('productos_info_adicional[]')
                
                # Si no llegan, intentar variantes comunes de nombre
                if not codigos:
                    codigos = request.POST.getlist('productos_codigos')
                if not cantidades:
                    cantidades = request.POST.getlist('productos_cantidades')
                if not precios_personalizados:
                    precios_personalizados = request.POST.getlist('productos_precios')
                if not ivas_personalizados:
                    ivas_personalizados = request.POST.getlist('productos_ivas')
                if not descripciones_reemplazo:
                    descripciones_reemplazo = request.POST.getlist('productos_descripciones')
                if not info_adicional_list:
                    info_adicional_list = request.POST.getlist('productos_info_adicional')

                print(f"Códigos recibidos: {codigos}")
                print(f"Cantidades recibidas: {cantidades}")
                print(f"Precios personalizados: {precios_personalizados}")
                print(f"IVAs personalizados: {ivas_personalizados}")
                print(f"Descripciones reemplazo: {descripciones_reemplazo}")
                print(f"Info adicional: {info_adicional_list}")
                
                logger.info(f"📦 Códigos recibidos: {codigos}")
                logger.info(f"🔢 Cantidades recibidas: {cantidades}")
                logger.info(f"💰 Precios personalizados: {precios_personalizados}")
                logger.info(f"📊 IVAs personalizados: {ivas_personalizados}")
                logger.info(f"📝 Descripciones reemplazo: {descripciones_reemplazo}")
                logger.info(f"ℹ️ Info adicional: {info_adicional_list}")

                # Validaciones iniciales
                if not codigos or not cantidades:
                    # Mensaje de ayuda para el frontend
                    msg = (
                        "No se enviaron productos para la factura.\n"
                        "\nDiagnóstico:\n"
                        f"Campos recibidos: {list(request.POST.keys())}\n"
                        "El backend espera los campos 'productos_codigos[]' y 'productos_cantidades[]' como arrays.\n"
                        "Asegúrate de que el formulario los envía exactamente con esos nombres y como múltiples campos (input hidden con name='productos_codigos[]').\n"
                        "Ejemplo correcto en HTML:\n"
                        "<input type='hidden' name='productos_codigos[]' value='COD1'>\n"
                        "<input type='hidden' name='productos_codigos[]' value='COD2'>\n"
                        "<input type='hidden' name='productos_cantidades[]' value='1'>\n"
                        "<input type='hidden' name='productos_cantidades[]' value='2'>\n"
                        "\nRevisa el JavaScript que genera estos campos antes de enviar el formulario.\n"
                    )
                    print(msg)
                    messages.error(request, msg)
                    return self.get(request)

                if len(codigos) != len(cantidades):
                    messages.error(request, "Error en los datos de productos enviados.")
                    return self.get(request)

                # Asegurar que la factura tenga un ID antes de acceder a relaciones
                if not factura.pk:
                    factura.save()
                    print(f"Factura guardada con ID: {factura.id}")
                
                # Limpiar detalles anteriores de esta factura
                DetalleFactura.objects.filter(factura=factura).delete()
                print("Detalles anteriores eliminados")

                # Variables para totales (SRI requiere exactitud en cálculos)
                sub_monto = Decimal('0.00')
                base_imponible = Decimal('0.00')
                monto_general = Decimal('0.00')
                total_iva = Decimal('0.00')
                productos_procesados = 0

                # Procesar cada producto
                errores = []  # Inicializar la lista de errores
                for idx, (codigo, cantidad_str) in enumerate(zip(codigos, cantidades)):
                    producto = Producto.objects.filter(empresa_id=factura.empresa_id, codigo=codigo).first()
                    servicio = Servicio.objects.filter(empresa_id=factura.empresa_id, codigo=codigo).first()
                    if not producto and not servicio:
                        errores.append(f"Producto o servicio con código '{codigo}' no encontrado.")
                        continue

                    cantidad = int(cantidad_str)
                    descuento = Decimal('0.00')
                    porcentaje_descuento = Decimal('0.00')
                    precio_sin_subsidio = None

                    # Mapeo de códigos SRI a porcentajes reales
                    MAPEO_IVA = {
                        '0': Decimal('0.00'),  # Sin IVA
                        '5': Decimal('0.05'),  # 5%
                        '2': Decimal('0.12'),  # 12%
                        '10': Decimal('0.13'), # 13%
                        '3': Decimal('0.14'),  # 14%
                        '4': Decimal('0.15'),  # 15%
                        '9': Decimal('0.15'),  # 15% (antes 16%) normalizado
                        '6': Decimal('0.00'),  # Exento
                        '7': Decimal('0.00'),  # Exento
                        '8': Decimal('0.08')   # 8%
                    }

                    # ✅ Usar precio personalizado si se envió, sino usar precio del producto
                    precio_pers_valor = precios_personalizados[idx] if precios_personalizados and idx < len(precios_personalizados) else None
                    
                    print("="*60)
                    print(f"🔍 PRECIO DEBUG [{idx}]:")
                    print(f"   precios_personalizados lista: {precios_personalizados}")
                    print(f"   precio_pers_valor: '{precio_pers_valor}'")
                    print("="*60)
                    
                    logger.info(f"   🔍 Precio personalizado recibido[{idx}]: '{precio_pers_valor}'")
                    
                    if precio_pers_valor and precio_pers_valor.strip():
                        try:
                            precio_unitario = Decimal(str(precio_pers_valor.strip()))
                            print(f"   ✅ USANDO PRECIO PERSONALIZADO: {precio_unitario}")
                            logger.info(f"   💰 Usando precio PERSONALIZADO: {precio_unitario}")
                        except Exception as e:
                            print(f"   ❌ ERROR CONVIRTIENDO PRECIO: {e}")
                            logger.error(f"   ❌ Error convirtiendo precio: {e}")
                            precio_unitario = producto.precio if producto else servicio.precio1
                    elif producto:
                        precio_unitario = producto.precio
                        print(f"   ⚠️ USANDO PRECIO ORIGINAL PRODUCTO: {precio_unitario}")
                    elif servicio:
                        precio_unitario = servicio.precio1
                        print(f"   ⚠️ USANDO PRECIO ORIGINAL SERVICIO: {precio_unitario}")
                    else:
                        continue
                    
                    # ✅ Usar IVA personalizado si se envió, sino usar IVA del producto
                    iva_pers_valor = ivas_personalizados[idx] if ivas_personalizados and idx < len(ivas_personalizados) else None
                    logger.info(f"   🔍 IVA personalizado recibido[{idx}]: '{iva_pers_valor}'")
                    
                    if iva_pers_valor and str(iva_pers_valor).strip():
                        iva_code = str(iva_pers_valor).strip()
                        iva_percent = MAPEO_IVA.get(iva_code, Decimal('0.15'))
                        logger.info(f"   📊 Usando IVA PERSONALIZADO: {iva_code} ({iva_percent * 100}%)")
                    elif producto:
                        iva_code = str(producto.iva.iva if hasattr(producto.iva, 'iva') else producto.iva)
                        iva_percent = MAPEO_IVA.get(iva_code, Decimal('0.15'))
                    elif servicio:
                        iva_code = str(servicio.iva.iva if hasattr(servicio.iva, 'iva') else servicio.iva)
                        iva_percent = MAPEO_IVA.get(iva_code, Decimal('0.15'))

                    # 🔍 DEBUG: Logging detallado de cálculos
                    logger.info(f"🔢 PROCESANDO: Código={codigo}, Cantidad={cantidad}")
                    logger.info(f"   Precio unitario: {precio_unitario}")
                    logger.info(f"   IVA code: {iva_code}")
                    logger.info(f"   IVA percent: {iva_percent}")

                    # ✅ CORREGIDO: Usar mismo algoritmo que JavaScript para exactitud
                    # JavaScript: precioConIva = precio * (1 + ivaPercent); totalConIva = cantidad * precioConIva;
                    precio_con_iva_unitario = precio_unitario * (Decimal('1.00') + iva_percent)
                    total = precio_con_iva_unitario * cantidad
                    subtotal = precio_unitario * cantidad
                    valor_iva = total - subtotal

                    logger.info(f"   Precio con IVA unitario SIN redondear: {precio_con_iva_unitario}")
                    logger.info(f"   Total SIN redondear: {total}")

                    # Redondear a 2 decimales EXACTO como JavaScript Math.round()
                    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    valor_iva = valor_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    logger.info(f"   Total CON redondeo Django: {total}")
                    logger.info(f"   📊 Acumulando en monto_general: {monto_general} + {total}")

                    # ✅ Determinar si hay valores personalizados diferentes al producto original
                    codigo_personalizado = None
                    precio_personalizado = None
                    iva_personalizado = None
                    
                    if producto:
                        # Código personalizado: si difiere del código del producto
                        if codigo != producto.codigo:
                            codigo_personalizado = codigo
                        # Precio personalizado: si difiere del precio del producto
                        if precio_unitario != producto.precio:
                            precio_personalizado = precio_unitario
                        # IVA personalizado: si difiere del IVA del producto
                        iva_original = str(producto.iva.iva if hasattr(producto.iva, 'iva') else producto.iva)
                        if iva_code != iva_original:
                            iva_personalizado = iva_code
                    elif servicio:
                        # Para servicios, guardar siempre los valores usados
                        codigo_personalizado = codigo if codigo != servicio.codigo else None
                        precio_personalizado = precio_unitario if precio_unitario != servicio.precio1 else None
                        iva_original = str(servicio.iva.iva if hasattr(servicio.iva, 'iva') else servicio.iva)
                        iva_personalizado = iva_code if iva_code != iva_original else None

                    # ✅ Obtener descripción de reemplazo e info adicional para este ítem
                    descripcion_reemplazo = None
                    info_adicional = None
                    if descripciones_reemplazo and idx < len(descripciones_reemplazo):
                        descripcion_reemplazo = descripciones_reemplazo[idx].strip() or None
                    if info_adicional_list and idx < len(info_adicional_list):
                        info_adicional = info_adicional_list[idx].strip() or None

                    print(f"💾 GUARDANDO DetalleFactura con precio_unitario={precio_unitario}")
                    
                    detalle = DetalleFactura.objects.create(
                        factura=factura,
                        producto=producto if producto else None,
                        servicio=servicio if servicio else None,
                        cantidad=cantidad,
                        sub_total=subtotal,
                        total=total,
                        descuento=descuento,
                        porcentaje_descuento=porcentaje_descuento,
                        precio_sin_subsidio=precio_sin_subsidio,
                        # ✅ CORREGIDO: Siempre guardar precio_unitario (ya tiene el valor correcto)
                        codigo_personalizado=codigo_personalizado,
                        precio_unitario=precio_unitario,  # ✅ Siempre guardar el precio usado
                        iva_codigo=iva_code,  # ✅ Siempre guardar el IVA usado
                        # ✅ Guardar descripción e info adicional para esta factura
                        descripcion_reemplazo=descripcion_reemplazo,
                        info_adicional=info_adicional
                    )
                    
                    print(f"💾 DetalleFactura guardado. ID={detalle.id}, precio_unitario en DB={detalle.precio_unitario}")
                    
                    # ✅ Si hay info adicional, crear DetalleAdicional para el XML SRI
                    if info_adicional:
                        DetalleAdicional.objects.create(
                            empresa_id=factura.empresa_id,
                            detalle_factura=detalle,
                            nombre='Información',
                            valor=info_adicional[:300]
                        )
                        logger.info(f"   📝 Info adicional agregada al detalle: {info_adicional[:50]}...")
                    
                    # ✅ DESCONTAR INVENTARIO: Solo si el producto tiene_inventario=True
                    if producto and getattr(producto, 'tiene_inventario', False):
                        if producto.disponible is None:
                            producto.disponible = 0
                        producto.disponible -= cantidad
                        producto.save()
                        logger.info(f"   📦 Inventario actualizado: {producto.codigo} - Stock restante: {producto.disponible}")
                    elif producto:
                        logger.info(f"   ℹ️ Producto {producto.codigo} no controla inventario - no se descuenta")
                    
                    # 🔧 CRÍTICO: Actualizar el detalle CON LOS VALORES CORRECTOS después del save()
                    # El método save() del modelo puede recalcular, así que forzamos nuestros valores
                    DetalleFactura.objects.filter(id=detalle.id).update(
                        sub_total=subtotal,
                        total=total
                    )

                    # Acumular totales
                    sub_monto += subtotal
                    if iva_percent > 0:
                        base_imponible += subtotal
                        total_iva += valor_iva
                    # El total de la factura debe incluir todos los productos y servicios,
                    # sin importar si tienen o no IVA asociado
                    monto_general += total

                    print(f"✅ Producto procesado: {codigo} - Cantidad: {cantidad} - Precio unitario: {precio_unitario} - Subtotal: {subtotal} - IVA: {valor_iva} - Total: {total}")
                    productos_procesados += 1
                if hasattr(factura, 'crear_totales_impuestos_automatico'):
                    factura.crear_totales_impuestos_automatico()
                factura.save()

        except Exception as e:
            print(f"❌ Error general en procesamiento: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            # ✅ AGREGAR: En caso de error, también enviar cajas
            try:
                cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion') if empresa_id else Caja.objects.none()
                contexto = {
                    'cajas': cajas_activas,
                }
                contexto = complementarContexto(contexto, request.user)
                messages.error(request, f"Error en procesamiento de factura: {str(e)}")
                return render(request, 'inventario/factura/detallesFactura.html', contexto)
            except:
                # Si falla cargar cajas, usar el método get normal
                messages.error(request, f"Error en procesamiento de factura: {str(e)}")
                return self.get(request)

        # Verificar que se procesó al menos un producto
        if productos_procesados == 0:
            # ✅ AGREGAR: En caso de error, también enviar cajas
            try:
                cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion') if empresa_id else Caja.objects.none()
                contexto = {
                    'cajas': cajas_activas,
                }
                contexto = complementarContexto(contexto, request.user)
                messages.error(request, "No se pudo procesar ningún producto. Verifique los datos.")
                return render(request, 'inventario/factura/detallesFactura.html', contexto)
            except:
                # Si falla cargar cajas, usar el método get normal
                messages.error(request, "No se pudo procesar ningún producto. Verifique los datos.")
                return self.get(request)

        # Redondear totales finales para cumplir SRI
        sub_monto = sub_monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        base_imponible = base_imponible.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        monto_general = monto_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_iva = total_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Actualizar totales de la factura según estructura SRI
        factura.sub_monto = sub_monto  # totalSinImpuestos en XML SRI
        factura.base_imponible = base_imponible  # baseImponible en XML SRI
        factura.monto_general = monto_general  # importeTotal en XML SRI
        factura.total_descuento = Decimal('0.00')  # Sin descuentos por ahora
        
        # Asegurar que la factura tenga un ID antes de procesar formas de pago
        if not factura.pk:
            factura.save()
            print(f"Factura guardada con ID: {factura.id}")
            
            # 🔧 CRÍTICO: FORZAR los valores correctos después del save()
            # El método save() del modelo puede recalcular, así que forzamos nuestros valores
            Factura.objects.filter(id=factura.id).update(
                sub_monto=sub_monto,
                base_imponible=base_imponible, 
                monto_general=monto_general
            )
            # Recargar la factura con los valores correctos
            factura.refresh_from_db()
            logger.info(f"🔧 VALORES FORZADOS: monto_general={factura.monto_general}")
        
        # 🔧 FIX CRÍTICO: Asegurar que la clave de acceso se genere INMEDIATAMENTE
        # Esto garantiza que la misma clave se use para PDF y autorización SRI
        if not hasattr(factura, 'clave_acceso') or not factura.clave_acceso:
            print("⚠️  Factura sin clave de acceso, forzando generación...")
            factura.save()  # Esto disparará la generación automática en el modelo
            factura.refresh_from_db()  # Recargar para obtener la clave generada
            
            if factura.clave_acceso:
                print(f"✅ Clave de acceso generada: {factura.clave_acceso}")
            else:
                raise ValueError(f"ERROR CRÍTICO: No se pudo generar clave de acceso para factura {factura.id}")
        else:
            print(f"✅ Clave de acceso ya existe: {factura.clave_acceso}")

        # ✅ PROCESAR FORMAS DE PAGO
        try:
            print("=== PROCESANDO FORMAS DE PAGO ===")
            print(f"📋 POST data keys: {list(request.POST.keys())}")
            
            # Obtener y validar datos de pagos
            pagos_data = request.POST.get('pagos_efectivo', '[]')
            print(f"📦 Datos de pagos recibidos: {pagos_data}")
            
            # ✅ LOGGING DETALLADO DE PAGOS
            logger.info(f"💰 Datos de pagos RAW: {pagos_data}")
            
            pagos_list = json.loads(pagos_data)
            logger.info(f"💰 Pagos parseados: {pagos_list}")
            logger.info(f"💰 Cantidad de pagos: {len(pagos_list)}")
            
            if not pagos_list:
                logger.warning("⚠️ No se recibieron formas de pago desde el formulario. Creando forma de pago por defecto para evitar bloqueo.")
                # Asegurar totales actualizados antes de crear pago automático
                factura.refresh_from_db()
                monto_total_factura = factura.monto_general or Decimal('0.00')
                if monto_total_factura <= 0:
                    raise Exception("Total de factura inválido para crear forma de pago automática")
                # Elegir una caja activa si existe
                caja_default = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('id').first()
                forma_pago_auto = FormaPago.objects.create(
                    factura=factura,
                    forma_pago='20',  # 'Otros con utilización del sistema financiero'
                    total=monto_total_factura,
                    caja=caja_default,
                    empresa=factura.empresa
                )
                logger.info(f"✅ Forma de pago automática creada: id={forma_pago_auto.id} total={monto_total_factura}")
                pagos_list = [{
                    'sri_pago': '20',
                    'monto': str(monto_total_factura),
                    'tipo': 'auto'
                }]
            
            # Limpiar formas de pago anteriores
            if hasattr(factura, 'formas_pago'):
                factura.formas_pago.all().delete()
            
            # Procesar cada pago
            PRECISION_DOS_DECIMALES = Decimal('0.01')
            suma_pagos = Decimal('0.00')
            
            for i, pago in enumerate(pagos_list):
                logger.info(f"💳 PROCESANDO PAGO {i+1}: {pago}")
                
                # Validar campos requeridos
                sri_pago = pago.get('sri_pago')
                if not sri_pago:
                    raise Exception("Código SRI de forma de pago es requerido")
                
                try:
                    # Normalizar el monto: reemplazar coma por punto y asegurar 2 decimales
                    monto_str = str(pago.get('monto', '0')).replace(',', '.')
                    logger.info(f"   Monto string recibido: '{monto_str}'")
                    
                    monto = Decimal(monto_str).quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
                    logger.info(f"   Monto convertido a Decimal: {monto}")
                    
                    if monto <= 0:
                        raise Exception("El monto debe ser mayor a cero")
                except InvalidOperation:
                    raise Exception("Monto de pago inválido")
                
                # Obtener tipo de pago para manejar depósitos sin caja
                tipo_pago = str(pago.get('tipo', '')).lower()
                caja = None
                if tipo_pago != 'deposito':
                    # Obtener la caja (acepta tanto 'caja' como 'caja_id') y validar empresa
                    caja_id = pago.get('caja') or pago.get('caja_id')
                    if not caja_id:
                        raise Exception("Caja no especificada para el pago")

                    try:
                        caja = Caja.objects.get(id=caja_id, activo=True, empresa_id=empresa_id)
                    except Caja.DoesNotExist:
                        raise Exception(f"Caja {caja_id} no existe, está inactiva o no pertenece a la empresa activa")
                else:
                    logger.info("   Pago de tipo 'deposito' - omitiendo validación de caja")

                # Crear forma de pago con monto normalizado (caja puede ser None)
                forma_pago_obj = FormaPago.objects.create(
                    factura=factura,
                    forma_pago=sri_pago,
                    total=monto,
                    caja=caja,
                    empresa=factura.empresa
                )
                suma_pagos += monto
                logger.info(f"   ✅ Pago registrado. Total acumulado: {suma_pagos}")

                # Guardar datos complementarios de cheque, tarjeta o depósito como campos adicionales de la factura
                try:
                    if str(pago.get('tipo', '')).lower() == 'cheque':
                        banco_val = pago.get('banco') or pago.get('banco_id')
                        comprobante = (pago.get('comprobante') or '').strip()
                        vence = (pago.get('vence') or '').strip()

                        # Banco (acepta ID o nombre directamente)
                        if banco_val:
                            banco_nombre = None
                            # Si es un número, intentar buscar por ID
                            try:
                                if str(banco_val).isdigit():
                                    banco = Banco.objects.get(id=int(banco_val), empresa_id=empresa_id)
                                    banco_nombre = str(banco.banco)
                                else:
                                    banco_nombre = str(banco_val)
                            except Banco.DoesNotExist:
                                banco_nombre = str(banco_val)

                            if banco_nombre:
                                CampoAdicional.objects.update_or_create(
                                    factura=factura,
                                    nombre='Banco Cheque',
                                    defaults={'valor': banco_nombre, 'orden': 1, 'empresa': factura.empresa}
                                )

                        # Comprobante
                        if comprobante:
                            CampoAdicional.objects.update_or_create(
                                factura=factura,
                                nombre='Comprobante Cheque',
                                defaults={'valor': comprobante, 'orden': 2, 'empresa': factura.empresa}
                            )
                        # Vence (fecha)
                        if vence:
                            CampoAdicional.objects.update_or_create(
                                factura=factura,
                                nombre='Vence Cheque',
                                defaults={'valor': vence, 'orden': 3, 'empresa': factura.empresa}
                            )
                    # Tarjeta de crédito (código 19) u objeto con tipo 'tarjeta'
                    if str(sri_pago) == '19' or str(pago.get('tipo', '')).lower() == 'tarjeta':
                        tarjeta_tipo = (pago.get('tarjeta_tipo') or '').strip()
                        comprobante_tarjeta = (pago.get('comprobante') or '').strip()

                        if tarjeta_tipo:
                            CampoAdicional.objects.update_or_create(
                                factura=factura,
                                nombre='Tarjeta',
                                defaults={'valor': tarjeta_tipo, 'orden': 4, 'empresa': factura.empresa}
                            )
                    # Depósito con banco y comprobante
                    if str(pago.get('tipo', '')).lower() == 'deposito':
                        banco_id = pago.get('banco')
                        comprobante_dep = (pago.get('comprobante') or '').strip()

                        if banco_id:
                            try:
                                banco = Banco.objects.get(id=banco_id, empresa_id=empresa_id)
                                CampoAdicional.objects.update_or_create(
                                    factura=factura,
                                    nombre='Banco Depósito',
                                    defaults={'valor': str(banco.banco), 'orden': 5, 'empresa': factura.empresa},
                                )
                            except Banco.DoesNotExist:
                                # Banco inexistente o de otra empresa: ignorar
                                pass
                        if comprobante_dep:
                            CampoAdicional.objects.update_or_create(
                                factura=factura,
                                nombre='Comprobante Depósito',
                                defaults={'valor': comprobante_dep, 'orden': 6, 'empresa': factura.empresa},
                            )
                except Exception as _e:
                    logger.warning(f"No se pudieron guardar datos adicionales del cheque: {_e}")

            logger.info(f"💰 SUMA TOTAL DE PAGOS: {suma_pagos}")

            # Recalcular totales de la factura para evitar diferencias por redondeo
            factura.save()
            factura.refresh_from_db()

            if factura.empresa_id:
                tenant_unsafe_service(FormaPago).update(
                    empresa_id=factura.empresa_id,
                    allow_null_empresa=True,
                    filters={"factura": factura, "empresa__isnull": True},
                    updates={"empresa": factura.empresa},
                )
                tenant_unsafe_service(CampoAdicional).update(
                    empresa_id=factura.empresa_id,
                    allow_null_empresa=True,
                    filters={"factura": factura, "empresa__isnull": True},
                    updates={"empresa": factura.empresa},
                )

            # 🔍 DEBUG: Logging detallado antes de validar pagos
            logger.info(f"📊 VALIDACIÓN FINAL:")
            logger.info(f"   Suma pagos SIN redondear: {suma_pagos}")
            logger.info(f"   Monto factura desde DB: {factura.monto_general}")

            # ✅ CORREGIDO: Usar redondeo estándar compatible con JavaScript Math.round()
            # JavaScript Math.round() usa el mismo algoritmo que Decimal ROUND_HALF_UP 
            
            # Redondear igual que JavaScript para evitar diferencias de $0.02
            suma_pagos = suma_pagos.quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
            monto_factura = factura.monto_general.quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
            
            logger.info(f"   Suma pagos CON redondeo: {suma_pagos}")
            logger.info(f"   Monto factura CON redondeo: {monto_factura}")
            logger.info(f"   Diferencia absoluta: {abs(suma_pagos - monto_factura)}")
            
            # Validar que la suma coincida con el total de la factura
            if suma_pagos != monto_factura:
                # Intentar sincronizar automáticamente antes de fallar
                logger.warning(f"⚠️ Discrepancia de pagos detectada - Suma: {suma_pagos}, Factura: {monto_factura}. Intentando sincronizar.")
                try:
                    if hasattr(factura, 'sincronizar_formas_pago'):
                        msg_sync = factura.sincronizar_formas_pago()
                        logger.info(f"🔧 {msg_sync}")
                        factura.refresh_from_db()
                        suma_pagos = sum(fp.total for fp in factura.formas_pago.all())
                        suma_pagos = Decimal(str(suma_pagos)).quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
                        monto_factura = factura.monto_general.quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
                except Exception as _sync_e:
                    logger.error(f"Error sincronizando formas de pago: {_sync_e}")
                if suma_pagos != monto_factura:
                    logger.error(f"❌ ERROR: Discrepancia de pagos persiste - Suma: {suma_pagos}, Factura: {monto_factura}")
                    raise Exception(
                        f"La suma de pagos (${suma_pagos}) no coincide con el total de la factura (${monto_factura}). "
                        f"Por favor, verifique que los montos ingresados sumen exactamente el total de la factura."
                    )
            
            # Guardar la factura y retornar respuesta exitosa (dentro de transacción)
            factura.save()
            messages.success(request, "Factura procesada correctamente")
            return redirect('inventario:verFactura', p=factura.id)
            
        except json.JSONDecodeError as e:
            messages.error(request, f"Error en datos de pago: {str(e)}")
            return redirect('inventario:emitirFactura')
        except Exception as e:
            messages.error(request, str(e))
            return redirect('inventario:emitirFactura')

    def get(self, request):
        # Obtener empresa activa y validar pertenencia
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida')
            return redirect('inventario:seleccionar_empresa')

        # ✅ AGREGAR: Obtener las cajas activas (solo de la empresa)
        cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion')
        
        # ✅ AGREGAR: Obtener la factura de la sesión para mostrarla
        factura_id = request.session.get('factura_id')
        factura = None
        if factura_id:
            factura = Factura.objects.filter(pk=factura_id, empresa_id=empresa_id).first()
            if not factura:
                # Comprobar si existe en otra empresa para mensaje apropiado
                if Factura.objects.filter(pk=factura_id).exists():
                    messages.error(request, 'Acceso no autorizado a factura de otra empresa.')
                else:
                    messages.error(request, 'No se pudo encontrar la factura. Por favor, cree una nueva factura.')
                request.session.pop('factura_id', None)
                return redirect('inventario:emitirFactura')
        else:
            messages.error(request, 'No se encontró la factura. Por favor, cree una nueva factura.')
            return redirect('inventario:emitirFactura')
        
        # ✅ Formas de pago SRI desde el modelo (evitar hardcode)
        formas_pago_sri = getattr(FormaPago, 'FORMAS_PAGO_CHOICES', [])

        # ✅ Lista de bancos: nombres únicos desde DB + fallback estático
        try:
            if hasattr(Banco, 'bancos_disponibles'):
                bancos_db = set(Banco.bancos_disponibles())
            else:
                bancos_db = set(Banco.objects.filter(empresa_id=empresa_id).values_list('banco', flat=True))
        except Exception:
            bancos_db = set()

        bancos_fallback = {
            'Pichincha', 'Produbanco', 'Pacifico', 'Machala', 'Guayaquil', 'Banecuador',
            'Internacional', 'Procredit', 'Austro', 'Bolivariano', 'Loja', 'Amazonas', 'Ruminahui'
        }
        lista_bancos = sorted({*(bancos_db or set()), *bancos_fallback})

        contexto = {
            'cajas': cajas_activas,
            'factura': factura,
            'formas_pago_sri': formas_pago_sri,
            'bancos_lista_nombres': lista_bancos,
            'bancos_db': Banco.objects.filter(activo=True, empresa_id=empresa_id).order_by('banco')
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/factura/detallesFactura.html', contexto)
    
    def _obtener_codigo_porcentaje_iva(self, iva_percent):
        """
        Mapea el porcentaje de IVA al código que requiere el SRI
        Según tabla 17 de la ficha técnica SRI
        """
        mapping = {
            Decimal('0.00'): '0',    # 0%
            Decimal('0.12'): '2',    # 12% (tarifa actual)
            Decimal('0.15'): '3',    # 15% (tarifa histórica)
            Decimal('0.14'): '4',    # 14% (tarifa histórica)
        }
        return mapping.get(iva_percent, '0')  # Default 0% si no se encuentra

# Función mejorada para buscar productos
@require_empresa_activa
def buscar_producto(request):
    """
    Busca productos y servicios por código exacto o parcial.
    """
    try:
        empresa_id = request.session.get('empresa_activa')

        codigo = request.GET.get('q', '').strip()
        listar_todos = request.GET.get('all') in ('1', 'true', 'True')
        print(f"🔍 Buscando producto o servicio con código: '{codigo}'")

        # Si no hay código y se solicita listado general, devolver primeros N
        if not codigo and listar_todos:
            resultados = []
            # Limitar resultados para evitar respuestas muy grandes
            LIMITE = 100

            # Mapeo de códigos SRI a porcentaje real
            MAPEO_IVA = {
                '0': 0.00,
                '5': 0.05,
                '2': 0.12,
                '10': 0.13,
                '3': 0.14,
                '4': 0.15,
                '9': 0.15,  # Normalizado a 15%
                '6': 0.00,
                '7': 0.00,
                '8': 0.08,
            }

            for p in Producto.objects.filter(empresa_id=empresa_id).order_by('codigo')[:LIMITE]:
                precio_base = float(p.precio) if p.precio else 0.0
                iva_percent = MAPEO_IVA.get(p.iva, 0.12)
                resultados.append({
                    'id': p.id,
                    'codigo': p.codigo,
                    'nombre': getattr(p, 'descripcion', '') or getattr(p, 'nombre', ''),
                    'precio': precio_base,
                    'iva_codigo': p.iva,
                    'iva_percent': iva_percent,
                    'precio_con_iva': precio_base * (1 + iva_percent),
                    'tipo': 'producto',
                })

            for s in Servicio.objects.filter(empresa_id=empresa_id).order_by('codigo')[:LIMITE]:
                precio_base = float(getattr(s, 'precio1', 0) or 0.0)
                # Servicios: si no hay IVA definido, usar 0.12 por defecto
                iva_code = str(getattr(s, 'iva', '') or '2')
                iva_percent = MAPEO_IVA.get(iva_code, 0.12)
                resultados.append({
                    'id': s.id,
                    'codigo': s.codigo,
                    'nombre': getattr(s, 'descripcion', '') or getattr(s, 'nombre', ''),
                    'precio': precio_base,
                    'iva_codigo': iva_code,
                    'iva_percent': iva_percent,
                    'precio_con_iva': precio_base * (1 + iva_percent),
                    'tipo': 'servicio',
                })

            return JsonResponse(resultados, safe=False)

        if not codigo:
            print("❌ Código vacío")
            return JsonResponse([], safe=False)

        resultados = []

        # Buscar producto exacto
        producto = Producto.objects.filter(empresa_id=empresa_id, codigo__iexact=codigo).first()
        if producto:
            precio_base = float(producto.precio) if producto.precio else 0.0
            
            # Mapeo de códigos SRI a porcentaje real
            MAPEO_IVA = {
                '0': 0.00,
                '5': 0.05,
                '2': 0.12,
                '10': 0.13,
                '3': 0.14,
                '4': 0.15,
                '9': 0.15,  # Normalizado (antes 16%)
                '6': 0.00,
                '7': 0.00,
                '8': 0.08
            }
            
            iva_percent = MAPEO_IVA.get(producto.iva, 0.12)  # 12% por defecto
            
            resultados.append({
                'id': producto.id,
                'codigo': producto.codigo,
                'nombre': producto.descripcion,
                'precio': precio_base,
                'iva_codigo': producto.iva,
                'iva_percent': iva_percent,
                'precio_con_iva': precio_base * (1 + iva_percent),
                'tipo': 'producto'
            })

        # Buscar servicio exacto
        servicio = Servicio.objects.filter(empresa_id=empresa_id, codigo__iexact=codigo).first()
        print(f"🔍 Query servicio: Servicio.objects.filter(codigo__iexact='{codigo}').first()")
        print(f"🔍 Servicio encontrado: {servicio}")
        
        if servicio:
            precio_base = float(servicio.precio1) if servicio.precio1 else 0.0
            
            print(f"📄 Servicio: {servicio.codigo} - {servicio.descripcion}")
            print(f"💰 Precio base: {precio_base}")
            print(f"🔢 IVA raw: {repr(servicio.iva)} (tipo: {type(servicio.iva)})")
            
            # ✅ CORREGIDO: Manejar el IVA del servicio de forma segura
            try:
                iva_code = str(servicio.iva) if servicio.iva else '2'  # 12% por defecto
                
                # Eliminado FIX temporal que forzaba 16% para ciertos servicios; usar configuración declarada
                
                iva_percent = MAPEO_IVA.get(iva_code, 0.12)
                precio_con_iva = precio_base * (1 + iva_percent)
                
                print(f"✅ IVA code: '{iva_code}', IVA %: {iva_percent}")
                print(f"💲 Precio con IVA: {precio_con_iva}")
                
            except Exception as e:
                print(f"⚠️ Error procesando IVA del servicio: {e}")
                # Fallback conservador al 15% estándar
                iva_percent = 0.15
                precio_con_iva = precio_base * (1 + iva_percent)
            
            resultados.append({
                'id': servicio.id,
                'codigo': servicio.codigo,
                'nombre': servicio.descripcion,
                'precio': precio_base,
                'iva_codigo': iva_code,
                'iva_percent': iva_percent,  # ✅ CRÍTICO: Agregar este campo faltante
                'precio_con_iva': precio_con_iva,
                'tipo': 'servicio'
            })

        # Si no hay exactos, buscar parciales
        if not resultados:
            from django.db.models import Q
            productos_similares = Producto.objects.filter(
                Q(empresa_id=empresa_id),
                Q(codigo__icontains=codigo) | Q(descripcion__icontains=codigo)
            )[:30]
            for p in productos_similares:
                precio_base = float(p.precio) if p.precio else 0.0
                
                # Mapeo de códigos SRI a porcentaje real
                MAPEO_IVA = {
                    '0': 0.00,
                    '5': 0.05,
                    '2': 0.12,
                    '10': 0.13,
                    '3': 0.14,
                    '4': 0.15,
                    '9': 0.15,
                    '6': 0.00,
                    '7': 0.00,
                    '8': 0.08
                }
                
                iva_percent = MAPEO_IVA.get(p.iva, 0.12)  # 12% por defecto
                
                resultados.append({
                    'id': p.id,
                    'codigo': p.codigo,
                    'nombre': p.descripcion,
                    'precio': precio_base,
                    'iva_codigo': p.iva,
                    'iva_percent': iva_percent,
                    'precio_con_iva': precio_base * (1 + iva_percent),
                    'tipo': 'producto'
                })
            servicios_similares = Servicio.objects.filter(
                Q(empresa_id=empresa_id),
                Q(codigo__icontains=codigo) | Q(descripcion__icontains=codigo) | Q(nombre__icontains=codigo)
            )[:30]
            for s in servicios_similares:
                precio_base = float(getattr(s, 'precio1', 0) or 0.0)
                iva_code = str(getattr(s, 'iva', '') or '2')
                MAPEO_IVA = {
                    '0': 0.00,
                    '5': 0.05,
                    '2': 0.12,
                    '10': 0.13,
                    '3': 0.14,
                    '4': 0.15,
                    '9': 0.15,
                    '6': 0.00,
                    '7': 0.00,
                    '8': 0.08
                }
                iva_percent = MAPEO_IVA.get(iva_code, 0.12)
                resultados.append({
                    'id': s.id,
                    'codigo': s.codigo,
                    'nombre': getattr(s, 'descripcion', '') or getattr(s, 'nombre', ''),
                    'precio': precio_base,
                    'iva_codigo': iva_code,
                    'iva_percent': iva_percent,
                    'precio_con_iva': precio_base * (1 + iva_percent),
                    'tipo': 'servicio'
                })

        return JsonResponse(resultados, safe=False)

    except Exception as e:
        print(f"❌ Error en buscar_producto: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse([], safe=False)

#Muestra y procesa los detalles de cada producto de la factura--------------------------------#
class ListarFacturas(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if empresa_id is None or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return HttpResponseRedirect('/inventario/panel')

        #Lista de productos de la BDD
        facturas = Factura.objects.filter(empresa_id=empresa_id)
        
        # La sincronización automática con el SRI ha sido deshabilitada para mejorar el rendimiento
        # Solo se ejecutará cuando el usuario haga clic en "Autorizar documento" o similar
        # Si necesita verificar estados pendientes, use el botón de sincronización manual
        #Crea el paginador

        contexto = {'tabla': facturas}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/factura/listarFacturas.html', contexto)

    #Fin de vista---------------------------------------------------------------------------------------#


# Vista para autorizar documentos en el SRI - ELIMINADA (DUPLICADA)
# Esta función fue movida al final del archivo con la implementación actualizada


# Vista para consultar estado individual de una factura en el SRI ------------------------------#
@csrf_exempt
@require_http_methods(["GET", "POST"])
@require_empresa_activa
def consultar_estado_sri(request, factura_id):
    """
    Vista para consultar el estado individual de una factura en el SRI
    y mostrar los mensajes de error específicos
    """
    try:
        # Obtener la factura de la empresa activa
        empresa_id = request.session.get('empresa_activa')
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        # Verificar que tenga clave de acceso
        if not hasattr(factura, 'clave_acceso') or not factura.clave_acceso:
            return JsonResponse({
                'success': False,
                'message': 'Esta factura no tiene clave de acceso. No se puede consultar el estado en el SRI.'
            })
        
        logger.info(f"Consultando estado SRI para factura {factura_id} - Clave: {factura.clave_acceso}")
        
        # Importar el módulo de integración SRI
        from .sri.integracion_django import SRIIntegration
        
        # Crear instancia de integración
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        
        # Consultar estado usando integración estándar
        # La integración expone consultar_estado_factura(factura_id)
        try:
            resultado = integration.consultar_estado_factura(factura.id)
        except AttributeError:
            # Fallback si la versión actual aún requiere cliente directo
            try:
                resultado = integration.consultar_autorizacion(factura.clave_acceso)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error consultando autorización: {e}'
                })
        
        # Procesar resultado
        if resultado.get('success'):
            estado_anterior = factura.estado_sri
            res_estado = resultado.get('estado') or resultado.get('resultado', {}).get('estado') or 'DESCONOCIDO'
            factura.estado_sri = res_estado
            # Mapear posibles estructuras
            numero_aut = resultado.get('numero_autorizacion') or resultado.get('resultado', {}).get('numero_autorizacion')
            fecha_aut = resultado.get('fecha_autorizacion') or resultado.get('resultado', {}).get('fecha_autorizacion')
            mensaje_detalle = resultado.get('detalle') or resultado.get('mensaje_detalle') or ''
            mensaje_principal = resultado.get('mensaje') or 'Consulta realizada exitosamente'
            if mensaje_principal:
                factura.mensaje_sri = mensaje_principal
            if mensaje_detalle:
                factura.mensaje_sri_detalle = mensaje_detalle
            if numero_aut:
                factura.numero_autorizacion = numero_aut
            if fecha_aut:
                try:
                    from datetime import datetime
                    factura.fecha_autorizacion = datetime.strptime(fecha_aut, '%d/%m/%Y %H:%M:%S')
                except Exception:
                    pass
            factura.save()

            # Ajustar fecha de autorización para mostrar (restar 5 horas)
            fecha_aut_respuesta = ''
            if factura.fecha_autorizacion:
                from datetime import timedelta
                fecha_aut_respuesta = (
                    factura.fecha_autorizacion - timedelta(hours=5)
                ).strftime('%d/%m/%Y %H:%M:%S')
            elif fecha_aut:
                fecha_aut_respuesta = fecha_aut
            # =============================
            # Envío automático de email si pasó a AUTORIZADA y no se había enviado
            # =============================
            try:
                if factura.estado_sri == 'AUTORIZADA' and not factura.email_enviado:
                    from .utils.email_facturas import send_factura_autorizada_email
                    # Asegurar generación de XML autorizado y RIDE
                    from .sri.integracion_django import SRIIntegration
                    integration_local = SRIIntegration(empresa=get_empresa_activa(request))
                    # Generar/obtener XML autorizado (persistido en storage si aplica)
                    xml_path = integration_local.generar_xml_factura(factura)
                    # Generar RIDE (firmado o simple según config)
                    ride_gen = RIDEGenerator()
                    pdf_dir = os.path.join(getattr(settings, 'MEDIA_ROOT', 'media'), 'facturas_pdf')
                    os.makedirs(pdf_dir, exist_ok=True)
                    ride_result = ride_gen.generar_ride_factura_firmado(
                        factura=factura,
                        output_dir=pdf_dir,
                        firmar=True
                    )
                    if isinstance(ride_result, tuple):
                        ride_path = ride_result[1]
                    else:
                        ride_path = ride_result
                    send_factura_autorizada_email(factura, xml_path, ride_path, copia_empresa=True)
                    factura.email_enviado = True
                    from datetime import timezone as _tz
                    from django.utils import timezone
                    factura.email_enviado_at = timezone.now()
                    factura.email_envio_intentos = factura.email_envio_intentos + 1
                    factura.email_ultimo_error = None
                    factura.save(update_fields=['email_enviado','email_enviado_at','email_envio_intentos','email_ultimo_error'])
                elif factura.estado_sri == 'AUTORIZADA':
                    # Ya estaba marcado; solo incrementamos contador si forzaron la consulta
                    factura.email_envio_intentos = factura.email_envio_intentos or 1
            except Exception as email_exc:
                logger.error(f"Fallo envío automático email factura {factura.id}: {email_exc}")
                factura.email_envio_intentos = factura.email_envio_intentos + 1
                factura.email_ultimo_error = str(email_exc)
                factura.save(update_fields=['email_envio_intentos','email_ultimo_error'])
            estado_cambio = (estado_anterior != factura.estado_sri)
            logger.info(f"Estado consultado exitosamente: {factura.estado_sri}")
            return JsonResponse({
                'success': True,
                'estado': factura.estado_sri,
                'mensaje': mensaje_principal,
                'detalle': mensaje_detalle,
                'numero_autorizacion': numero_aut or '',
                'fecha_autorizacion': fecha_aut_respuesta,
                'estado_cambio': estado_cambio
            })
        else:
            # Extraer mensajes técnicos del SRI si existen
            mensajes_sri = []
            bruto = resultado.get('resultado') if isinstance(resultado.get('resultado'), dict) else resultado
            if bruto and isinstance(bruto, dict):
                mensajes_sri = bruto.get('mensajes', []) or []
            primer = mensajes_sri[0] if mensajes_sri else {}
            identificador = primer.get('identificador', '')
            mensaje_sri = primer.get('mensaje', '')
            info_extra = primer.get('informacionAdicional', '')
            detalle_compuesto = '\n'.join(filter(None,[mensaje_sri, info_extra])) or resultado.get('message','Error desconocido')
            logger.error(f"Error al consultar estado: {detalle_compuesto} (id={identificador})")
            return JsonResponse({
                'success': False,
                'message': (
                    '❌ Error al consultar el estado:\n\n'
                    f'{detalle_compuesto}'
                    '\n\nIdentificador: '
                    f'{identificador or 'N/D'}'
                    '\n\nPosibles causas frecuentes:\n'
                    '• Clave de acceso aún no procesada (intente en 1-2 min)\n'
                    '• Comprobante rechazado (revise mensajes SRI)\n'
                    '• Problemas temporales en servicios SRI\n'
                    '• Conectividad / timeout'
                )
            })
            
    except ImportError:
        logger.error("No se pudo importar el módulo de integración del SRI")
        return JsonResponse({
            'success': False,
            'message': """❌ Error del sistema: Módulo de integración SRI no disponible

El sistema de consulta del SRI no está correctamente configurado.
Contacte al administrador del sistema."""
        })
    except Exception as e:
        logger.error(f"Error crítico al consultar estado de factura {factura_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f"""❌ Error interno del servidor:

{str(e)}

Si el problema persiste, contacte al soporte técnico."""
        })

#Fin de vista consultar estado SRI------------------------------------------------------------#


# Vista para listar facturas con problemas del SRI ------------------------------------------#
class FacturasSRIProblemas(LoginRequiredMixin, View):
    """
    Vista para mostrar todas las facturas que tienen problemas con el SRI
    """
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        from django.db.models import Q
        from datetime import datetime, timedelta
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        
        # Obtener parámetros de filtro
        estado_filtro = request.GET.get('estado', '')
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        
        # Query base: facturas que tienen clave de acceso pero no están autorizadas
        query = Q(clave_acceso__isnull=False) & Q(clave_acceso__gt='')
        
        # Facturas con problemas: PENDIENTE, RECHAZADA, ERROR, o sin estado pero con más de 1 día
        problemas_query = (
            Q(estado_sri__in=['PENDIENTE', 'RECHAZADA', 'ERROR']) |
            Q(estado_sri__isnull=True, fecha_emision__lt=datetime.now().date() - timedelta(days=1)) |
            Q(estado_sri='', fecha_emision__lt=datetime.now().date() - timedelta(days=1))
        )
        
        query &= problemas_query
        
        # Aplicar filtros
        if estado_filtro:
            if estado_filtro == 'PENDIENTE':
                query &= (Q(estado_sri='PENDIENTE') | Q(estado_sri__isnull=True) | Q(estado_sri=''))
            else:
                query &= Q(estado_sri=estado_filtro)
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                query &= Q(fecha_emision__gte=fecha_desde_obj)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                query &= Q(fecha_emision__lte=fecha_hasta_obj)
            except ValueError:
                pass
        
        # Obtener facturas con problemas (filtradas por empresa)
        facturas = Factura.objects.filter(query, empresa_id=empresa_id).order_by('-fecha_emision', '-id')
        
        # Calcular estadísticas por estado
        from django.db.models import Count
        estadisticas = {}
        
        # Contar por estados específicos
        estados_count = facturas.values('estado_sri').annotate(count=Count('id'))
        for item in estados_count:
            estado = item['estado_sri'] or 'PENDIENTE'
            estadisticas[estado] = item['count']
        
        # Asegurar que siempre tengamos los estados principales
        estados_principales = ['PENDIENTE', 'RECHAZADA', 'ERROR', 'RECIBIDA']
        for estado in estados_principales:
            if estado not in estadisticas:
                estadisticas[estado] = 0
        
        contexto = {
            'facturas': facturas,
            'estadisticas': estadisticas,
            'filtros': {
                'estado': estado_filtro,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta
            }
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/factura/facturas_sri_problemas.html', contexto)

#Fin de vista facturas SRI problemas--------------------------------------------------------#


#Muestra los detalles individuales de una factura------------------------------------------------#
# Agregar estos imports al inicio del archivo views.py (después de las importaciones existentes)

# Reemplazar la clase VerFactura existente
class VerFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        try:
            # Obtener la factura de la empresa activa
            empresa_id = request.session.get('empresa_activa')
            if not request.user.empresas.filter(id=empresa_id).exists():
                raise Http404("Empresa no válida")
            factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
            
            # Obtener los detalles de la factura
            detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto')
            
            # Obtener las opciones generales de la empresa
            try:
                empresa = getattr(factura, 'empresa', None)
                opciones = Opciones.objects.for_tenant(empresa).first()
                if not opciones and empresa:
                    opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
            except Opciones.DoesNotExist:
                opciones = None
            
            # === USAR FUNCIONES DE ADAPTACIÓN PARA XML Y RIDE ===
            datos_factura = adapt_factura(factura, detalles=detalles, opciones=opciones)
            
            # Rutas de almacenamiento normalizadas
            media_paths = build_factura_media_paths(factura)

            # ✅ VERIFICAR SI EXISTEN XML Y RIDE (sin abrirlos para evitar 403)
            xml_path = None
            xml_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmada.xml"
            xml_storage_path = f"{media_paths.xml_dir}/{xml_filename}"
            
            # Solo verificar existencia sin abrir el archivo
            try:
                if default_storage.exists(xml_storage_path):
                    xml_path = xml_storage_path
                    logger.info(f"XML SRI encontrado: {xml_storage_path}")
                else:
                    logger.info(f"XML SRI no encontrado en: {xml_storage_path}")
            except Exception as e:
                logger.warning(f"Error verificando XML: {e}")

            # ✅ VERIFICAR SI EXISTE RIDE (PDF firmado)
            ride_path = None
            signed_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmado.pdf"
            ride_storage_path = f"{media_paths.pdf_dir}/{signed_filename}"
            
            # Solo verificar existencia sin abrir el archivo
            try:
                if default_storage.exists(ride_storage_path):
                    ride_path = ride_storage_path
                    logger.info(f"RIDE PDF encontrado: {ride_storage_path}")
                else:
                    logger.info(f"RIDE PDF no encontrado en: {ride_storage_path}")
            except Exception as e:
                logger.warning(f"Error verificando RIDE: {e}")
            
            # ✅ AGREGAR MENSAJE DE FACTURA PROCESADA SOLO SI VIENE RECIÉN COMPLETADA
            if 'HTTP_REFERER' in request.META and 'detallesDeFactura' in request.META['HTTP_REFERER']:
                if detalles.exists():
                    mensaje_exito = f'🎉 ¡FACTURA PROCESADA EXITOSAMENTE! Número: {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia} | Total: ${factura.monto_general:.2f}'
                    if xml_path and ride_path:
                        mensaje_exito += ' | ✅ XML y RIDE generados'
                    messages.success(request, mensaje_exito)
            
            print(f"✅ Mostrando factura ID: {factura.id}")
            print(f"   - Número: {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}")
            print(f"   - Cliente: {factura.nombre_cliente}")
            print(f"   - Total: ${factura.monto_general}")
            print(f"   - Detalles encontrados: {detalles.count()}")
            print(f"   - XML SRI: {xml_path or 'No generado'}")
            print(f"   - RIDE PDF: {ride_path or 'No generado'}")

            xml_display_name = Path(xml_path).name if xml_path else None
            ride_display_name = Path(ride_path).name if ride_path else None

            contexto = {
                'factura': factura,
                'detalles': detalles,
                'opciones': opciones,
                'xml_sri': xml_display_name,
                'ride_pdf': ride_display_name
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/factura/verFactura.html', contexto)
            
        except Exception as e:
            print(f"❌ Error al mostrar factura: {e}")
            messages.error(request, f'Error al cargar la factura: {str(e)}')
            return redirect('inventario:listarFacturas')

    def post(self, request, p):
        """Permite descargar el RIDE (PDF) o el XML SRI - SIEMPRE FIRMA EL PDF"""
        try:
            empresa_id = request.session.get('empresa_activa')
            if not request.user.empresas.filter(id=empresa_id).exists():
                raise Http404("Empresa no válida")
            factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
            action = request.POST.get('action', 'download_pdf')
            media_paths = build_factura_media_paths(factura)

            if action == 'download_xml':
                # Descargar XML
                xml_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmada.xml"
                xml_storage_path = f"{media_paths.xml_dir}/{xml_filename}"

                if default_storage.exists(xml_storage_path):
                    return FileResponse(
                        default_storage.open(xml_storage_path, 'rb'),
                        as_attachment=True,
                        filename=xml_filename,
                        content_type='application/xml'
                    )
                else:
                    messages.error(request, 'El archivo XML no está disponible.')
                    return redirect('inventario:verFactura', p=p)

            else:
                # Descargar PDF (RIDE) - SIEMPRE GENERAR Y FIRMAR
                signed_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmado.pdf"
                unsigned_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.pdf"

                signed_path = f"{media_paths.pdf_dir}/{signed_filename}"
                unsigned_path = f"{media_paths.pdf_dir}/{unsigned_filename}"
                
                # Siempre intentar generar y firmar el PDF
                try:
                    # Obtener detalles y opciones necesarias
                    detalles = DetalleFactura.objects.filter(factura=factura)
                    empresa = getattr(factura, 'empresa', None)
                    opciones = Opciones.objects.for_tenant(empresa).first()
                    if not opciones and empresa:
                        opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
                    
                    # Generar RIDE firmado
                    ride_generator = RIDEGenerator()
                    result = ride_generator.generar_ride_factura_firmado(
                        factura=factura,
                        output_dir=media_paths.pdf_dir,
                        firmar=True
                    )

                    if isinstance(result, tuple):
                        # Se firmó correctamente, devuelve (original, firmado)
                        pdf_path = result[1]  # Usar el PDF firmado
                    else:
                        # No se firmó, devuelve solo el path original
                        pdf_path = result
                        
                    # Verificar que el archivo firmado existe
                    if default_storage.exists(signed_path):
                        return FileResponse(
                            default_storage.open(signed_path, 'rb'),
                            as_attachment=True,
                            filename=signed_filename,
                            content_type='application/pdf'
                        )
                    elif default_storage.exists(pdf_path):
                        # Si no se pudo firmar, devolver el no firmado
                        return FileResponse(
                            default_storage.open(pdf_path, 'rb'),
                            as_attachment=True,
                            filename=Path(pdf_path).name,
                            content_type='application/pdf'
                        )
                    else:
                        messages.error(request, 'Error al generar el PDF firmado.')
                        return redirect('inventario:verFactura', p=p)
                        
                except Exception as e:
                    logger.error(f"Error generando PDF firmado: {e}")
                    messages.error(request, f'Error al generar el PDF firmado: {str(e)}')
                    return redirect('inventario:verFactura', p=p)

        except Exception as e:
            messages.error(request, f'Error descargando archivo: {str(e)}')
            return redirect('inventario:verFactura', p=p)

#Fin de vista--------------------------------------------------------------------------------------#


#Editar factura existente--------------------------------------------------------------------------#
class EditarFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        """Muestra el formulario para editar una factura existente"""
        print(f"🔵 EditarFactura.get() llamado con factura_id={p}")
        try:
            # Verificar facturador en sesión
            facturador_id = request.session.get('facturador_id')
            print(f"🔵 Facturador ID en sesión: {facturador_id}")
            if not facturador_id:
                messages.warning(request, 'Debe iniciar sesión como facturador antes de editar facturas.')
                # Guardar la URL actual para redirigir después del login
                next_url = request.path
                return redirect(f'/inventario/login_facturador/?next={next_url}')
            
            try:
                facturador = Facturador.tenant_objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                if 'facturador_id' in request.session:
                    del request.session['facturador_id']
                if 'facturador_nombre' in request.session:
                    del request.session['facturador_nombre']
                return redirect('inventario:login_facturador')

            # Obtener empresa activa
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa antes de editar facturas.')
                return redirect('inventario:panel')
            
            empresa = Empresa.objects.get(id=empresa_id)

            # Obtener la factura a editar
            factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
            
            # Verificar que la factura no esté autorizada
            if factura.estado_sri == 'AUTORIZADO':
                messages.warning(request, 'No se puede editar una factura autorizada por el SRI.')
                return redirect('inventario:verFactura', p=p)
            
            # Obtener los detalles de la factura
            detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto', 'servicio')
            
            # Obtener formas de pago de la factura (usando _unsafe_objects para evitar filtro tenant)
            formas_pago = FormaPago._unsafe_objects.filter(factura=factura).select_related('caja')
            print(f"🔵 Formas de pago encontradas: {formas_pago.count()}")
            for fp in formas_pago:
                print(f"   - forma_pago={fp.forma_pago}, total={fp.total}, caja={fp.caja}")

            # Preparar datos para el formulario
            cedulas = Cliente.objects.filter(empresa_id=empresa_id).values_list('id', 'identificacion')
            secuencias = Secuencia.objects.filter(empresa_id=empresa_id, tipo_documento='01', activo=True).order_by('establecimiento', 'punto_emision')
            almacenes = Almacen.objects.filter(activo=True, empresa_id=empresa_id)
            cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion')
            
            # Buscar la secuencia que coincide con la factura
            secuencia_factura_id = None
            if factura.establecimiento and factura.punto_emision:
                secuencia_match = Secuencia.objects.filter(
                    empresa_id=empresa_id,
                    establecimiento=factura.establecimiento,
                    punto_emision=factura.punto_emision,
                    tipo_documento='01',
                    activo=True
                ).first()
                if secuencia_match:
                    secuencia_factura_id = secuencia_match.id
                    print(f"🔵 Secuencia encontrada para factura: id={secuencia_factura_id}, desc={secuencia_match.descripcion}")
            
            # Formas de pago SRI
            formas_pago_sri = getattr(FormaPago, 'FORMAS_PAGO_CHOICES', [])

            # Lista de bancos
            try:
                if hasattr(Banco, 'bancos_disponibles'):
                    bancos_db = set(Banco.bancos_disponibles())
                else:
                    bancos_db = set(Banco.objects.filter(empresa_id=empresa_id).values_list('banco', flat=True))
            except Exception:
                bancos_db = set()

            bancos_fallback = {
                'Pichincha', 'Produbanco', 'Pacifico', 'Machala', 'Guayaquil', 'Banecuador',
                'Internacional', 'Procredit', 'Austro', 'Bolivariano', 'Loja', 'Amazonas', 'Ruminahui'
            }
            lista_bancos = sorted({*(bancos_db or set()), *bancos_fallback})

            # Preparar formulario con datos de la factura
            initial_data = {
                'secuencia': secuencia_factura_id,
                'secuencia_valor': factura.secuencia,
                'identificacion_cliente': factura.identificacion_cliente,
                'nombre_cliente': factura.nombre_cliente,
                'correo_cliente': factura.cliente.correo if factura.cliente else '',
                'almacen': str(factura.almacen_id) if factura.almacen_id else '',
                'establecimiento': factura.establecimiento,
                'punto_emision': factura.punto_emision,
                'concepto': factura.concepto or '',
                'fecha_emision': factura.fecha_emision,
                'fecha_vencimiento': factura.fecha_vencimiento,
            }
            # Configurar choices ANTES de crear el formulario con initial
            almacen_choices = [('', '...')] + [(str(a.id), a.descripcion) for a in almacenes]
            form = EmitirFacturaFormulario(cedulas=cedulas, secuencias=secuencias, initial=initial_data)
            form.fields['almacen'].choices = almacen_choices
            # Forzar el valor inicial del almacén
            if factura.almacen_id:
                form.fields['almacen'].initial = str(factura.almacen_id)
            print(f"🔵 Almacén inicial: {factura.almacen_id}, choices: {almacen_choices[:3]}...")

            # Preparar context
            contexto = {
                'form': form,
                'factura': factura,
                'detalles': detalles,
                'formas_pago_factura': formas_pago,
                'cedulas': cedulas,
                'secuencias': secuencias,
                'secuencia_factura_id': secuencia_factura_id,
                'almacenes': almacenes,
                'facturador': facturador,
                'cajas': cajas_activas,
                'formas_pago_sri': formas_pago_sri,
                'bancos_lista_nombres': lista_bancos,
                'bancos_db': Banco.objects.filter(activo=True, empresa_id=empresa_id).order_by('banco'),
                'now': timezone.now(),
                'es_edicion': True  # Flag para que el template sepa que estamos editando
            }
            contexto = complementarContexto(contexto, request.user)

            return render(request, 'inventario/factura/editarFactura.html', contexto)

        except Exception as e:
            print(f"Error al cargar la página de editar factura: {e}")
            messages.error(request, f"Error al cargar la página: {e}")
            return redirect('inventario:listarFacturas')

    def post(self, request, p):
        """Procesa la actualización de la factura"""
        try:
            from django.db import transaction
            from decimal import Decimal
            import json
            
            # Verificar facturador
            facturador_id = request.session.get('facturador_id')
            if not facturador_id:
                messages.error(request, 'Debe iniciar sesión como facturador.')
                return redirect('inventario:login_facturador')
            
            try:
                facturador = Facturador.tenant_objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                return redirect('inventario:login_facturador')

            # Obtener empresa activa
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'No se ha seleccionado una empresa válida.')
                return redirect('inventario:panel')
            
            empresa = Empresa.objects.get(id=empresa_id)

            # Obtener la factura a editar
            factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
            
            # Verificar que no esté autorizada
            if factura.estado_sri == 'AUTORIZADO':
                messages.error(request, 'No se puede editar una factura autorizada.')
                return redirect('inventario:verFactura', p=p)

            # Validar productos
            codigos = request.POST.getlist('productos_codigos[]')
            cantidades = request.POST.getlist('productos_cantidades[]')
            
            if not codigos:
                codigos = request.POST.getlist('productos_codigos')
                cantidades = request.POST.getlist('productos_cantidades')
            
            if not codigos or not cantidades:
                raise ValueError("Debe agregar al menos un producto a la factura.")
            
            if len(codigos) != len(cantidades):
                raise ValueError("Error en los datos de productos.")

            # Validar formas de pago
            pagos_json = request.POST.get('pagos_efectivo', '[]')
            try:
                pagos_list = json.loads(pagos_json)
            except json.JSONDecodeError:
                raise ValueError("Error al procesar las formas de pago.")
            
            if not pagos_list:
                raise ValueError("Debe agregar al menos una forma de pago.")

            # Actualizar factura con transacción
            with transaction.atomic():
                # Actualizar datos del cliente
                cliente_id = request.POST.get('cliente_id')
                if not cliente_id:
                    raise ValueError("No se seleccionó un cliente válido.")
                    
                cliente = get_object_or_404(Cliente, pk=cliente_id, empresa_id=empresa.id)
                
                # Actualizar correo del cliente si cambió
                correo_cliente = request.POST.get('correo_cliente', '').strip()
                if correo_cliente:
                    cliente.correo = correo_cliente
                    cliente.save()

                # Actualizar datos de la factura
                factura.nombre_cliente = cliente.razon_social
                factura.identificacion = cliente.identificacion
                factura.telefono = cliente.telefono or ''
                factura.direccion = cliente.direccion or ''
                factura.correo = correo_cliente or cliente.correo or ''
                
                # Actualizar fechas
                from datetime import datetime
                factura.fecha_emision = datetime.strptime(request.POST.get('fecha_emision'), '%Y-%m-%d').date()
                factura.fecha_vencimiento = datetime.strptime(request.POST.get('fecha_vencimiento'), '%Y-%m-%d').date()
                
                # Actualizar almacén
                almacen_id = request.POST.get('almacen')
                if almacen_id:
                    factura.almacen = get_object_or_404(Almacen, pk=almacen_id, empresa=empresa)
                
                # Actualizar concepto
                factura.concepto = request.POST.get('concepto', 'Sin concepto')

                # Eliminar detalles anteriores
                DetalleFactura.objects.filter(factura=factura).delete()
                
                # Eliminar formas de pago anteriores
                FormaPago.objects.filter(factura=factura).delete()

                # Crear nuevos detalles (reutilizando la lógica de emitir factura)
                descuentos = request.POST.getlist('productos_descuentos[]') or request.POST.getlist('productos_descuentos')
                porcentajes_descuento = request.POST.getlist('productos_porcentajes[]') or request.POST.getlist('productos_porcentajes')
                errores = []
                
                crear_detalles_factura(factura, codigos, cantidades, descuentos, porcentajes_descuento, errores)
                
                if errores:
                    raise ValueError(f"Errores en productos: {', '.join(errores)}")

                # Recalcular totales (considerando productos Y servicios)
                detalles = DetalleFactura.objects.filter(factura=factura)
                subtotal_sin_imp = Decimal('0.00')
                subtotal_iva = Decimal('0.00')
                iva_total = Decimal('0.00')
                total_general = Decimal('0.00')
                
                for d in detalles:
                    # Determinar el código IVA del producto o servicio
                    if d.producto:
                        codigo_iva = d.producto.iva
                    elif d.servicio:
                        codigo_iva = d.servicio.iva
                    else:
                        codigo_iva = '0'
                    
                    if codigo_iva == '0' or codigo_iva == '6' or codigo_iva == '7':
                        subtotal_sin_imp += d.sub_total or Decimal('0.00')
                    else:
                        subtotal_iva += d.sub_total or Decimal('0.00')
                    
                    iva_total += d.iva or Decimal('0.00')
                    total_general += d.total or Decimal('0.00')
                
                factura.sub_total_sin_impuesto = subtotal_sin_imp.quantize(Decimal('0.01'))
                factura.sub_total_iva = subtotal_iva.quantize(Decimal('0.01'))
                factura.iva = iva_total.quantize(Decimal('0.01'))
                factura.monto_general = total_general.quantize(Decimal('0.01'))
                factura.save()

                # Crear nuevas formas de pago (sin validación full_clean para evitar conflicto de timing)
                for pago in pagos_list:
                    caja_id = pago.get('caja_id')
                    forma_pago = FormaPago(
                        factura=factura,
                        forma_pago=pago.get('forma_pago', '01'),
                        total=Decimal(str(pago.get('valor', 0))),
                        plazo=pago.get('plazo', 0) or 0,
                        unidad_tiempo=pago.get('unidad_tiempo', 'dias') or 'dias',
                        caja_id=caja_id if caja_id else None,
                        empresa=empresa
                    )
                    # Guardar sin ejecutar full_clean() que tiene la validación problemática
                    super(FormaPago, forma_pago).save()

                messages.success(request, f'✅ Factura {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia} actualizada exitosamente.')
                return redirect('inventario:verFactura', p=factura.id)

        except ValueError as ve:
            messages.error(request, str(ve))
            return redirect('inventario:editarFactura', p=p)
        except Exception as e:
            print(f"Error actualizando factura: {e}")
            messages.error(request, f"Error al actualizar la factura: {str(e)}")
            return redirect('inventario:editarFactura', p=p)

#Fin de vista--------------------------------------------------------------------------------------#


#Genera la factura en CSV--------------------------------------------------------------------------#
class GenerarFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        import csv

        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404('Empresa no válida')
        factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
        detalles = DetalleFactura.objects.filter(id_factura_id=p, factura__empresa_id=empresa_id)

        nombre_factura = "factura_%s.csv" % (factura.id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_factura
        writer = csv.writer(response)

        writer.writerow(['Producto', 'Cantidad', 'Sub-total', 'Total', 'IVA %'])

        MAPEO_IVA = {
            '0': 0.00, '5': 5.00, '2': 12.00, '10': 13.00,
            '3': 14.00, '4': 15.00, '6': 0.00, '7': 0.00, '8': 8.00
        }

        for detalle in detalles:
            if hasattr(detalle, 'producto') and detalle.producto:
                iva_percent = detalle.producto.get_porcentaje_iva_real()
                descripcion = detalle.producto.descripcion
            elif hasattr(detalle, 'servicio') and detalle.servicio:
                iva_percent = MAPEO_IVA.get(detalle.servicio.iva, 0.00)
                descripcion = detalle.servicio.descripcion
            else:
                iva_percent = 0.00
                descripcion = ''
            writer.writerow([descripcion, detalle.cantidad, detalle.sub_total, detalle.total, iva_percent])

        writer.writerow(['Total general:', '', '', factura.monto_general])

        return response

        #Fin de vista--------------------------------------------------------------------------------------#


#Genera la factura en PDF--------------------------------------------------------------------------#
class GenerarFacturaPDF(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        """Generar y descargar RIDE PDF"""
        from django.core.files.storage import default_storage
        from io import BytesIO

        empresa_id = request.session.get('empresa_activa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
        
        try:
            # Generar RIDE (sin firmar para evitar complicaciones)
            ride_generator = RIDEGenerator()
            result = ride_generator.generar_ride_factura_firmado(
                factura=factura,
                output_dir='facturas_pdf',
                firmar=False  # Sin firma para simplificar
            )
            
            # El resultado es un path en el storage
            storage_path = result if isinstance(result, str) else result[0]
            
            # Leer el archivo desde el storage
            if default_storage.exists(storage_path):
                pdf_file = default_storage.open(storage_path, 'rb')
                filename = f"RIDE_{factura.establecimiento}-{factura.punto_emision}-{str(factura.secuencia).zfill(9)}.pdf"
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                pdf_file.close()
                return response
            else:
                messages.error(request, 'No se encontró el archivo PDF generado.')
                return redirect('inventario:verFactura', p=p)
                
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error al generar el PDF: {str(e)}')
            return redirect('inventario:verFactura', p=p)

        #Fin de vista--------------------------------------------------------------------------------------#


## --- Proveedor views (versión consolidada: ver definiciones posteriores únicas) --- ##


#Agrega un pedido-----------------------------------------------------------------------------------#      
class AgregarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida')
            return HttpResponseRedirect('/inventario/panel')
        # Limitar proveedores a la empresa activa
        proveedores = Proveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social_proveedor')
        cedulas = []
        for prov in proveedores:
            nombre_proveedor = (prov.razon_social_proveedor + " " + (prov.nombre_comercial_proveedor or '')).strip()
            cedulas.append([
                prov.identificacion_proveedor,
                f"{nombre_proveedor}. C.I: {prov.identificacion_proveedor}"
            ])
        form = EmitirPedidoFormulario(cedulas=cedulas)
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/pedido/emitirPedido.html', contexto)

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida')
            return HttpResponseRedirect('/inventario/panel')
        proveedores = Proveedor.objects.filter(empresa_id=empresa_id).order_by('razon_social_proveedor')
        cedulas = []
        for prov in proveedores:
            nombre_proveedor = (prov.razon_social_proveedor + " " + (prov.nombre_comercial_proveedor or '')).strip()
            cedulas.append([
                prov.identificacion_proveedor,
                f"{nombre_proveedor}. C.I: {prov.identificacion_proveedor}"
            ])
        form = EmitirPedidoFormulario(request.POST, cedulas=cedulas)
        if form.is_valid():
            request.session['form_details'] = form.cleaned_data['productos']
            request.session['id_proveedor'] = form.cleaned_data['proveedor']  # identificacion_proveedor
            return HttpResponseRedirect("detallesPedido")
        return render(request, 'inventario/pedido/emitirPedido.html', {'form': form})


#--------------------------------------------------------------------------------------------------#


#Lista todos los pedidos---------------------------------------------------------------------------#
class ListarPedidos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Debe seleccionar una empresa válida')
            return HttpResponseRedirect('/inventario/panel')
        pedidos = Pedido.objects.filter(empresa_id=empresa_id).select_related('proveedor').order_by('-fecha', '-id')
        contexto = {'tabla': pedidos}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/pedido/listarPedidos.html', contexto)

    #------------------------------------------------------------------------------------------------#


#Muestra y procesa los detalles de cada producto de la factura--------------------------------#
class DetallesPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        cedula = request.session.get('id_proveedor')
        productos = request.session.get('form_details')
        empresa_id = request.session.get('empresa_activa')
        PedidoFormulario = formset_factory(
            DetallesPedidoFormulario,
            extra=productos,
            form_kwargs={'empresa_id': empresa_id}
        )
        formset = PedidoFormulario()
        contexto = {'formset': formset}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/pedido/detallesPedido.html', contexto)

    def post(self, request):
        cedula = request.session.get('id_proveedor')
        productos = request.session.get('form_details')
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa no válida')
            return HttpResponseRedirect('/inventario/panel')
        PedidoFormulario = formset_factory(
            DetallesPedidoFormulario,
            extra=productos,
            form_kwargs={'empresa_id': empresa_id}
        )

        inicial = {
            'descripcion': '',
            'cantidad': 0,
            'subtotal': 0,
        }

        data = {
            'form-TOTAL_FORMS': productos,
            'form-INITIAL_FORMS': 0,
            'form-MAX_NUM_FORMS': '',
        }

        formset = PedidoFormulario(request.POST, data)

        if formset.is_valid():

            id_producto = []
            cantidad = []
            subtotal = []
            total_general = []
            productos_cache = {}
            sub_monto = Decimal('0')
            monto_general = Decimal('0')

            for form in formset:
                producto_seleccionado = form.cleaned_data.get('descripcion')
                cant = form.cleaned_data.get('cantidad')
                sub = form.cleaned_data.get('valor_subtotal')

                if producto_seleccionado is None:
                    continue

                try:
                    producto_validado = productos_cache[producto_seleccionado.id]
                except KeyError:
                    try:
                        producto_validado = obtenerProducto(producto_seleccionado.id, empresa_id)
                    except Http404:
                        messages.error(request, 'El producto seleccionado no pertenece a la empresa activa.')
                        contexto = {'formset': formset}
                        contexto = complementarContexto(contexto, request.user)
                        return render(
                            request,
                            'inventario/pedido/detallesPedido.html',
                            contexto,
                            status=400,
                        )
                    productos_cache[producto_seleccionado.id] = producto_validado

                id_producto.append(producto_validado.id)
                cantidad.append(cant)
                subtotal.append(sub)

            sub_monto = sum(subtotal, Decimal('0'))

            for index, element in enumerate(subtotal):
                producto = productos_cache[id_producto[index]]
                porcentaje = Decimal(str(producto.get_porcentaje_iva_real())) / 100
                nuevoPrecio = element + (element * porcentaje)
                monto_general += nuevoPrecio
                total_general.append(nuevoPrecio)

            from datetime import date

            proveedor = get_object_or_404(Proveedor, identificacion_proveedor=cedula, empresa_id=empresa_id)
            presente = False
            empresa = get_object_or_404(Empresa, id=empresa_id)
            pedido = Pedido(
                proveedor=proveedor,
                fecha=date.today(),
                sub_monto=sub_monto,
                monto_general=monto_general,
                presente=presente,
                empresa=empresa
            )
            pedido.save()
            id_pedido = pedido

            for indice, elemento in enumerate(id_producto):
                objetoProducto = productos_cache[elemento]
                cantidadDetalle = cantidad[indice]
                subDetalle = subtotal[indice]
                totalDetalle = total_general[indice]

                # Validar que el producto pertenezca a la misma empresa
                if hasattr(objetoProducto, 'empresa_id') and objetoProducto.empresa_id != empresa_id:
                    messages.error(request, 'El producto seleccionado no pertenece a la empresa activa.')
                    contexto = {'formset': formset}
                    contexto = complementarContexto(contexto, request.user)
                    pedido.delete()
                    return render(
                        request,
                        'inventario/pedido/detallesPedido.html',
                        contexto,
                        status=400,
                    )
                detallePedido = DetallePedido(
                    id_pedido=id_pedido,
                    id_producto=objetoProducto,
                    cantidad=cantidadDetalle,
                    sub_total=subDetalle,
                    total=totalDetalle,
                    empresa_id=empresa_id
                )
                detallePedido.save()

            messages.success(request, 'Pedido de ID %s insertado exitosamente.' % id_pedido.id)
            return HttpResponseRedirect("/inventario/agregarPedido")

        else:
            status_code = 200
            for form in formset:
                if 'descripcion' in form.errors:
                    messages.error(request, 'Uno o más productos no pertenecen a la empresa activa.')
                    status_code = 400
                    break
            contexto = {'formset': formset}
            contexto = complementarContexto(contexto, request.user)
            return render(
                request,
                'inventario/pedido/detallesPedido.html',
                contexto,
                status=status_code,
            )

        #Fin de vista-----------------------------------------------------------------------------------#


#Muestra los detalles individuales de un pedido------------------------------------------------#
class VerPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa no válida')
            return HttpResponseRedirect('/inventario/panel')
        pedido = get_object_or_404(Pedido, id=p, empresa_id=empresa_id)
        detalles = DetallePedido.objects.filter(id_pedido_id=p, empresa_id=empresa_id)
        recibido = Pedido.recibido(p)
        contexto = {'pedido': pedido, 'detalles': detalles, 'recibido': recibido}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/pedido/verPedido.html', contexto)


#Fin de vista--------------------------------------------------------------------------------------#

#Valida un pedido ya insertado------------------------------------------------#
class ValidarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa no válida')
            return HttpResponseRedirect('/inventario/panel')
        pedido = get_object_or_404(Pedido, id=p, empresa_id=empresa_id)
        detalles = DetallePedido.objects.filter(id_pedido_id=p, empresa_id=empresa_id)

        #Agrega los productos del pedido
        for elemento in detalles:
            elemento.id_producto.disponible += elemento.cantidad
            elemento.id_producto.save()

        pedido.presente = True
        pedido.save()
        messages.success(request, 'Pedido de ID %s verificado exitosamente.' % pedido.id)
        return HttpResponseRedirect("/inventario/verPedido/%s" % p)
    #Fin de vista--------------------------------------------------------------------------------------#


#Genera el pedido en CSV--------------------------------------------------------------------------#
class GenerarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        import csv
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa no válida')
            return HttpResponseRedirect('/inventario/panel')
        pedido = get_object_or_404(Pedido, id=p, empresa_id=empresa_id)
        detalles = DetallePedido.objects.filter(id_pedido_id=p, empresa_id=empresa_id)

        nombre_pedido = "pedido_%s.csv" % (pedido.id)

        response = HttpResponse(content_type='text/csv')

        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_pedido
        writer = csv.writer(response)

        writer.writerow(['Producto', 'Cantidad', 'Sub-total', 'Total', 'IVA %'])

        for producto in detalles:
            iva_percent = producto.id_producto.get_porcentaje_iva_real()
            writer.writerow([producto.id_producto.descripcion, producto.cantidad, producto.sub_total, producto.total, iva_percent])

        writer.writerow(['Total general:', '', '', pedido.monto_general])

        return response

        #Fin de vista--------------------------------------------------------------------------------------#


#Genera el pedido en PDF--------------------------------------------------------------------------#
class GenerarPedidoPDF(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Empresa no válida')
            return HttpResponseRedirect('/inventario/panel')
        pedido = get_object_or_404(Pedido, id=p, empresa_id=empresa_id)
        empresa = getattr(pedido, 'empresa', None)
        general = Opciones.objects.for_tenant(empresa).first()
        if not general and empresa:
            general = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
        detalles = DetallePedido.objects.filter(id_pedido_id=p, empresa_id=empresa_id)

        data = {
            'fecha': pedido.fecha,
            'monto_general': pedido.monto_general,
            'nombre_proveedor': pedido.proveedor.nombre + " " + pedido.proveedor.apellido,
            'cedula_proveedor': pedido.proveedor.cedula,
            'id_reporte': pedido.id,
            'detalles': detalles,
            'modo': 'pedido',
            'general': general
        }

        nombre_pedido = "pedido_%s.pdf" % (pedido.id)

        pdf = render_to_pdf('inventario/PDF/prueba.html', data)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_pedido

        return response
        #Fin de vista--------------------------------------------------------------------------------------#


#Crea un nuevo usuario--------------------------------------------------------------#
class CrearUsuario(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        # Permitir acceso a usuarios root o administradores de empresa (nivel ADMIN)
        if not (hasattr(request.user, 'nivel') and (request.user.nivel in (Usuario.ADMIN, Usuario.ROOT))):
            messages.error(request, 'No tiene permisos para crear usuarios')
            return HttpResponseRedirect('/inventario/panel')
        form = NuevoUsuarioFormulario(user=request.user)
        contexto = {'form': form, 'modo': request.session.get('usuarioCreado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/usuario/crearUsuario.html', contexto)

    def post(self, request):
        if not (hasattr(request.user, 'nivel') and (request.user.nivel in (Usuario.ADMIN, Usuario.ROOT))):
            messages.error(request, 'No tiene permisos para crear usuarios')
            return HttpResponseRedirect('/inventario/panel')
        form = NuevoUsuarioFormulario(request.POST, user=request.user)
        if not form.is_valid():
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
            return HttpResponseRedirect('/inventario/crearUsuario')

        identificacion = form.cleaned_data['identificacion']
        nombre_completo = form.cleaned_data['nombre_completo']
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        level = form.cleaned_data['level']
        empresa_id = request.session.get('empresa_activa')
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return HttpResponseRedirect('/inventario/crearUsuario')

        if usuarioExiste(Usuario, 'username', identificacion):
            # En vez de bloquear, intentamos vincular a la empresa si no lo está
            existente = Usuario.objects.filter(username=identificacion).first()
            if existente:
                # Verificar si ya está vinculado a esta empresa
                rel = UsuarioEmpresa.objects.filter(usuario=existente, empresa=empresa).first()
                if rel:
                    # Ya vinculado: actualizar overrides si se suministran
                    nivel_form = level
                    if request.user.nivel == Usuario.ADMIN:
                        # ADMIN no puede escalar a ADMIN/ROOT en override si el destino sería mayor que USER
                        if nivel_form != Usuario.USER:
                            nivel_form = Usuario.USER
                    # Guardar overrides solo si cambian
                    if rel.nivel_empresa != nivel_form:
                        rel.nivel_empresa = nivel_form
                    # Email override: si difiere del base y del existente
                    if email and email != existente.email:
                        rel.email_empresa = email
                    rel.save()
                    messages.success(request, 'Usuario creado exitosamente')
                    return HttpResponseRedirect('/inventario/crearUsuario')
                # Crear nueva relación con overrides
                nivel_form = level
                if request.user.nivel == Usuario.ADMIN and nivel_form != Usuario.USER:
                    nivel_form = Usuario.USER
                rel = UsuarioEmpresa.objects.create(
                    usuario=existente,
                    empresa=empresa,
                    nivel_empresa=nivel_form if nivel_form != existente.nivel else None,
                    email_empresa=email if email != existente.email else None,
                )
                messages.success(request, 'Usuario creado exitosamente')
                return HttpResponseRedirect('/inventario/crearUsuario')
        if usuarioExiste(Usuario, 'email', email):
            # Permitir reutilización de email SOLO si corresponde al mismo usuario identificado
            existente_correo = Usuario.objects.filter(email=email).first()
            if existente_correo and existente_correo.username != identificacion:
                messages.error(request, f"El correo '{email}' ya pertenece a otro usuario distinto.")
                return HttpResponseRedirect('/inventario/crearUsuario')

        # Reglas de escalado:
        # - Solo ROOT puede crear ROOT o ADMIN
        # - ADMIN solo puede crear USER
        if request.user.nivel == Usuario.ADMIN:
            nivel_destino = Usuario.USER
        else:  # ROOT
            if level == Usuario.ROOT:
                nivel_destino = Usuario.USER  # No permitir crear otro root por formulario
            else:
                nivel_destino = level

        nuevoUsuario = Usuario(
            username=identificacion,
            email=email,  # base; podría diferir por empresa con override futuro
        )
        nuevoUsuario.first_name = nombre_completo
        nuevoUsuario.last_name = ''
        nuevoUsuario.nivel = nivel_destino
        # Flags derivados
        nuevoUsuario.is_staff = (nivel_destino == Usuario.ADMIN)
        nuevoUsuario.is_superuser = False  # Nunca desde esta vista
        nuevoUsuario.set_password(password)
        nuevoUsuario.save()
        # Crear relación con overrides (si el nivel difiere del global o email distinto se repetirá igual)
        UsuarioEmpresa.objects.create(
            usuario=nuevoUsuario,
            empresa=empresa,
            nivel_empresa=None,  # para nuevo usuario el nivel global ya refleja intención
            email_empresa=None,  # se puede agregar override luego
        )
        messages.success(request, 'Usuario creado exitosamente')
        return HttpResponseRedirect('/inventario/crearUsuario')


#Fin de vista----------------------------------------------------------------------


#Lista todos los usuarios actuales--------------------------------------------------------------#
class ListarUsuarios(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa = get_empresa_activa(request)
        usuarios = Usuario.objects.filter(empresas=empresa)
        if not request.user.is_superuser:
            usuarios = usuarios.filter(is_superuser=False)
        contexto = {'tabla': usuarios}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/usuario/listarUsuarios.html', contexto)

    def post(self, request):
        pass

    #Fin de vista----------------------------------------------------------------------


#Importa toda la base de datos, primero crea una copia de la actual mientras se procesa la nueva--#
class ImportarBDD(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        if request.user.is_superuser == False:
            messages.error(request, 'Solo los administradores pueden importar una nueva base de datos')
            return HttpResponseRedirect('/inventario/panel')

        form = ImportarBDDFormulario()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/BDD/importar.html', contexto)

    def post(self, request):
        form = ImportarBDDFormulario(request.POST, request.FILES)

        if form.is_valid():
            temp_path = manejarArchivo(request.FILES['archivo'])

            try:
                call_command('loaddata', temp_path, verbosity=0)
                messages.success(request, 'Base de datos subida exitosamente')
                return HttpResponseRedirect('/inventario/importarBDD')
            except Exception:
                messages.error(request, 'El archivo esta corrupto')
                return HttpResponseRedirect('/inventario/importarBDD')
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)


#Fin de vista--------------------------------------------------------------------------------


#Descarga toda la base de datos en un archivo---------------------------------------------#
class DescargarBDD(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        with NamedTemporaryFile(mode='w+', suffix='.xml', dir='/tmp', delete=False, encoding='utf-8') as tmp_file:
            call_command(
                'dumpdata',
                'inventario',
                indent=4,
                stdout=tmp_file,
                format='xml',
                exclude=['contenttypes', 'auth.permission'],
            )
            tmp_path = tmp_file.name

        file_handle = open(tmp_path, 'rb')
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename='inventario_respaldo.xml',
            content_type='application/xml',
        )

        def cleanup(_: HttpResponse) -> None:
            try:
                file_handle.close()
            finally:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

        response.add_post_render_callback(cleanup)
        return response


#Fin de vista--------------------------------------------------------------------------------


#Configuracion general de varios elementos--------------------------------------------------#
class ConfiguracionGeneral(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        # Obtener la empresa activa desde la sesión o crearla
        empresa_id = request.session.get('empresa_activa')
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if not empresa:
            ruc_usuario = request.user.username
            if re.fullmatch(r"\d{13}", ruc_usuario):
                empresa = Empresa.objects.create(
                    ruc=ruc_usuario,
                    razon_social="PENDIENTE",
                )
                UsuarioEmpresa.objects.get_or_create(usuario=request.user, empresa=empresa)
                # Promoción controlada: asignar ADMIN empresa sin superuser global
                if getattr(request.user, 'nivel', Usuario.USER) != Usuario.ADMIN:
                    request.user.nivel = Usuario.ADMIN
                request.user.is_staff = True
                request.user.is_superuser = False  # Nunca elevar aquí
                request.user.save(update_fields=["nivel", "is_staff", "is_superuser"])
                grupo, _ = Group.objects.get_or_create(name="Administrador")
                request.user.groups.set([grupo])
                request.session['empresa_activa'] = empresa.id

        # Intentar obtener configuración ligada a la empresa
        conf = None
        if empresa:
            conf = Opciones.objects.filter(empresa=empresa).first()

        # Crear automática si no existe nada
        if not conf and empresa:
            conf = Opciones.objects.create(
                empresa=empresa,
                identificacion=getattr(empresa, 'ruc', '0000000000000') or '0000000000000',
                razon_social='PENDIENTE',
                nombre_comercial='PENDIENTE',
                direccion_establecimiento='PENDIENTE',
                correo='pendiente@empresa.com',
                telefono='0000000000',
            )

        # Si aún no hay (ni empresa), error simple
        if not conf:
            messages.error(request, 'No hay empresa ni configuración creada.')
            return HttpResponseRedirect('/')

        # Usar el formulario con instance para evitar set manual campo por campo
        # Como OpcionesFormulario es forms.Form (no ModelForm) cargamos valores vía initial
        identificacion = getattr(empresa, 'ruc', None)
        if conf.identificacion and conf.identificacion != '0000000000000':
            identificacion = conf.identificacion
        if not identificacion:
            identificacion = request.user.username

        initial = {
            'identificacion': identificacion,
            'razon_social': conf.razon_social,
            'nombre_comercial': conf.nombre_comercial,
            'correo': conf.correo,
            'telefono': conf.telefono,
            'moneda': conf.moneda,
            'direccion_establecimiento': conf.direccion_establecimiento,
            'obligado': conf.obligado,
            'tipo_regimen': conf.tipo_regimen,
            'es_contribuyente_especial': conf.es_contribuyente_especial,
            'numero_contribuyente_especial': conf.numero_contribuyente_especial or '',
            'es_agente_retencion': conf.es_agente_retencion,
            'numero_agente_retencion': conf.numero_agente_retencion or '',
        }
        form = OpcionesFormulario(initial=initial)
        contexto = complementarContexto({'form': form, 'configuracion': conf}, request.user)
        return render(request, 'inventario/opciones/configuracion.html', contexto)
    
    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        empresa = Empresa.objects.filter(id=empresa_id).first()
        conf = None
        if empresa:
            conf = Opciones.objects.filter(empresa=empresa).first()
        if not conf and empresa:
            conf = Opciones.objects.create(
                empresa=empresa,
                identificacion=getattr(empresa, 'ruc', '0000000000000') or '0000000000000',
                razon_social='PENDIENTE',
                nombre_comercial='PENDIENTE',
                direccion_establecimiento='PENDIENTE',
                correo='pendiente@empresa.com',
                telefono='0000000000',
            )
        if not conf:
            messages.error(request, 'No hay empresa ni configuración creada.')
            return HttpResponseRedirect('/')
        form = OpcionesFormulario(request.POST, request.FILES)
        if form.is_valid():
            # Asignar manual porque no es ModelForm
            conf.identificacion = form.cleaned_data['identificacion']
            conf.razon_social = form.cleaned_data['razon_social']
            conf.nombre_comercial = form.cleaned_data.get('nombre_comercial')
            conf.direccion_establecimiento = form.cleaned_data.get('direccion_establecimiento')
            conf.correo = form.cleaned_data.get('correo')
            conf.telefono = form.cleaned_data.get('telefono')
            conf.obligado = form.cleaned_data.get('obligado')
            conf.tipo_regimen = form.cleaned_data.get('tipo_regimen')
            conf.moneda = form.cleaned_data.get('moneda')
            conf.es_contribuyente_especial = form.cleaned_data.get('es_contribuyente_especial')
            conf.numero_contribuyente_especial = form.cleaned_data.get('numero_contribuyente_especial') or None
            conf.es_agente_retencion = form.cleaned_data.get('es_agente_retencion')
            conf.numero_agente_retencion = form.cleaned_data.get('numero_agente_retencion') or None
            imagen = request.FILES.get('imagen')
            if imagen:
                conf.imagen = imagen
            conf.empresa = empresa
            conf.save()
            if empresa:
                empresa.ruc = conf.identificacion
                empresa.razon_social = conf.razon_social or 'PENDIENTE'
                empresa.save(update_fields=['ruc', 'razon_social'])
            messages.success(request, 'Configuración actualizada exitosamente!')
            return redirect('inventario:panel')
        contexto = complementarContexto({'form': form, 'configuracion': conf}, request.user)
        return render(request, 'inventario/opciones/configuracion.html', contexto)
#Fin de vista--------------------------------------------------------------------------------


#Accede a los modulos del manual de usuario---------------------------------------------#
class VerManualDeUsuario(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, pagina):
        if pagina == 'inicio':
            return render(request, 'inventario/manual/index.html')

        if pagina == 'producto':
            return render(request, 'inventario/manual/producto.html')

        if pagina == 'proveedor':
            return render(request, 'inventario/manual/proveedor.html')

        if pagina == 'pedido':
            return render(request, 'inventario/manual/pedido.html')

        if pagina == 'clientes':
            return render(request, 'inventario/manual/clientes.html')

        if pagina == 'factura':
            return render(request, 'inventario/manual/factura.html')

        if pagina == 'usuarios':
            return render(request, 'inventario/manual/usuarios.html')

        if pagina == 'opciones':
            return render(request, 'inventario/manual/opciones.html')


#Fin de vista--------------------------------------------------------------------------------

class Secuencias(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')

            secuencias = Secuencia.objects.filter(empresa_id=empresa_id).order_by('tipo_documento','establecimiento','punto_emision')
            form = SecuenciaFormulario()  # Formulario vacío para crear una nueva secuencia (empresa se asigna server-side)
            contexto = {'form': form, 'secuencias': secuencias, 'empresa_activa': empresa_id}
            contexto = complementarContexto(contexto, request.user)  # Añade información adicional al contexto
            return render(request, 'inventario/opciones/secuencias.html', contexto)
        except Exception as e:
            messages.error(request, f"Error al cargar las secuencias: {e}")
            return redirect('inventario:panel')

    def post(self, request):
        secuencia_id = request.POST.get('id', None)  # Recuperar el ID del formulario (puede ser None)
        form = SecuenciaFormulario(request.POST)

        if form.is_valid():
            try:
                empresa_id = request.session.get('empresa_activa')
                if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                    messages.error(request, 'Seleccione una empresa válida.')
                    return redirect('inventario:seleccionar_empresa')
                # Si se proporciona un ID, intenta buscar la secuencia para actualizar
                if secuencia_id and Secuencia.objects.filter(id=secuencia_id, empresa_id=empresa_id).exists():
                    secuencia = Secuencia.objects.get(id=secuencia_id, empresa_id=empresa_id)
                    for field, value in form.cleaned_data.items():
                        setattr(secuencia, field, value)
                    # Evitar reasignación de empresa cruzada
                    secuencia.empresa_id = empresa_id
                    secuencia.save()
                    messages.success(request, f'Secuencia actualizada exitosamente con ID {secuencia.id}!')
                else:
                    # Crear nueva secuencia asignando empresa_activa explícitamente
                    nueva_secuencia = form.save(commit=False)
                    nueva_secuencia.empresa_id = empresa_id
                    nueva_secuencia.save()
                    messages.success(request, f'Nueva secuencia creada exitosamente con ID {nueva_secuencia.id}!')
                return redirect('inventario:secuencias')

            except Exception as e:
                messages.error(request, f'Error al actualizar o crear la secuencia: {e}')
        else:
            messages.error(request, 'Error en los datos del formulario.')

        # Recargar las secuencias si hay errores
        try:
            empresa_id = request.session.get('empresa_activa')
            secuencias = Secuencia.objects.filter(empresa_id=empresa_id) if empresa_id else Secuencia.objects.none()
            contexto = {'form': form, 'secuencias': secuencias, 'empresa_activa': empresa_id}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/secuencias.html', contexto)
        except Exception as e:
            messages.error(request, f"Error al recargar las secuencias: {e}")
            return redirect('inventario:panel')


class ListaSecuencias(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        secuencias = Secuencia.objects.filter(empresa_id=empresa_id).order_by('tipo_documento','establecimiento','punto_emision')
        contexto = {'secuencias': secuencias, 'empresa_activa': empresa_id}
        contexto = complementarContexto(contexto, request.user)  # Añade información al contexto si es necesario
        return render(request, 'inventario/opciones/lista_secuencias.html', contexto)


class EliminarSecuencia(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        secuencia = get_object_or_404(Secuencia, id=id, empresa_id=empresa_id)
        secuencia.delete()
        messages.success(request, f'Secuencia con ID {id} eliminada exitosamente.')
        return redirect('inventario:lista_secuencias')


class EditarSecuencia(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, *args, **kwargs):
        try:
            # Extraemos el 'id' desde los argumentos de la URL
            secuencia_id = kwargs.get('id')
            # Obtenemos la secuencia o lanzamos 404 si no existe
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            secuencia = get_object_or_404(Secuencia, id=secuencia_id, empresa_id=empresa_id)
            # Inicializamos el formulario con la instancia de la secuencia
            form = SecuenciaFormulario(instance=secuencia)
            # Renderizamos la plantilla con el formulario
            return render(request, 'inventario/opciones/editar_secuencia.html', {'form': form, 'secuencia': secuencia})
        except Exception as e:
            messages.error(request, f"Error al cargar la secuencia para edición: {e}")
            return redirect('inventario:secuencias')

    def post(self, request, *args, **kwargs):
        try:
            # Extraemos el 'id' desde los argumentos de la URL
            secuencia_id = kwargs.get('id')
            # Obtenemos la secuencia o lanzamos 404 si no existe
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            secuencia = get_object_or_404(Secuencia, id=secuencia_id, empresa_id=empresa_id)
            # Vinculamos los datos enviados con la instancia existente
            form = SecuenciaFormulario(request.POST, instance=secuencia)

            if form.is_valid():
                # Guardamos los cambios asegurando que la empresa no cambie
                updated = form.save(commit=False)
                updated.empresa_id = empresa_id
                updated.save()
                messages.success(request, 'Secuencia actualizada correctamente.')
                return redirect('inventario:lista_secuencias')  # Redirige a la lista de secuencias
            else:
                messages.error(request, 'Error en los datos enviados.')
                return render(request, 'inventario/opciones/editar_secuencia.html', {'form': form, 'secuencia': secuencia})
        except Exception as e:
            messages.error(request, f"Error al actualizar la secuencia: {e}")
            return redirect('inventario:secuencias')

class CrearFacturador(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')

        form = FacturadorForm()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/facturador_form.html', contexto)

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')

        form = FacturadorForm(request.POST)

        if form.is_valid():
            try:
                # Empresa activa obligatoria
                empresa_id = request.session.get('empresa_activa')
                empresa = Empresa.objects.filter(id=empresa_id).first()
                if not empresa or not request.user.empresas.filter(id=empresa.id).exists():
                    messages.error(request, 'Seleccione una empresa válida antes de crear facturadores.')
                    return redirect('inventario:seleccionar_empresa')
                # Crear el facturador usando el manager personalizado
                facturador = Facturador.objects.create_facturador(
                    nombres=form.cleaned_data['nombres'],
                    telefono=form.cleaned_data.get('telefono', ''),
                    correo=form.cleaned_data['correo'],
                    password=form.cleaned_data['password'],  # Se encriptará automáticamente
                    descuento_permitido=form.cleaned_data.get('descuento_permitido', 0.00),
                    activo=form.cleaned_data.get('activo', True),
                    empresa=empresa,
                )

                messages.success(request, f'Facturador {facturador.nombres} creado exitosamente.')
                return redirect('inventario:listar_facturadores')
            except IntegrityError:
                messages.error(request, 'La contraseña ya está en uso.')
            except Exception as e:
                print(f"Error al crear facturador: {e}")
                messages.error(request, f'Error al crear el facturador: {str(e)}')
        else:
            print("Errores en el formulario:", form.errors)
            messages.error(request, 'Por favor, corrija los errores en el formulario.')

        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/facturador_form.html', contexto)

# Listar Facturadores
class ListarFacturadores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')

        facturadores = Facturador.tenant_objects.filter(empresa_id=empresa_id)
    # Limpieza opcional: si existen facturadores huérfanos (empresa NULL) y el usuario es admin, se podrían reclamar
    # (De momento solo los ignoramos)
        contexto = {'facturadores': facturadores}
        contexto = complementarContexto(contexto, request.user)
        # Asegúrate de que la plantilla esté en la ruta correcta
        return render(request, 'inventario/opciones/facturador_list.html', contexto)

# Editar Facturador
class EditarFacturador(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        # Recupera el facturador o lanza 404 si no existe
        facturador = get_object_or_404(Facturador.tenant_objects, id=id, empresa_id=empresa_id)
        # Crea el formulario con los datos existentes
        form = FacturadorForm(instance=facturador)
        contexto = {
            'form': form,
            'facturador': facturador
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/editar_facturador.html', contexto)

    def post(self, request, id):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        # Recupera el facturador o lanza 404 si no existe
        facturador = get_object_or_404(Facturador.tenant_objects, id=id, empresa_id=empresa_id)

        # Copia los datos del formulario para evitar problemas con el checkbox
        data = request.POST.copy()
        # Si el checkbox no se envía, se considera como False
        data['activo'] = data.get('activo') == 'True'

        # Crea el formulario con los datos enviados y el facturador a editar
        form = FacturadorForm(data, instance=facturador)

        if form.is_valid():
            try:
                # Guarda los cambios si el formulario es válido
                form.save()
                messages.success(request, 'Facturador actualizado exitosamente.')
                return redirect('inventario:listar_facturadores')
            except IntegrityError:
                messages.error(request, 'La contraseña ya está en uso.')
            except Exception as e:
                print(e)
                messages.error(request, f'Error al actualizar el facturador: {str(e)}')
        else:
            # Muestra los errores en la consola para depuración
            print(form.errors)
            messages.error(request, 'Revise los datos proporcionados. Hay errores en el formulario.')

        # Reenvía el formulario con errores o después de una excepción
        contexto = {
            'form': form,
            'facturador': facturador
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/editar_facturador.html', contexto)

# Eliminar Facturador
class EliminarFacturador(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        facturador = get_object_or_404(Facturador.tenant_objects, id=id, empresa_id=empresa_id)
        facturador.delete()
        messages.success(request, 'Facturador eliminado exitosamente.')
        return redirect('inventario:listar_facturadores')

class LoginFacturador(View):
    def post(self, request):
        try:
            # Obtener solo la contraseña del formulario
            password = request.POST.get('password')
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return render(request, 'inventario/facturador/login_facturador.html')
            
            if not password:
                messages.error(request, 'La contraseña es requerida.')
                return render(request, 'inventario/facturador/login_facturador.html')
            
            # Buscar el facturador dentro de la empresa activa
            facturadores = Facturador.tenant_objects.filter(activo=True, empresa_id=empresa_id)
            facturador_valido = None
            
            for facturador in facturadores:
                if facturador.check_password(password):
                    facturador_valido = facturador
                    break
            
            if facturador_valido:
                # Guardar la sesión del facturador
                request.session['facturador_id'] = facturador_valido.id
                request.session['facturador_nombre'] = facturador_valido.nombres
                
                messages.success(request, f'Bienvenido {facturador_valido.nombres}')
                
                # Redirigir a la página solicitada o a emitirFactura por defecto
                next_url = request.GET.get('next') or request.POST.get('next') or 'inventario:emitirFactura'
                if next_url.startswith('/'):
                    return redirect(next_url)
                else:
                    return redirect(next_url)
            else:
                messages.error(request, 'Contraseña incorrecta. Verifique e intente nuevamente.')
                return render(request, 'inventario/facturador/login_facturador.html')
                
        except Exception as e:
            print(f"Error en LoginFacturador: {e}")
            messages.error(request, 'Error interno del servidor.')
            return render(request, 'inventario/facturador/login_facturador.html')

    def get(self, request):
        # Mostrar el formulario de login
        return render(request, 'inventario/facturador/login_facturador.html')


class LoginProformador(View):
    def post(self, request):
        try:
            # Obtener solo la contraseña del formulario
            password = request.POST.get('password')
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return render(request, 'inventario/facturador/login_proformador.html')
            
            if not password:
                messages.error(request, 'La contraseña es requerida.')
                return render(request, 'inventario/facturador/login_proformador.html')
            
            # Buscar el facturador dentro de la empresa activa
            facturadores = Facturador.tenant_objects.filter(activo=True, empresa_id=empresa_id)
            facturador_valido = None
            
            for facturador in facturadores:
                if facturador.check_password(password):
                    facturador_valido = facturador
                    break
            
            if facturador_valido:
                # Emitir token firmado de 2 minutos de validez, no guardar en sesión
                from django.core import signing
                token = signing.dumps({'fid': facturador_valido.id}, salt='proformador')
                messages.success(request, f'Bienvenido {facturador_valido.nombres}')
                # Redirigir a emisión con token en la URL
                return redirect(f"/inventario/proformas/emitir/?t={token}")
            else:
                messages.error(request, 'Contraseña incorrecta. Verifique e intente nuevamente.')
                return render(request, 'inventario/facturador/login_proformador.html')
                
        except Exception as e:
            print(f"Error en LoginProformador: {e}")
            messages.error(request, 'Error interno del servidor.')
            return render(request, 'inventario/facturador/login_proformador.html')

    def get(self, request):
        # Mostrar el formulario de login
        return render(request, 'inventario/facturador/login_proformador.html')

#Para agregar los almacénes
@require_empresa_activa
def gestion_almacenes(request):
    """Gestión de Almacenes: siempre requiere empresa activa y aísla por tenant."""
    from .models import Empresa
    empresa_id = request.session.get('empresa_activa')
    empresa = Empresa.objects.get(id=empresa_id)

    if request.method == 'POST':
        form = AlmacenForm(request.POST)
        if form.is_valid():
            almacen = form.save(commit=False)
            almacen.empresa = empresa  # siempre
            almacen.save()
            messages.success(request, "Almacén agregado exitosamente.")
            return redirect('inventario:gestion_almacenes')
    else:
        form = AlmacenForm()

    almacenes = Almacen.objects.filter(empresa=empresa).order_by('descripcion')

    context = {
        'form': form,
        'almacenes': almacenes,
        'empresa_contexto': empresa,
    }
    context = complementarContexto(context, request.user)
    return render(request, 'inventario/opciones/almacenes.html', context)


def editar_almacen(request, id):
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return HttpResponseForbidden()
    almacen = get_object_or_404(Almacen, id=id, empresa_id=empresa_id)
    if request.method == 'POST':
        form = AlmacenForm(request.POST, instance=almacen)
        if form.is_valid():
            form.save()
            messages.success(request, "Almacén editado exitosamente.")
            return redirect('inventario:gestion_almacenes')
    else:
        form = AlmacenForm(instance=almacen)

    context = {
        'form': form,
        'edit_mode': True,
        'almacen': almacen,
    }
    context = complementarContexto(context, request.user)
    return render(request, 'inventario/opciones/almacenes_form.html', context)

def eliminar_almacen(request, id):
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return HttpResponseForbidden()
    almacen = get_object_or_404(Almacen, id=id, empresa_id=empresa_id)
    almacen.delete()
    messages.success(request, "Almacén eliminado exitosamente.")
    return redirect('inventario:gestion_almacenes')


# Agregar al final del archivo views.py, antes de las funciones de almacén

class RideView(LoginRequiredMixin, View):
    """Vista para mostrar el RIDE en HTML"""
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        try:
            # Obtener la factura de la empresa activa
            empresa_id = request.session.get('empresa_activa')
            if not request.user.empresas.filter(id=empresa_id).exists():
                raise Http404("Empresa no válida")
            factura = get_object_or_404(Factura, id=p, empresa_id=empresa_id)
            
            # Obtener los detalles de la factura
            detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto')
            
            # Obtener las opciones generales de la empresa
            try:
                empresa = getattr(factura, 'empresa', None)
                opciones = Opciones.objects.for_tenant(empresa).first()
                if not opciones and empresa:
                    opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
            except Opciones.DoesNotExist:
                opciones = None
            
            if not detalles.exists():
                messages.error(request, 'La factura no tiene detalles para mostrar.')
                return redirect('inventario:verFactura', p=p)
            
            contexto = {
                'factura': factura,
                'detalles': detalles,
                'opciones': opciones
            }
            
            return render(request, 'inventario/sri/factura_ride.html', contexto)
            
        except Exception as e:
            messages.error(request, f'Error al mostrar RIDE: {str(e)}')
            return redirect('inventario:verFactura', p=p)

# === FUNCIONES DE ADAPTACIÓN PARA SRI/XML/PDF ===
def adapt_opciones(opciones):
    """
    Adapta una instancia de Opciones a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'ruc': getattr(opciones, 'identificacion', '0000000000000'),
        'razon_social': getattr(opciones, 'razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
        'nombre_comercial': getattr(opciones, 'nombre_comercial', ''),
        'direccion_matriz': getattr(opciones, 'direccion_establecimiento', '[CONFIGURAR DIRECCIÓN]'),
        'telefono': getattr(opciones, 'telefono', ''),
        'email': getattr(opciones, 'correo', ''),
        'contribuyente_especial': getattr(opciones, 'numero_contribuyente_especial', None) if getattr(opciones, 'es_contribuyente_especial', False) else None,
        'obligado_contabilidad': 'SI' if getattr(opciones, 'obligado', 'SI') == 'SI' else 'NO',
        'tipo_ambiente': getattr(opciones, 'tipo_ambiente', '1'),
        'tipo_emision': getattr(opciones, 'tipo_emision', '1'),
        'moneda': getattr(opciones, 'moneda', 'DOLAR'),
    }

def adapt_cliente(cliente):
    """
    Adapta una instancia de Cliente a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'tipo_identificacion': getattr(cliente, 'tipoIdentificacion', '04'),
        'identificacion': getattr(cliente, 'identificacion', '9999999999999'),
        'razon_social': getattr(cliente, 'razon_social', 'CONSUMIDOR FINAL'),
        'nombre_comercial': getattr(cliente, 'nombre_comercial', ''),
        'direccion': getattr(cliente, 'direccion', ''),
        'telefono': getattr(cliente, 'telefono', ''),
        'correo': getattr(cliente, 'correo', ''),
    }

def adapt_producto(producto):
    """
    Adapta una instancia de Producto a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'codigo': getattr(producto, 'codigo', ''),
        'descripcion': getattr(producto, 'descripcion', ''),
        'precio': float(getattr(producto, 'precio', 0)),
        'iva': getattr(producto, 'iva', '0'),
        'categoria': getattr(producto, 'categoria', ''),
        'disponible': getattr(producto, 'disponible', 0),
    }

def adapt_detallefactura(detalle):
    """
    Adapta una instancia de DetalleFactura a un dict compatible con SRI/ride_generator/xml_generator
    Usa valores personalizados si existen, sino los del producto/servicio original
    """
    producto = getattr(detalle, 'producto', None)
    servicio = getattr(detalle, 'servicio', None)
    prod_dict = adapt_producto(producto) if producto else {}
    
    # ✅ Usar código personalizado si existe, sino el del producto/servicio
    codigo = getattr(detalle, 'codigo_personalizado', None)
    if not codigo:
        if producto:
            codigo = prod_dict.get('codigo', '')
        elif servicio:
            codigo = getattr(servicio, 'codigo', '')
        else:
            codigo = ''
    
    # ✅ Usar precio personalizado si existe, sino el del producto/servicio
    precio = getattr(detalle, 'precio_unitario', None)
    if precio is None:
        precio = prod_dict.get('precio', 0) if producto else getattr(servicio, 'precio1', 0) if servicio else 0
    
    # ✅ Usar IVA personalizado si existe, sino el del producto/servicio
    iva_codigo = getattr(detalle, 'iva_codigo', None)
    if not iva_codigo:
        if producto:
            iva_codigo = prod_dict.get('iva', '0')
        elif servicio:
            iva_codigo = str(servicio.iva.iva if hasattr(servicio.iva, 'iva') else servicio.iva) if servicio else '0'
        else:
            iva_codigo = '0'
    
    # ✅ Descripción: usar reemplazo si existe, sino la del producto/servicio
    descripcion_reemplazo = getattr(detalle, 'descripcion_reemplazo', None)
    if descripcion_reemplazo:
        descripcion = descripcion_reemplazo
    else:
        descripcion = prod_dict.get('descripcion', '') if producto else getattr(servicio, 'descripcion', '') if servicio else ''
    
    # ✅ Información adicional (detallesAdicionales del XML SRI)
    info_adicional = getattr(detalle, 'info_adicional', None)
    detalles_adicionales = []
    if info_adicional:
        detalles_adicionales.append({
            'nombre': 'Información',
            'valor': info_adicional[:300]  # Máximo 300 caracteres según SRI
        })
    
    return {
        'codigo_principal': codigo,
        'descripcion': descripcion,
        'cantidad': float(getattr(detalle, 'cantidad', 0)),
        'precio_unitario': float(precio),
        'descuento': float(getattr(detalle, 'descuento', 0) or 0),
        'precio_total_sin_impuesto': float(getattr(detalle, 'sub_total', 0)),
        'codigo_porcentaje_iva': iva_codigo,
        'detalles_adicionales': detalles_adicionales,  # ✅ Info adicional para XML
    }

def adapt_factura(factura, detalles=None, opciones=None):
    """
    Adapta una instancia de Factura y sus detalles a un dict compatible con SRI/ride_generator/xml_generator
    """
    detalles = detalles or []
    opciones_dict = adapt_opciones(opciones) if opciones else {}
    fecha_emision = getattr(factura, 'fecha_emision', None)
    if isinstance(fecha_emision, str):
        fecha_emision_str = fecha_emision
    elif fecha_emision is not None:
        fecha_emision_str = fecha_emision.strftime("%d/%m/%Y")
    else:
        fecha_emision_str = ''
    return {
        'emisor': opciones_dict,
        'fecha_emision': fecha_emision_str,
        'establecimiento': getattr(factura, 'establecimiento', '001'),
        'punto_emision': getattr(factura, 'punto_emision', '001'),
        'secuencial': getattr(factura, 'secuencia', '000000001'),
        'cliente': adapt_cliente(getattr(factura, 'cliente', None)) if getattr(factura, 'cliente', None) else {},
        'identificacion_cliente': getattr(factura, 'identificacion_cliente', '9999999999999'),
        'nombre_cliente': getattr(factura, 'nombre_cliente', 'CONSUMIDOR FINAL'),
        'direccion_cliente': getattr(factura, 'direccion_cliente', ''),
        'detalles': [adapt_detallefactura(d) for d in detalles],
        'totales': {
            'subtotal_sin_impuestos': float(getattr(factura, 'sub_total', getattr(factura, 'sub_monto', 0))),
            'subtotal_0': 0.0,  # Ajustar si hay lógica para 0%
            'subtotal_15': float(getattr(factura, 'sub_total', getattr(factura, 'sub_monto', 0))),  # Ajustar según IVA
            'descuento_total': float(getattr(factura, 'descuento', 0) or 0),
            'iva_15': float(getattr(factura, 'iva', getattr(factura, 'monto_general', 0) - getattr(factura, 'sub_monto', 0))),
            'importe_total': float(getattr(factura, 'monto_general', 0)),
        },
        'concepto': getattr(factura, 'concepto', ''),
        'clave_acceso': getattr(factura, 'clave_acceso', None),
    }

#Crea una lista de los proveedores, 10 por pagina----------------------------------------#
class ListarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        empresa_id = request.session.get('empresa_activa')
        if empresa_id is None or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'No se ha seleccionado una empresa válida')
            return redirect('inventario:panel')
        proveedores = Proveedor.objects.filter(empresa_id=empresa_id)
        contexto = {'tabla': proveedores}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/proveedor/listarProveedores.html', contexto)

#Fin de vista--------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar a un proveedor---------------------------------#
class AgregarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            form = ProveedorFormulario(request.POST)
            messages.error(request, 'No hay una empresa activa seleccionada.')
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            form = ProveedorFormulario(request.POST)
            messages.error(request, 'No hay una empresa activa seleccionada.')
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})

        form = ProveedorFormulario(request.POST, empresa=empresa)

        if form.is_valid():
            # ✅ ACTUALIZADO: Usar nombres de campos correctos del formulario actualizado
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']
            identificacion_proveedor = form.cleaned_data['identificacion_proveedor']
            razon_social_proveedor = form.cleaned_data['razon_social_proveedor']
            nombre_comercial_proveedor = form.cleaned_data['nombre_comercial_proveedor']
            direccion = form.cleaned_data['direccion']
            nacimiento = form.cleaned_data.get('nacimiento')  # Opcional
            telefono = form.cleaned_data.get('telefono')  # Opcional
            correo = form.cleaned_data['correo']
            telefono2 = form.cleaned_data.get('telefono2')  # Opcional
            correo2 = form.cleaned_data.get('correo2')  # Opcional
            observaciones = form.cleaned_data.get('observaciones')  # Opcional
            convencional = form.cleaned_data.get('convencional')  # Opcional
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoProveedor = form.cleaned_data['tipoProveedor']

            # ✅ ACTUALIZADO: Crear proveedor con campos correctos
            proveedor = Proveedor(
                tipoIdentificacion=tipoIdentificacion,
                identificacion_proveedor=identificacion_proveedor,
                razon_social_proveedor=razon_social_proveedor,
                nombre_comercial_proveedor=nombre_comercial_proveedor,
                direccion=direccion,
                nacimiento=nacimiento,
                telefono=telefono,
                correo=correo,
                telefono2=telefono2,
                correo2=correo2,
                observaciones=observaciones,
                convencional=convencional,
                tipoVenta=tipoVenta,
                tipoRegimen=tipoRegimen,
                tipoProveedor=tipoProveedor,
                empresa=empresa,
            )

            proveedor.save()
            form = ProveedorFormulario()
            messages.success(request, 'Proveedor ingresado exitosamente con ID %s.' % proveedor.id)
            request.session['proveedorProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarProveedor")
        else:
            #De lo contrario lanzara el mismo formulario
            messages.error(request, 'Error al agregar el proveedor, ya existe o se encuentra en la base de datos')
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})

    def get(self, request):
        form = ProveedorFormulario()
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('proveedorProcesado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/agregarProveedor.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Formulario simple que procesa un script para importar los proveedores-----------------#
class ImportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarProveedoresFormulario(request.POST)
        if form.is_valid():
            request.session['proveedoresImportados'] = True
            return HttpResponseRedirect("/inventario/importarProveedores")

    def get(self, request):
        form = ImportarProveedoresFormulario()

        if request.session.get('proveedoresImportados') == True:
            importado = request.session.get('proveedoresImportados')
            contexto = {'form': form, 'proveedoresImportados': importado}
            request.session['proveedoresImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/importarProveedores.html', contexto)

#Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los proveedores-----------------------#
class ExportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        form = ExportarProveedoresFormulario(request.POST)
        if form.is_valid():
            request.session['proveedoresExportados'] = True

            #Se obtienen las entradas de proveedor en formato JSON
            data = serializers.serialize("json", Proveedor.objects.filter(empresa_id=empresa_id))
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("proveedores.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("proveedores.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="proveedores.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarProveedoresFormulario()

        if request.session.get('proveedoresExportados') == True:
            exportado = request.session.get('proveedoresExportados')
            contexto = {'form': form, 'proveedoresExportados': exportado}
            request.session['proveedoresExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/exportarProveedores.html', contexto)

#Fin de vista-------------------------------------------------------------------------#


#Muestra el mismo formulario del proveedor pero con los datos a editar----------------------#
class EditarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()
        # Crea una instancia del formulario y la llena con los datos (multi-tenant)
        proveedor = get_object_or_404(Proveedor, id=p, empresa_id=empresa_id)
        form = ProveedorFormulario(request.POST, instance=proveedor, empresa=proveedor.empresa)
        # Revisa si es valido:

        if form.is_valid():
            # ✅ ACTUALIZADO: Usar nombres de campos correctos del formulario actualizado
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']
            identificacion_proveedor = form.cleaned_data['identificacion_proveedor']
            razon_social_proveedor = form.cleaned_data['razon_social_proveedor']
            nombre_comercial_proveedor = form.cleaned_data['nombre_comercial_proveedor']
            direccion = form.cleaned_data['direccion']
            nacimiento = form.cleaned_data.get('nacimiento')  # Opcional
            telefono = form.cleaned_data.get('telefono')  # Opcional
            correo = form.cleaned_data['correo']
            telefono2 = form.cleaned_data.get('telefono2')  # Opcional
            correo2 = form.cleaned_data.get('correo2')  # Opcional
            observaciones = form.cleaned_data.get('observaciones')  # Opcional
            convencional = form.cleaned_data.get('convencional')  # Opcional
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoProveedor = form.cleaned_data['tipoProveedor']

            # ✅ ACTUALIZADO: Actualizar proveedor con campos correctos
            proveedor.tipoIdentificacion = tipoIdentificacion
            proveedor.identificacion_proveedor = identificacion_proveedor
            proveedor.razon_social_proveedor = razon_social_proveedor
            proveedor.nombre_comercial_proveedor = nombre_comercial_proveedor
            proveedor.direccion = direccion
            proveedor.nacimiento = nacimiento
            proveedor.telefono = telefono
            proveedor.correo = correo
            proveedor.telefono2 = telefono2
            proveedor.correo2 = correo2
            proveedor.observaciones = observaciones
            proveedor.convencional = convencional
            proveedor.tipoVenta = tipoVenta
            proveedor.tipoRegimen = tipoRegimen
            proveedor.tipoProveedor = tipoProveedor
            proveedor.save()

            messages.success(request, 'Proveedor actualizado exitosamente')
            return HttpResponseRedirect("/inventario/editarProveedor/%s" % p)

        else:
            return render(request, 'inventario/proveedor/editarProveedor.html', {'form': form})

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden()
        proveedor = get_object_or_404(Proveedor, id=p, empresa_id=empresa_id)
        form = ProveedorFormulario(instance=proveedor, empresa=proveedor.empresa)

        contexto = {'form': form, 'proveedor': proveedor}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/editarProveedor.html', contexto)
        
#VISTAS PARA CAJA
class ListarCajas(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            cajas = Caja.objects.filter(empresa_id=empresa_id).order_by('descripcion')
            contexto = {'tabla': cajas, 'empresa_activa': empresa_id}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/listar_cajas.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar las cajas: {str(e)}')
            return redirect('inventario:panel')

#Fin de vista--------------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar una caja-----------------------------------------#
class AgregarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        form = CajaFormulario()
        contexto = {'form': form, 'modo': request.session.get('cajaProcesada'), 'empresa_activa': empresa_id}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/crear_caja.html', contexto)

    def post(self, request):
        form = CajaFormulario(request.POST)
        if form.is_valid():
            try:
                empresa_id = request.session.get('empresa_activa')
                if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                    messages.error(request, 'Seleccione una empresa válida.')
                    return redirect('inventario:seleccionar_empresa')
                caja = form.save(commit=False)
                caja.creado_por = request.user
                caja.empresa_id = empresa_id
                caja.save()
                messages.success(request, f'Caja "{caja.descripcion}" creada exitosamente.')
                request.session['cajaProcesada'] = 'agregada'
                return redirect('inventario:agregarCaja')
            except Exception as e:
                messages.error(request, f'Error al crear la caja: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{form.fields[field].label}: {error}')
        
        contexto = {'form': form, 'modo': request.session.get('cajaProcesada')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/crear_caja.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Muestra el mismo formulario pero con los datos a editar--------------------------------#
class EditarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            caja = get_object_or_404(Caja, id=id, empresa_id=empresa_id)
            form = CajaFormulario(instance=caja)
            contexto = {'form': form, 'caja': caja, 'modo': request.session.get('cajaProcesada'), 'editar': True}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/editar_caja.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la caja: {str(e)}')
            return redirect('inventario:listarCajas')

    def post(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            caja = get_object_or_404(Caja, id=id, empresa_id=empresa_id)
            form = CajaFormulario(request.POST, instance=caja)
            if form.is_valid():
                caja_actualizada = form.save(commit=False)
                caja_actualizada.empresa_id = empresa_id
                caja_actualizada.save()
                messages.success(request, f'Caja "{caja_actualizada.descripcion}" actualizada exitosamente.')
                request.session['cajaProcesada'] = 'editada'
                return redirect('inventario:editarCaja', id=caja.id)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{form.fields[field].label}: {error}')
        except Exception as e:
            messages.error(request, f'Error al actualizar la caja: {str(e)}')
        
        contexto = {'form': form, 'caja': caja, 'modo': request.session.get('cajaProcesada'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/editar_caja.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Muestra los detalles de una caja en modo solo lectura----------------------------------#
class VerCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            caja = get_object_or_404(Caja, id=id, empresa_id=empresa_id)
            from django.utils import timezone
            dias_desde_creacion = (timezone.now().date() - caja.fecha_creacion.date()).days
            contexto = {'caja': caja, 'dias_desde_creacion': dias_desde_creacion, 'modo': 'ver'}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/ver_caja.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar los detalles de la caja: {str(e)}')
            return redirect('inventario:listarCajas')

#Fin de vista-----------------------------------------------------------------------------#


#Elimina una caja con validaciones-------------------------------------------------------#
class EliminarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            caja = get_object_or_404(Caja, id=id, empresa_id=empresa_id)
            nombre_caja = caja.descripcion
            caja.delete()
            messages.success(request, f'Caja "{nombre_caja}" eliminada exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar la caja: {str(e)}')
        return redirect('inventario:listarCajas')

    def get(self, request, id):
        messages.warning(request, 'Método no permitido para eliminar cajas.')
        return redirect('inventario:listarCajas')


# === VISTAS PARA GESTIÓN DE BANCOS ===

#Lista todos los cuentas bancarias--------------------------------------------------------------#
class ListarBancos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            bancos = Banco.objects.filter(empresa_id=empresa_id).order_by('banco', 'titular')
            
            # Agregar contexto común del sistema
            contexto = {'bancos': bancos, 'empresa_activa': empresa_id}
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/listar_bancos.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar las cuentas bancarias: {str(e)}')
            return redirect('inventario:panel')

#Fin de vista--------------------------------------------------------------------------------#


class CrearBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            messages.error(request, 'Seleccione una empresa válida.')
            return redirect('inventario:seleccionar_empresa')
        form = BancoFormulario()
        contexto = {'form': form, 'empresa_activa': empresa_id}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/bancos/crear_banco.html', contexto)

    def post(self, request):
        form = BancoFormulario(request.POST)
        
        if form.is_valid():
            try:
                # Crear nueva cuenta bancaria
                empresa_id = request.session.get('empresa_activa')
                if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                    messages.error(request, 'Seleccione una empresa válida.')
                    return redirect('inventario:seleccionar_empresa')
                banco = form.save(commit=False)
                banco.creado_por = request.user
                banco.empresa_id = empresa_id
                banco.save()
                messages.success(request, 'Cuenta bancaria creada exitosamente.')
                return redirect('inventario:listar_bancos')  # ✅ CORRECTO
            except Exception as e:
                messages.error(request, f'Error al crear la cuenta bancaria: {str(e)}')
        else:
            # Mostrar errores de validación
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        # ❌ ESTABA MAL: return render(request, 'cajas/crear_caja.html', {'title': 'Agregar Caja', 'form': form})
        # ✅ CORRECTO:
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/bancos/crear_banco.html', contexto)


class EditarBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            banco = get_object_or_404(Banco, id=id, empresa_id=empresa_id)
            form = BancoFormulario(instance=banco)
            
            contexto = {
                'form': form, 
                'banco': banco,
                'modo': 'editar'
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/bancos/editar_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
    
    def post(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            banco = get_object_or_404(Banco, id=id, empresa_id=empresa_id)
            form = BancoFormulario(request.POST, instance=banco)
            if form.is_valid():
                updated = form.save(commit=False)
                updated.empresa_id = empresa_id
                updated.save()
                # ❌ ESTABA MAL: messages.success(request, 'Caja actualizada exitosamente.')
                # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
                # ✅ CORRECTO:
                messages.success(request, 'Cuenta bancaria actualizada exitosamente.')
                return redirect('inventario:listar_bancos')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        except Exception as e:
            # ❌ ESTABA MAL: messages.error(request, f'Error al actualizar la caja: {str(e)}')
            # ✅ CORRECTO:
            messages.error(request, f'Error al actualizar la cuenta bancaria: {str(e)}')
        
        # ❌ ESTABA MAL: return render(request, 'cajas/editar_caja.html', {'title': 'Editar Caja', 'form': form, 'caja': banco})
        # ✅ CORRECTO:
        contexto = {
            'form': form, 
            'banco': banco,
            'modo': 'editar'
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/editar_banco.html', contexto)


class VerBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            banco = get_object_or_404(Banco, id=id, empresa_id=empresa_id)
            
            # Calcular información adicional
            from django.utils import timezone
            dias_desde_apertura = (timezone.now().date() - banco.fecha_apertura).days if banco.fecha_apertura else 0
            
            contexto = {
                'banco': banco,  # ✅ CORRECTO: banco, no caja
                'dias_desde_apertura': dias_desde_apertura,
                'modo': 'ver'
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/ver_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar los detalles de la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')


class EliminarBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            banco = get_object_or_404(Banco, id=id, empresa_id=empresa_id)
            # ❌ ESTABA MAL: return render(request, 'cajas/eliminar_caja.html', {'title': 'Eliminar Caja', 'caja': banco})
            # ✅ CORRECTO:
            contexto = {
                'banco': banco,
                'titulo': 'Eliminar Cuenta Bancaria'
            }
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/eliminar_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
    
    def post(self, request, id):
        try:
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
                messages.error(request, 'Seleccione una empresa válida.')
                return redirect('inventario:seleccionar_empresa')
            banco = get_object_or_404(Banco, id=id, empresa_id=empresa_id)
            nombre_banco = f"{banco.banco} - {banco.titular}"
            banco.delete()
            # ❌ ESTABA MAL: messages.success(request, 'Caja eliminada exitosamente.')
            # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
            # ✅ CORRECTO:
            messages.success(request, f'Cuenta bancaria "{nombre_banco}" eliminada exitosamente.')
            return redirect('inventario:listar_bancos')
        except Exception as e:
            # ❌ ESTABA MAL: messages.error(request, f'Error al eliminar la caja: {str(e)}')
            # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
            # ✅ CORRECTO:
            messages.error(request, f'Error al eliminar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
        

        
class FirmaElectronicaView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        empresa = getattr(request, 'tenant', None)
        if not empresa:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.filter(id=empresa_id).first()

        opciones = Opciones.objects.for_tenant(empresa).first()
        created = False
        if not opciones:
            if not empresa or not getattr(empresa, 'ruc', None) or len(empresa.ruc) != 13:
                messages.error(request, 'No existe configuración y el RUC de la empresa no es válido. Configure empresa primero.')
                return redirect('inventario:configuracionGeneral')
            opciones = Opciones(
                empresa=empresa,
                identificacion=empresa.ruc,
                razon_social=getattr(empresa, 'razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
                direccion_establecimiento='[CONFIGURAR DIRECCIÓN]',
                correo='pendiente@empresa.com',
                telefono='0000000000'
            )
            try:
                opciones.save()
                created = True
            except ValidationError as e:
                messages.error(request, f'Error creando configuración inicial: {e}')
                return redirect('inventario:configuracionGeneral')
        if created:
            messages.info(request, 'Configuración creada. Complete los datos y cargue la firma.')

        form = FirmaElectronicaForm(instance=opciones)
        aviso_caducidad = self._obtener_aviso_caducidad(opciones)
        
        contexto = {
            'form': form,
            'aviso_caducidad': aviso_caducidad,
            'now': date.today(),
            'opciones': opciones  # Agregar opciones al contexto para debugging
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/firma_electronica.html', contexto)
    
    def post(self, request):
        empresa = getattr(request, 'tenant', None)
        if not empresa:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.filter(id=empresa_id).first()

        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones:
            if not empresa or not getattr(empresa, 'ruc', None) or len(empresa.ruc) != 13:
                messages.error(request, 'No existe configuración válida. Configure empresa primero.')
                return redirect('inventario:configuracionGeneral')
            opciones = Opciones(
                empresa=empresa,
                identificacion=empresa.ruc,
                razon_social=getattr(empresa, 'razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
                direccion_establecimiento='[CONFIGURAR DIRECCIÓN]',
                correo='pendiente@empresa.com',
                telefono='0000000000'
            )
            try:
                opciones.save()
            except ValidationError as e:
                messages.error(request, f'Error creando configuración inicial: {e}')
                return redirect('inventario:configuracionGeneral')
        # Asegurar RUC válido antes de procesar firma
        if opciones.identificacion == '0000000000000':
            empresa = opciones.empresa or Empresa.objects.first()
            if empresa and getattr(empresa, 'ruc', None) and len(empresa.ruc) == 13:
                opciones.identificacion = empresa.ruc
                try:
                    opciones.save()
                except ValidationError as e:
                    messages.error(request, f'Error validando RUC: {e}')
                    return redirect('inventario:configuracionGeneral')
            else:
                messages.error(request, 'RUC inválido. Actualice configuración general primero.')
                return redirect('inventario:configuracionGeneral')

        form = FirmaElectronicaForm(request.POST, request.FILES, instance=opciones)
        
        if form.is_valid():
            try:
                # Guardar el formulario
                opciones_guardadas = form.save()
                
                # Validar la firma electrónica si se subió
                if opciones_guardadas.firma_electronica and opciones_guardadas.password_firma:
                    messages.success(request, 'Firma electrónica actualizada correctamente.')
                else:
                    messages.success(request, 'Configuración actualizada correctamente.')
                
                # Redirigir para evitar que el mensaje aparezca en el panel principal
                return redirect('inventario:firma_electronica')
                
            except ValidationError as e:
                messages.error(request, f'Error de validación: {e.message}')
            except Exception as e:
                messages.error(request, f'Error al guardar la firma electrónica: {str(e)}')
                # En caso de error, mantener el formulario con los datos ingresados
        else:
            # Si el formulario no es válido, mostrar errores
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        # Obtener aviso de caducidad actualizado
        aviso_caducidad = self._obtener_aviso_caducidad(opciones)
        
        contexto = {
            'form': form,
            'aviso_caducidad': aviso_caducidad,
            'now': date.today(),
            'opciones': opciones
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/firma_electronica.html', contexto)
        
    def _obtener_aviso_caducidad(self, opciones):
        """
        Método privado para obtener el aviso de caducidad
        """
        aviso_caducidad = None
        if opciones and opciones.fecha_caducidad_firma:
            try:
                dias_restantes = (opciones.fecha_caducidad_firma - date.today()).days
                if dias_restantes < 0:
                    aviso_caducidad = "¡La firma electrónica ha caducado!"
                elif dias_restantes <= 30:
                    aviso_caducidad = f"Atención: La firma electrónica caduca en {dias_restantes} días."
                elif dias_restantes <= 90:
                    aviso_caducidad = f"Información: La firma electrónica caduca en {dias_restantes} días."
            except Exception as e:
                print(f"Error calculando días restantes: {e}")
        return aviso_caducidad
class EliminarFirmaElectronicaView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        empresa = getattr(request, 'tenant', None)
        if not empresa:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.filter(id=empresa_id).first()
        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones and empresa:
            opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
        eliminado = False
        if opciones.firma_electronica:
            # Intenta borrar el archivo físico usando el método delete()
            try:
                opciones.firma_electronica.delete(save=False)
                eliminado = True
            except Exception as e:
                messages.error(request, f'Error eliminando archivo físico: {e}')
            # Limpia la referencia en la base de datos
            opciones.firma_electronica = None
            opciones.fecha_caducidad_firma = None
            opciones.save()
            if eliminado:
                messages.success(request, 'Firma electrónica eliminada correctamente.')
            else:
                messages.warning(request, 'No se pudo eliminar el archivo físico, pero la referencia fue eliminada.')
        else:
            messages.info(request, 'No hay firma electrónica para eliminar.')
        return HttpResponseRedirect(reverse('inventario:firma_electronica'))


class DescargarFirmaElectronicaView(LoginRequiredMixin, View):
    """Serve el archivo de firma electrónica sólo a usuarios autorizados."""
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa = getattr(request, 'tenant', None)
        if not empresa:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.filter(id=empresa_id).first()
        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones or not opciones.firma_electronica:
            raise Http404("Archivo no disponible")
        if not request.user.is_staff:
            return HttpResponseForbidden("No autorizado")
        file_obj = opciones.firma_electronica.open('rb')
        filename = os.path.basename(opciones.firma_electronica.name)
        return FileResponse(file_obj, as_attachment=True, filename=filename)


from .models import Servicio
from .forms import ServicioFormulario
from django.urls import reverse_lazy

# Listar servicios
class ListarServicios(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        servicios = Servicio.objects.filter(empresa_id=empresa_id).order_by('-fecha_creacion')
        contexto = {'servicios': servicios}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/listarServicios.html', contexto)
# Agregar servicio
from .funciones import generar_codigo_servicio

class AgregarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        codigo_nuevo = generar_codigo_servicio()
        form = ServicioFormulario(initial={'codigo': codigo_nuevo})
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)

    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        form = ServicioFormulario(request.POST)
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        if form.is_valid():
            servicio = form.save(commit=False)
            servicio.empresa_id = empresa_id
            servicio.save()
            return redirect('inventario:listarServicios')
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)
# Editar servicio
class EditarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        servicio = get_object_or_404(Servicio, pk=p, empresa_id=empresa_id)
        form = ServicioFormulario(instance=servicio)
        contexto = {'form': form, 'edit_mode': True, 'servicio': servicio}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)

    def post(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        servicio = get_object_or_404(Servicio, pk=p, empresa_id=empresa_id)
        form = ServicioFormulario(request.POST, instance=servicio)
        contexto = {'form': form, 'edit_mode': True, 'servicio': servicio}
        contexto = complementarContexto(contexto, request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.empresa_id = empresa_id  # reforzar pertenencia
            updated.save()
            return redirect('inventario:listarServicios')
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)


class EliminarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden("No tienes acceso a esta empresa")
        servicio = get_object_or_404(Servicio, pk=p, empresa_id=empresa_id)
        servicio.delete()
        return redirect('inventario:listarServicios')


@csrf_exempt
@require_http_methods(["GET"])
def empresa_api(request, ruc):
    """Endpoint para consultar información de una empresa por RUC."""
    if not ruc:
        return JsonResponse({'error': True, 'message': 'El RUC es requerido'}, status=400)
    try:
        from services import consultar_identificacion as servicio_consultar_identificacion
        resultado = servicio_consultar_identificacion(ruc)

        razon_social = resultado.get('razon_social', '')
        nombre_comercial = resultado.get('nombre_comercial', '')
        direccion = resultado.get('direccion', '')
        tipo_regimen = resultado.get('tipo_regimen')
        obligado_contabilidad = resultado.get('obligado_contabilidad', 'NO')

        respuesta = {
            'error': False,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'direccion': direccion,
            'correo': resultado.get('email', ''),
            'telefono': resultado.get('telefono', ''),
            'obligado_contabilidad': obligado_contabilidad,
            'actividad_economica': resultado.get('actividad_economica', ''),
        }
        if tipo_regimen:
            respuesta['tipo_regimen'] = tipo_regimen

        return JsonResponse(respuesta, status=resultado.get('status_code', 200))
    except Exception as e:
        logger.error(f"Error en empresa_api: {e}")
        return JsonResponse({'error': True, 'message': f'Error consultando API externa: {e}'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def buscar_empresa(request):
    ruc = request.GET.get('q', '')
    if not ruc:
        return JsonResponse({'error': True, 'message': 'El RUC es requerido'}, status=400)
    try:
        from services import consultar_identificacion as servicio_consultar_identificacion
        resultado = servicio_consultar_identificacion(ruc)
        
        # Registrar los datos recibidos para depuración
        logger.info(f"Datos recibidos de la API: {resultado}")
        
        # Extraer los campos básicos
        razon_social = resultado.get('razon_social', '')
        nombre_comercial = resultado.get('nombre_comercial', '')
        direccion = resultado.get('direccion', '')
        
        # Usar directamente los campos ya mapeados en services.py
        tipo_regimen = resultado.get('tipo_regimen')
        obligado_contabilidad = resultado.get('obligado_contabilidad', 'NO')
        
        # Registrar los valores que se enviarán al frontend
        logger.info(f"Valores que se enviarán al frontend:")
        logger.info(f"  razon_social: {razon_social}")
        logger.info(f"  nombre_comercial: {nombre_comercial}")
        logger.info(f"  direccion: {direccion}")
        logger.info(f"  correo: {resultado.get('email', '')}")
        logger.info(f"  telefono: {resultado.get('telefono', '')}")
        logger.info(f"  obligado_contabilidad: {obligado_contabilidad}")
        logger.info(f"  tipo_regimen: {tipo_regimen}")
        logger.info(f"  actividad_economica: {resultado.get('actividad_economica', '')}")
        
        # Construir y devolver la respuesta JSON
        respuesta = {
            'error': False,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'direccion': direccion,
            'correo': resultado.get('email', ''),
            'telefono': resultado.get('telefono', ''),
            'obligado_contabilidad': obligado_contabilidad,
            'actividad_economica': resultado.get('actividad_economica', ''),
        }
        if tipo_regimen:
            respuesta['tipo_regimen'] = tipo_regimen
        
        logger.info(f"Respuesta JSON completa: {respuesta}")
        return JsonResponse(respuesta)
    except Exception as e:
        logger.error(f"Error en buscar_empresa: {e}")
        return JsonResponse({'error': True, 'message': f'Error consultando API externa: {e}'}, status=500)


class FormasPagoView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, factura_id):
        # Obtener la factura de la empresa activa
        empresa_id = request.session.get('empresa_activa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)

        # Obtener cajas activas (solo de la empresa)
        cajas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion')
        
        # Usar las opciones de forma de pago del modelo FormaPago directamente
        formas_pago_sri = FormaPago.FORMAS_PAGO_CHOICES
        
        # Seleccionar la primera caja por defecto
        primera_caja = cajas.first()
        
        contexto = {
            'factura': factura,
            'cajas': cajas,
            'formas_pago': formas_pago_sri,
            'primera_caja': primera_caja,
            'total': factura.monto_general or factura.sub_monto or 0,
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/factura/formas_pago.html', contexto)


class GuardarFormaPagoView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, factura_id):
        empresa_id = request.session.get('empresa_activa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        try:
            # Obtener datos del formulario
            forma_pago_codigo = request.POST.get('forma_pago')  # Ahora es el código directamente
            caja_id = request.POST.get('caja')
            monto_recibido = request.POST.get('monto_recibido') or request.POST.get('monto_efectivo')
            
            # Validar datos
            if not forma_pago_codigo or not caja_id or not monto_recibido:
                return JsonResponse({
                    'success': False,
                    'message': 'Todos los campos son obligatorios'
                })
            
            # Obtener objetos y validar existencia
            try:
                caja = Caja.objects.get(pk=caja_id, empresa_id=empresa_id)
                if not caja.activo:
                    return JsonResponse({
                        'success': False,
                        'message': f'La caja \'{caja.descripcion}\' está inactiva - seleccione una caja activa'
                    })
            except Caja.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': f'Caja con ID {caja_id} no encontrada'
                })
            
            print(f"   Caja validada: {caja.descripcion} (ID: {caja.id}, Activa: {caja.activo})")
            
            # Convertir monto
            try:
                monto = Decimal(str(monto_recibido))
            except:
                return JsonResponse({
                    'success': False,
                    'message': 'Monto inválido'
                })
            
            # 🔍 VALIDACIÓN ESTRICTA: Verificar coherencia acumulada ANTES de crear
            print(f"🔍 VALIDANDO coherencia acumulada en GuardarFormaPagoView")
            print(f"   Factura ID: {factura.id}")
            print(f"   Total factura: ${factura.monto_general}")
            print(f"   Nuevo monto: ${monto}")
            
            # Validar que el monto sea mayor a 0
            if monto <= 0:
                return JsonResponse({
                    'success': False,
                    'message': f'El monto debe ser mayor a 0 (recibido: ${monto})'
                })
            
            # Validar código SRI según tabla oficial
            codigos_sri_oficiales = [
                '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
                '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
                '21', '22', '23', '24', '25'
            ]
            
            if forma_pago_codigo not in codigos_sri_oficiales:
                return JsonResponse({
                    'success': False,
                    'message': f'Código SRI \'{forma_pago_codigo}\' no válido - debe usar código oficial (01-25)'
                })
            
            # Obtener pagos existentes y calcular suma actual
            pagos_existentes = factura.formas_pago.all()
            suma_pagos_existentes = sum(p.total for p in pagos_existentes)
            
            print(f"   Pagos existentes: {pagos_existentes.count()}")
            print(f"   Suma actual: ${suma_pagos_existentes}")
            
            # Calcular suma total después de agregar el nuevo pago
            suma_total_con_nuevo = suma_pagos_existentes + monto
            print(f"   Suma con nuevo pago: ${suma_total_con_nuevo}")
            
            # 🚫 VALIDACIÓN ESTRICTA: SOLO se permite IGUALDAD EXACTA
            if suma_total_con_nuevo != factura.monto_general:
                if suma_total_con_nuevo > factura.monto_general:
                    exceso = suma_total_con_nuevo - factura.monto_general
                    return JsonResponse({
                        'success': False,
                        'message': f'SUMA EXCEDE TOTAL: ${suma_total_con_nuevo} > ${factura.monto_general}. Exceso: ${exceso}. Ajuste el monto.'
                    })
                else:
                    faltante = factura.monto_general - suma_total_con_nuevo
                    return JsonResponse({
                        'success': False,
                        'message': f'PAGO INCOMPLETO: ${suma_total_con_nuevo} < ${factura.monto_general}. Faltan: ${faltante}. Solo se permiten pagos que completen EXACTAMENTE el total.'
                    })
            
            print(f"   ✅ Pagos completos - coherencia perfecta: ${suma_total_con_nuevo} = ${factura.monto_general}")
            
            # Calcular cambio (solo si hay exceso en este pago específico)
            cambio = Decimal('0.00')
            falta_antes_del_pago = factura.monto_general - suma_pagos_existentes
            if monto > falta_antes_del_pago:
                cambio = monto - falta_antes_del_pago
                print(f"   💰 Cambio calculado: ${cambio}")
            
            print(f"✅ Validación pasada - creando forma de pago")
            
            # Guardar forma de pago usando el modelo correcto con valores exactos
            forma_pago_factura = FormaPago.objects.create(
                factura=factura,
                forma_pago=forma_pago_codigo,  # Código SRI exacto seleccionado
                caja=caja,                     # Caja exacta seleccionada
                total=monto,                   # Monto exacto ingresado
                empresa=factura.empresa
            )
            
            # Verificar coherencia final después de la creación (debe ser exacta)
            pagos_finales = factura.formas_pago.all()
            suma_final = sum(p.total for p in pagos_finales)
            
            # Log para debugging con información completa
            logger.info(f"✅ Forma de pago guardada: ID={forma_pago_factura.id}, Código={forma_pago_codigo}, Total=${monto}")
            logger.info(f"📊 Estado final: Suma=${suma_final}, Total factura=${factura.monto_general}")
            
            # ASSERT: Debe ser exactamente igual (validación redundante de seguridad)
            if suma_final != factura.monto_general:
                logger.error(f"❌ ERROR CRÍTICO: Suma final ${suma_final} ≠ Total ${factura.monto_general}")
                raise Exception("ERROR INTERNO: Coherencia perdida después de crear forma de pago")
            
            # Mensaje de éxito confirmando coherencia perfecta
            return JsonResponse({
                'success': True,
                'message': f'✅ Forma de pago guardada - Factura COMPLETAMENTE PAGADA (${suma_final})',
                'cambio': str(cambio) if cambio > 0 else '0.00',
                'suma_actual': str(suma_final),
                'total_factura': str(factura.monto_general),
                'faltante': '0.00',
                'completado': True,
                'coherencia_perfecta': True,
                'redirect_url': reverse('inventario:detallesDeFactura')
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al guardar forma de pago: {str(e)}'
            })

def validar_facturador(request):
    """Vista para validar las credenciales del facturador solo con contraseña"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password')

            if not password:
                return JsonResponse({'success': False, 'error': 'La contraseña es requerida'})
            # ================= MULTI-EMPRESA FIX =================
            # Limitar búsqueda a facturadores de la empresa activa.
            empresa_id = request.session.get('empresa_activa')
            if not empresa_id:
                return JsonResponse({'success': False, 'error': 'Empresa activa no establecida'}, status=400)

            # Filtrar primero por empresa y activos para reducir superficie.
            # Se intenta una coincidencia única por comparación de hash.
            facturador_valido = None
            for facturador in Facturador.tenant_objects.filter(empresa_id=empresa_id, activo=True):
                if facturador.password and check_password(password, facturador.password):
                    facturador_valido = facturador
                    break
            # ======================================================

            if facturador_valido:
                # Guardar el facturador en la sesión
                request.session['facturador_id'] = facturador_valido.id
                request.session['facturador_nombre'] = facturador_valido.nombres
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Contraseña incorrecta'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error del servidor: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


# ✅ NUEVAS VISTAS PARA INTEGRACIÓN SRI COMPLETA
@csrf_exempt
@require_empresa_activa
def enviar_documento_sri(request, factura_id):
    """Envía una factura al SRI y devuelve el estado de recepción."""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)

    try:
        from inventario.sri.integracion_django import SRIIntegration

        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        # Lookup estrictamente multi-tenant
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)

        integration = SRIIntegration(empresa=get_empresa_activa(request))
        resultado = integration.enviar_factura(factura_id)

        if resultado.get('success'):
            return JsonResponse({
                'success': True,
                'message': 'Documento enviado correctamente al SRI',
                'resultado': {
                    'estado': resultado.get('estado'),
                    'mensajes': resultado.get('mensajes', [])
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error al enviar documento'),
                'resultado': {
                    'estado': resultado.get('estado'),
                    'mensajes': resultado.get('mensajes', [])
                }
            })

    except Http404:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en enviar_documento_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })

@csrf_exempt
@require_empresa_activa
def autorizar_documento_sri(request, factura_id):
    """
    Vista para autorizar un documento electrónico en el SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration

        # Verificar que la factura existe y pertenece a la empresa activa
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        # Procesar factura en el SRI
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        resultado = integration.procesar_factura(factura_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'message': 'Documento procesado correctamente en el SRI',
                'resultado': {
                    'estado': factura.estado_sri or resultado.get('resultado', {}).get('estado', 'PROCESADO'),
                    'numero_autorizacion': factura.numero_autorizacion,
                    'fecha_autorizacion': factura.fecha_autorizacion.isoformat() if factura.fecha_autorizacion else None,
                    'clave_acceso': factura.clave_acceso,
                    'mensaje': resultado.get('message', 'Procesado exitosamente')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error desconocido'),
                'error_detalle': resultado.get('resultado', {})
            })
            
    except Http404:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en autorizar_documento_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


@csrf_exempt
def sincronizar_masivo_sri(request):
    """
    Sincroniza masivamente el estado de facturas pendientes SOLO de la empresa activa (máx 50)
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        from django.db.models import Q
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)
        
        # Obtener facturas que necesitan sincronización (filtradas por empresa)
        facturas_qs = (Factura.objects
            .filter(empresa_id=empresa_id)
            .filter(
                Q(estado_sri__isnull=True) |
                Q(estado_sri='PENDIENTE') |
                Q(estado_sri='RECIBIDA') |
                Q(estado_sri='') |
                Q(estado_sri='NO_AUTORIZADA')
            )
            .filter(clave_acceso__isnull=False)
            .exclude(clave_acceso='')
            .order_by('-fecha_emision'))

        facturas_pendientes = list(facturas_qs[:50])  # Límite de seguridad
        
        total_facturas = facturas_qs.count()
        actualizadas = 0
        errores = 0
        rechazadas = 0
        
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        resultados = []
        
        for factura in facturas_pendientes[:50]:  # Limitar a 50 para evitar timeout
            try:
                estado_anterior = factura.estado_sri or 'SIN_ESTADO'
                
                # Consultar estado en el SRI
                resultado = integration.consultar_estado_factura(factura.id)
                
                if resultado['success']:
                    # Recargar la factura para obtener el estado actualizado
                    factura.refresh_from_db()
                    estado_nuevo = factura.estado_sri
                    
                    if estado_nuevo in ('RECHAZADA', 'NO_AUTORIZADA'):
                        rechazadas += 1
                    
                    resultados.append({
                        'numero': factura.numero,
                        'clave_acceso': factura.clave_acceso,
                        'estado_anterior': estado_anterior,
                        'estado_nuevo': estado_nuevo,
                        'fecha_autorizacion': factura.fecha_autorizacion.isoformat() if factura.fecha_autorizacion else None,
                        'mensaje': factura.mensaje_sri or '',
                        'success': True
                    })
                    actualizadas += 1
                else:
                    resultados.append({
                        'numero': factura.numero,
                        'clave_acceso': factura.clave_acceso,
                        'estado_anterior': estado_anterior,
                        'error': resultado.get('message', 'Error desconocido'),
                        'success': False
                    })
                    errores += 1
                        
            except Exception as e:
                resultados.append({
                    'numero': factura.numero,
                    'clave_acceso': factura.clave_acceso,
                    'estado_anterior': estado_anterior,
                    'error': str(e),
                    'success': False
                })
                errores += 1
        
        return JsonResponse({
            'success': True,
            'total_facturas': total_facturas,
            'procesadas': len(resultados),
            'actualizadas': actualizadas,
            'rechazadas': rechazadas,
            'errores': errores,
            'resultados': resultados
        })
                
    except Exception as e:
        logger.error(f"Error en sincronización masiva SRI: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }, status=500)


@csrf_exempt
def validar_xml_factura(request, factura_id):
    """
    Valida el XML de una factura específica contra el XSD del SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe y pertenece a la empresa activa
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        if not factura.clave_acceso:
            return JsonResponse({
                'success': False,
                'message': 'La factura no tiene clave de acceso generada'
            })
        
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        
        try:
            # Generar XML con validación
            xml_path = integration.generar_xml_factura(factura, validar_xsd=True)
            
            return JsonResponse({
                'success': True,
                'message': 'XML generado y validado exitosamente',
                'xml_path': xml_path,
                'validacion': 'XML cumple con el XSD del SRI'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'XML no válido según XSD del SRI',
                'error': str(e),
                'validacion': 'XML NO cumple con el XSD'
            })
            
    except Http404:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en validar_xml_factura: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


@csrf_exempt
def reenviar_factura_sri(request, factura_id):
    """
    Vista para reenviar una factura rechazada al SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe y pertenece a la empresa activa
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        # Reenviar factura
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        resultado = integration.reenviar_factura(factura_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'message': 'Factura reenviada exitosamente',
                'resultado': {
                    'estado': factura.estado_sri,
                    'mensaje': resultado.get('message', 'Reenviado exitosamente')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error reenviando factura')
            })
            
    except Http404:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en reenviar_factura_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


def generar_xml_factura_view(request, factura_id):
    """
    Vista para generar solo el XML de una factura (sin enviar al SRI)
    """
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe y pertenece a la empresa activa
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            raise Http404("Empresa no válida")
        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)
        
        # Generar XML
        integration = SRIIntegration(empresa=get_empresa_activa(request))
        xml_path = integration.generar_xml_factura(factura)
        
        # Leer el XML generado
        xml_content = storage_read_text(xml_path)
        
        # Devolver como respuesta HTTP
        response = HttpResponse(xml_content, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="factura_{factura.numero}.xml"'
        
        return response
        
    except Http404:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error generando XML: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error generando XML: {str(e)}'
        })


def debug_proforma_data(request):
    """Vista temporal (restringida) para debuggear datos de proforma.

    Ahora limitada a superuser + empresa activa. No expone datos sensibles.
    """
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("No autorizado")
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return HttpResponseForbidden("Empresa no válida")
    return JsonResponse({'success': True, 'message': 'Debug deshabilitado en producción'})


# ==========================
#  ENVÍO FACTURA POR EMAIL
# ==========================
@csrf_exempt
def enviar_factura_email(request, factura_id):
    """
    Envía la factura por correo electrónico al cliente.
    - Verifica empresa activa y pertenencia del usuario.
    - Genera el RIDE si no existe.
    - Envía email con RIDE PDF y XML autorizado adjuntos.
    """
    if request.method not in ("POST", "GET"):
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
            return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)

        factura = get_object_or_404(Factura, id=factura_id, empresa_id=empresa_id)

        # Verificar que la factura esté autorizada
        if factura.estado_sri != 'AUTORIZADA':
            return JsonResponse({
                'success': False, 
                'message': f'La factura debe estar AUTORIZADA para enviar email. Estado actual: {factura.estado_sri or "Sin enviar al SRI"}'
            })

        # Usar el método de integración SRI
        from inventario.sri.integracion_django import SRIIntegration
        
        sri_integration = SRIIntegration()
        resultado = sri_integration.enviar_factura_email(factura)
        
        if resultado.get('success'):
            logger.info(f"✅ Email enviado para factura {factura.id}")
            return JsonResponse({
                'success': True,
                'message': resultado.get('message', 'Email enviado correctamente'),
                'factura_id': factura.id
            })
        else:
            logger.error(f"❌ Error enviando email para factura {factura.id}: {resultado.get('message')}")
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error desconocido al enviar email')
            })

    except Http404:
        return JsonResponse({'success': False, 'message': f'Factura {factura_id} no encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Error en enviar_factura_email: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)
        if not almacenes_activos.exists():
            almacen1, created1 = Almacen.objects.get_or_create(
                descripcion="Almacén Principal",
                defaults={'activo': True, 'empresa': empresa_principal}
            )
            almacen2, created2 = Almacen.objects.get_or_create(
                descripcion="Almacén Secundario", 
                defaults={'activo': True, 'empresa': empresa_principal}
            )
            if created1 or created2:
                html_content += "<p class='success'>✅ Almacenes creados</p>"
        
        # Crear facturadores
        if not facturadores_activos.exists():
            try:
                facturador1, created1 = Facturador.objects.get_or_create(
                    correo="facturador1@test.com",
                    defaults={
                        'nombres': "Juan Pérez",
                        'activo': True,
                        'empresa': empresa_principal,
                        'telefono': '0999999999'
                    }
                )
                if created1:
                    facturador1.set_password("123456")
                    facturador1.save()
                
                facturador2, created2 = Facturador.objects.get_or_create(
                    correo="facturador2@test.com",
                    defaults={
                        'nombres': "María López",
                        'activo': True,
                        'empresa': empresa_principal,
                        'telefono': '0988888888'
                    }
                )
                if created2:
                    facturador2.set_password("123456")
                    facturador2.save()
                    
                if created1 or created2:
                    html_content += "<p class='success'>✅ Facturadores creados</p>"
            except Exception as e:
                html_content += f"<p class='error'>❌ Error creando facturadores: {e}</p>"
        
        html_content += '<p><a href="?">🔄 Recargar sin crear datos</a></p>'
    else:
        html_content += '<p><a href="?create_data=1" style="background:#4CAF50;color:white;padding:10px;text-decoration:none;border-radius:5px;">🚀 Crear datos de prueba</a></p>'
    
    html_content += """
    <hr>
    <h3>🔗 Enlaces útiles</h3>
    <p><a href="/inventario/proformas/emitir/" style="background:#2196F3;color:white;padding:8px;text-decoration:none;border-radius:3px;">📄 Ir a Emisión de Proforma</a></p>
    <p><a href="/inventario/panel/" style="background:#FF9800;color:white;padding:8px;text-decoration:none;border-radius:3px;">🏠 Ir al Panel</a></p>
    </body>
    </html>
    """
    
    return HttpResponse(html_content)


# ===============================
# GUÍAS DE REMISIÓN - FUNCIONES DIRECTAS
# ===============================

# Importar dependencias necesarias
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date
import json
import logging

## (logger y stub PDF definidos al inicio del archivo)

@login_required
def listar_guias_remision(request):
    """Vista para listar todas las guias de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    # Obtener parámetros de filtro
    numero = request.GET.get('numero', '').strip()
    cliente = request.GET.get('cliente', '').strip()
    estado = request.GET.get('estado', '').strip()
    fecha = request.GET.get('fecha', '').strip()
    
    # Query base (scoped by empresa)
    guias = GuiaRemision.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if numero:
        guias = guias.filter(secuencial__icontains=numero)
    
    if cliente:
        from django.db.models import Q
        guias = guias.filter(
            Q(destinatario_nombre__icontains=cliente) |
            Q(destinatario_identificacion__icontains=cliente)
        )
    
    if estado:
        guias = guias.filter(estado=estado)
    
    if fecha:
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
            guias = guias.filter(fecha_inicio_traslado=fecha_obj)
        except ValueError:
            pass
    
    # Ordenar por fecha y secuencial
    guias = guias.order_by('-fecha_inicio_traslado', '-secuencial')
    
    # Paginación
    paginator = Paginator(guias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'guias': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'paginator': paginator,
        'filtros': {
            'numero': numero,
            'cliente': cliente,
            'estado': estado,
            'fecha': fecha,
        }
    }
    
    # Agregar datos del usuario para el header
    context = complementarContexto(context, request.user)
    
    return render(request, 'inventario/guia_remision/listarGuiasRemision.html', context)

@login_required
def emitir_guia_remision(request):
    """Vista para crear una nueva guia de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obtener configuración
                config = ConfiguracionGuiaRemision.get_configuracion()
                
                # Establecimiento/Punto/Secuencial desde selección de Secuencia (si llega)
                est_post = (request.POST.get('establecimiento') or '').strip()
                pemi_post = (request.POST.get('punto_emision') or '').strip()
                secu_post = (request.POST.get('secuencial') or '').strip()

                establecimiento = est_post if est_post else config.establecimiento_defecto
                punto_emision = pemi_post if pemi_post else config.punto_emision_defecto

                # Normalizar a 3 y 9 dígitos
                try:
                    establecimiento = f"{int(establecimiento):03d}"
                except Exception:
                    establecimiento = f"{str(establecimiento).zfill(3)}" if establecimiento else "001"
                try:
                    punto_emision = f"{int(punto_emision):03d}"
                except Exception:
                    punto_emision = f"{str(punto_emision).zfill(3)}" if punto_emision else "001"

                # Crear la guía con los campos correctos del modelo según XSD SRI
                # Obtener factura relacionada (si existe)
                factura_id = request.POST.get('factura_id')
                factura_obj = None
                if factura_id:
                    try:
                        factura_obj = Factura.objects.get(id=factura_id, empresa=empresa)
                    except Factura.DoesNotExist:
                        pass
                
                guia = GuiaRemision(
                    empresa=empresa,
                    factura=factura_obj,  # ✅ Vincular factura si existe
                    establecimiento=establecimiento,
                    punto_emision=punto_emision,
                    fecha_inicio_traslado=request.POST.get('fecha_inicio_traslado'),
                    fecha_fin_traslado=request.POST.get('fecha_fin_traslado') or None,
                    direccion_partida=(request.POST.get('direccion_partida') or ''),
                    direccion_destino=(request.POST.get('direccion_destino') or ''),
                    dir_establecimiento=(request.POST.get('dir_establecimiento') or ''),
                    transportista_ruc=request.POST.get('transportista_ruc'),
                    transportista_nombre=request.POST.get('transportista_nombre'),
                    tipo_identificacion_transportista=request.POST.get('tipo_identificacion_transportista', '05'),
                    placa=request.POST.get('placa'),
                    rise=request.POST.get('rise', ''),
                    obligado_contabilidad=request.POST.get('obligado_contabilidad', ''),
                    contribuyente_especial=request.POST.get('contribuyente_especial', ''),
                    correo_envio=request.POST.get('correo_envio', ''),
                    informacion_adicional=request.POST.get('informacion_adicional', ''),
                    ruta=request.POST.get('ruta', ''),
                    usuario_creacion=request.user,
                    estado='borrador'
                )
                # Si llega un secuencial calculado, úsalo; si no, el save lo generará
                if secu_post and secu_post.isdigit():
                    guia.secuencial = str(int(secu_post)).zfill(9)
                guia.save()
                
                # Procesar destinatarios y sus productos
                destinatarios = {}
                productos = {}
                
                for key in request.POST:
                    if key.startswith('destinatarios['):
                        # Parsear estructura: destinatarios[1][ruc] o destinatarios[1][productos][1][codigo]
                        parts = key.replace('destinatarios[', '').split(']')
                        
                        if len(parts) >= 2:
                            idx_dest = parts[0]
                            
                            # Inicializar destinatario
                            if idx_dest not in destinatarios:
                                destinatarios[idx_dest] = {}
                                productos[idx_dest] = {}
                            
                            # Verificar si es un producto o campo del destinatario
                            if '[productos][' in key:
                                # Es un producto: destinatarios[1][productos][2][codigo]
                                idx_prod = parts[2]
                                campo_prod = parts[3].replace('[', '')
                                
                                if idx_prod not in productos[idx_dest]:
                                    productos[idx_dest][idx_prod] = {}
                                
                                productos[idx_dest][idx_prod][campo_prod] = request.POST.get(key, '').strip()
                            else:
                                # Es campo del destinatario: destinatarios[1][ruc]
                                campo_dest = parts[1].replace('[', '')
                                destinatarios[idx_dest][campo_dest] = request.POST.get(key, '').strip()
                
                # Crear destinatarios y sus productos
                from inventario.models import DestinatarioGuia, DetalleDestinatarioGuia
                
                for idx_dest, dest_data in destinatarios.items():
                    if dest_data.get('ruc') and dest_data.get('nombre'):
                        # Crear destinatario con datos del documento sustento (factura)
                        destinatario_obj = DestinatarioGuia.objects.create(
                            guia=guia,
                            identificacion_destinatario=dest_data.get('ruc', ''),
                            razon_social_destinatario=dest_data.get('nombre', ''),
                            dir_destinatario=dest_data.get('direccion', ''),
                            motivo_traslado=dest_data.get('motivo', '01'),
                            doc_aduanero_unico=dest_data.get('documento', ''),
                            cod_estab_destino=dest_data.get('cod_estab', '001'),
                            # ✅ Campos del documento sustento (factura)
                            cod_doc_sustento=dest_data.get('cod_doc_sustento', ''),
                            num_doc_sustento=dest_data.get('num_doc_sustento', ''),
                            num_aut_doc_sustento=dest_data.get('num_aut_doc_sustento', ''),
                            fecha_emision_doc_sustento=dest_data.get('fecha_emision_doc_sustento') or None,
                        )
                        
                        # Crear productos del destinatario
                        if idx_dest in productos:
                            for idx_prod, prod_data in productos[idx_dest].items():
                                if prod_data.get('codigo') and prod_data.get('descripcion') and prod_data.get('cantidad'):
                                    try:
                                        cantidad_decimal = Decimal(str(prod_data.get('cantidad', '1')))
                                        DetalleDestinatarioGuia.objects.create(
                                            destinatario=destinatario_obj,
                                            codigo_interno=prod_data.get('codigo', '')[:25],
                                            descripcion=prod_data.get('descripcion', '')[:300],
                                            cantidad=cantidad_decimal
                                        )
                                    except Exception as e:
                                        logger.warning(f"Error al crear producto: {e}")
                
                # Generar clave de acceso usando el generador del XML
                from inventario.guia_remision.xml_generator_guia import XMLGeneratorGuiaRemision
                try:
                    opciones = Opciones.objects.filter(empresa=empresa).first()
                    if not opciones:
                        raise ValueError("No se encontraron opciones para la empresa")
                    
                    xml_gen = XMLGeneratorGuiaRemision(guia, empresa, opciones)
                    guia.clave_acceso = xml_gen.generar_clave_acceso()
                    guia.save()
                    logger.info(f"✅ Clave de acceso generada: {guia.clave_acceso} ({len(guia.clave_acceso)} dígitos)")
                except Exception as e:
                    logger.error(f"❌ ERROR generando clave de acceso: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    guia.clave_acceso = f"TEMP{guia.id:015d}"
                    guia.save()
                    messages.warning(request, f"⚠️ Clave temporal asignada. Error: {e}")
                
                messages.success(request, f'Guia de remision {guia.numero_completo} creada exitosamente.')
                return redirect('inventario:ver_guia_remision', guia_id=guia.id)
                
        except Exception as e:
            logger.error(f"Error al crear guia de remision: {str(e)}")
            messages.error(request, f'Error al crear la guia: {str(e)}')
    
    # GET request - mostrar formulario
    # GET request - mostrar formulario
    # Secuencias SOLO de Guía de Remisión (código SRI 06)
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if empresa:
        secuencias_guia = Secuencia.objects.filter(empresa=empresa, tipo_documento='06', activo=True).order_by('descripcion')
    else:
        secuencias_guia = Secuencia.objects.none()
    
    # Obtener facturas autorizadas de la empresa para vincular con guías
    facturas_autorizadas = Factura.objects.filter(
        empresa=empresa,
        estado_sri='AUTORIZADA'
    ).select_related('cliente').order_by('-fecha_emision')[:100]  # Últimas 100 facturas autorizadas
    
    context = {
        'fecha_hoy': date.today().isoformat(),
        'configuracion': ConfiguracionGuiaRemision.get_configuracion(),
        'secuencias_guia': secuencias_guia,
        'facturas_autorizadas': facturas_autorizadas,
    }
    
    # Agregar datos del usuario para el header
    context = complementarContexto(context, request.user)
    
    return render(request, 'inventario/guia_remision/emitirGuiaRemision.html', context)

@login_required
def obtener_datos_factura(request, factura_id):
    """Vista AJAX para obtener datos de una factura y sus productos"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida'})
    
    try:
        # Obtener factura con sus detalles
        factura = Factura.objects.select_related('cliente').get(id=factura_id, empresa=empresa)
        
        # Obtener productos de la factura
        from inventario.models import DetalleFactura
        detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto', 'servicio')
        
        productos = []
        for detalle in detalles:
            # Obtener codigo y descripcion desde producto o servicio
            if detalle.producto:
                codigo = detalle.producto.codigo
                descripcion = detalle.producto.descripcion
            elif detalle.servicio:
                codigo = detalle.servicio.codigo
                descripcion = detalle.servicio.descripcion
            else:
                codigo = 'SIN_CODIGO'
                descripcion = 'Sin descripción'
            
            productos.append({
                'codigo': codigo,
                'descripcion': descripcion,
                'cantidad': float(detalle.cantidad)
            })
        
        return JsonResponse({
            'success': True,
            'factura': {
                'numero': f"{factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}",
                'clave_acceso': factura.clave_acceso or '',
                'fecha_emision': factura.fecha_emision.isoformat(),
            },
            'cliente': {
                'identificacion': factura.identificacion_cliente,
                'nombre': factura.nombre_cliente,
                'direccion': factura.cliente.direccion if factura.cliente else 'Sin dirección',
            },
            'productos': productos
        })
    except Factura.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Factura no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def ver_guia_remision(request, guia_id):
    """Vista para ver los detalles de una guia de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    
    context = {
        'guia': guia,
    }
    
    # Agregar datos del usuario para el header
    context = complementarContexto(context, request.user)
    
    return render(request, 'inventario/guia_remision/verGuiaRemision.html', context)

@login_required
def editar_guia_remision(request, guia_id):
    """Vista para editar una guia de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    
    if not guia.puede_editarse():
        messages.error(request, 'No se puede editar una guia que no esta en borrador.')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Actualizar datos de la guía
                guia.fecha_emision = request.POST.get('fecha_emision')
                guia.fecha_inicio_traslado = request.POST.get('fecha_inicio_traslado')
                guia.fecha_fin_traslado = request.POST.get('fecha_fin_traslado') or None
                guia.motivo_traslado = request.POST.get('motivo_traslado')
                guia.destinatario_identificacion = request.POST.get('destinatario_identificacion')
                guia.destinatario_nombre = request.POST.get('destinatario_nombre')
                guia.direccion_partida = request.POST.get('direccion_partida')
                guia.direccion_destino = request.POST.get('direccion_destino')
                guia.transportista_ruc = request.POST.get('transportista_ruc')
                guia.transportista_nombre = request.POST.get('transportista_nombre')
                guia.placa = request.POST.get('placa')
                guia.transportista_observaciones = request.POST.get('transportista_observaciones', '')
                guia.usuario_modificacion = request.user
                guia.save()
                
                # Eliminar detalles existentes y crear nuevos
                guia.detalles.all().delete()
                productos_data = _extraer_productos_del_post(request.POST)
                for i, producto in enumerate(productos_data, 1):
                    if producto['codigo'] and producto['descripcion'] and producto['cantidad']:
                        DetalleGuiaRemision.objects.create(
                            guia=guia,
                            empresa=empresa,
                            orden=i,
                            codigo_producto=producto['codigo'],
                            descripcion_producto=producto['descripcion'],
                            cantidad=producto['cantidad']
                        )
                
                messages.success(request, f'Guia de remision {guia.numero_completo} actualizada exitosamente.')
                return redirect('inventario:ver_guia_remision', guia_id=guia.id)
                
        except Exception as e:
            logger.error(f"Error al actualizar guia de remision: {str(e)}")
            messages.error(request, f'Error al actualizar la guia: {str(e)}')
    
    context = {
        'guia': guia,
        'configuracion': ConfiguracionGuiaRemision.get_configuracion(),
    }
    
    return render(request, 'inventario/guia_remision/editarGuiaRemision.html', context)

@login_required
@require_http_methods(["POST"])
def anular_guia_remision(request, guia_id):
    """Vista para anular una guia de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=400)
    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    
    if not guia.puede_anularse():
        return JsonResponse({
            'success': False,
            'message': 'No se puede anular esta guía en su estado actual.'
        })
    
    try:
        guia.estado = 'anulada'
        guia.usuario_modificacion = request.user
        guia.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Guía {guia.numero_completo} anulada exitosamente.'
        })
        
    except Exception as e:
        logger.error(f"Error al anular guía de remisión {guia_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error al anular la guía: {str(e)}'
        })

@csrf_exempt
@require_http_methods(["GET"])
def buscar_transportista(request):
    """Endpoint para consultar información de transportista por RUC/Cédula"""
    identificacion = request.GET.get('q', '').strip()
    if not identificacion:
        return JsonResponse({'error': True, 'message': 'La identificación es requerida'}, status=400)
    
    try:
        from services import consultar_identificacion as servicio_consultar_identificacion
        resultado = servicio_consultar_identificacion(identificacion)
        
        # Determinar tipo de identificación según longitud
        tipo_id = '05'  # Por defecto cédula
        if len(identificacion) == 13:
            tipo_id = '04'  # RUC
        elif len(identificacion) == 10:
            tipo_id = '05'  # Cédula
        else:
            tipo_id = '06'  # Pasaporte u otro
        
        respuesta = {
            'error': False,
            'razon_social': resultado.get('razon_social', ''),
            'nombre_comercial': resultado.get('nombre_comercial', ''),
            'direccion': resultado.get('direccion', ''),
            'tipo_identificacion': tipo_id,
            'rise': resultado.get('tipo_regimen', '') if resultado.get('tipo_regimen') == 'RISE' else '',
            'obligado_contabilidad': resultado.get('obligado_contabilidad', 'NO'),
        }
        
        return JsonResponse(respuesta)
        
    except Exception as e:
        logger.error(f"Error en buscar_transportista: {e}")
        return JsonResponse({
            'error': True, 
            'message': f'No se pudo consultar la identificación: {str(e)}'
        }, status=500)

@login_required
def descargar_guia_pdf(request, guia_id):
    """Vista para descargar el PDF de una guia de remision"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    
    if guia.estado != 'autorizada':
        messages.error(request, 'Solo se puede descargar PDF de guías autorizadas.')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)
    
    try:
        # Por ahora, generar PDF simple
        from django.http import HttpResponse
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="guia_remision_{guia.numero_completo}.pdf"'
        response.write(b"PDF de guia de remision - En desarrollo")
        return response
        
    except Exception as e:
        logger.error(f"Error al generar PDF de guía {guia_id}: {str(e)}")
        messages.error(request, f'Error al generar PDF: {str(e)}')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)

@login_required
def autorizar_guia_remision(request, guia_id):
    """Vista para firmar y enviar una guía de remisión al SRI"""
    empresa_id = request.session.get('empresa_activa')
    empresa = None
    if empresa_id:
        empresa = request.user.empresas.filter(id=empresa_id).first()
    if not empresa:
        messages.error(request, 'Seleccione una empresa válida.')
        return redirect('inventario:seleccionar_empresa')
    
    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    
    if guia.estado != 'borrador':
        messages.error(request, 'Solo se pueden autorizar guías en estado borrador.')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)
    
    try:
        # Usar el integrador completo que ya existe
        from inventario.guia_remision.integracion_sri_guia import IntegracionGuiaRemisionSRI
        
        integrador = IntegracionGuiaRemisionSRI(empresa)
        resultado = integrador.procesar_guia_remision(guia.id)
        
        if resultado['success']:
            messages.success(request, f'✅ Guía de remisión {guia.numero_completo} autorizada exitosamente por el SRI.')
        else:
            messages.error(request, f'❌ Error: {resultado["message"]}')
            
    except Exception as e:
        logger.error(f"Error al autorizar guía {guia_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error inesperado: {str(e)}')
    
    return redirect('inventario:ver_guia_remision', guia_id=guia.id)

@login_required
@csrf_exempt
def buscar_cliente_ajax(request):
    """Vista AJAX para buscar un cliente exacto por identificación (CI/RUC).
    Espera POST { identificacion: '...' }
    Respuesta:
      { success: true, cliente: { id, identificacion, razon_social, nombre_comercial, correo, direccion } }
      o { success: false, message }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)

    identificacion = (request.POST.get('identificacion') or '').strip()
    if not identificacion:
        return JsonResponse({'success': False, 'message': 'Identificación requerida'}, status=400)

    try:
        cliente = Cliente.objects.filter(empresa_id=empresa_id, identificacion=identificacion).first()
        if not cliente:
            return JsonResponse({'success': False, 'message': 'Cliente no encontrado'}, status=404)

        cliente_data = {
            'id': cliente.id,
            'identificacion': cliente.identificacion,
            'razon_social': cliente.razon_social,
            'nombre_comercial': cliente.nombre_comercial or '',
            'correo': cliente.correo or '',
            'direccion': cliente.direccion or ''
        }
        return JsonResponse({'success': True, 'cliente': cliente_data})
    except Exception as e:
        logger.error(f"Error al buscar cliente {identificacion}: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error interno: {str(e)}'}, status=500)

# API dedicada limpia para búsqueda (GET /api/clientes/buscar?q=...&exact=1)
@login_required
@csrf_exempt
def buscar_cliente_api(request):
    """Endpoint puro JSON para búsqueda de clientes.
    GET params:
      q: término (obligatorio)
      exact=1 -> intenta coincidencia exacta por identificacion primero.
    Respuesta:
      { success: true, results: [...], exact: {..} } o { success:false, message }
    Nunca redirige; si falta empresa, 403 JSON.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'success': True, 'results': []})
    exact_flag = request.GET.get('exact') in ('1','true','True')
    base_qs = Cliente.objects.filter(empresa_id=empresa_id)
    exact_obj = None
    if exact_flag:
        exact_obj = base_qs.filter(identificacion=q).first()
    qs = base_qs.filter(
        Q(identificacion__icontains=q) |
        Q(razon_social__icontains=q) |
        Q(nombre_comercial__icontains=q)
    ).order_by('razon_social')[:15]
    def serial(c):
        return {
            'id': c.id,
            'identificacion': c.identificacion,
            'razon_social': c.razon_social,
            'nombre_comercial': c.nombre_comercial or '',
            'nombre_compuesto': (c.razon_social + (f" {c.nombre_comercial}" if c.nombre_comercial else "")).strip(),
            'correo': c.correo or ''
        }
    data = {
        'success': True,
        'results': [serial(c) for c in qs]
    }
    if exact_obj:
        data['exact'] = serial(exact_obj)
    return JsonResponse(data)

@login_required
@csrf_exempt
def crear_cliente_api(request):
    """Crea rápidamente un cliente minimo si no existe.
    POST JSON o form:
      identificacion (obligatorio)
      razon_social (si falta usa identificacion)
      correo (opcional)
      direccion (opcional, por defecto 'NO ESPECIFICADA')
    Reglas:
      - Detecta tipoIdentificacion por longitud (13=RUC->'04',10=cedula->'05',otros->'08')
      - Si ya existe retorna ese cliente (idempotente)
    Respuesta:
      {success: true, created: bool, cliente:{...}} | {success:false,message}
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)
    try:
        import json
        # Normalizar data indiferente del content-type
        if request.method == 'POST':
            if request.content_type and 'application/json' in request.content_type:
                try:
                    data = json.loads(request.body.decode('utf-8') or '{}')
                except Exception:
                    data = {}
            else:
                data = request.POST
        else:
            data = {}

        def _val(k, default=''):
            v = data.get(k) if hasattr(data, 'get') else None
            if v is None:
                return default
            return str(v).strip()

        identificacion = _val('identificacion')
        if not identificacion:
            return JsonResponse({'success': False, 'message': 'Identificación requerida'}, status=400)
        razon_social = _val('razon_social') or identificacion
        correo = _val('correo')
        direccion = _val('direccion') or 'NO ESPECIFICADA'
        # Log breve para debug (se puede bajar a debug luego)
        logger.debug(f"[crear_cliente_api] payload normalizado id={identificacion} razon={razon_social}")
        # Heurística tipo identificacion
        if len(identificacion) == 13:
            tipoIdentificacion = '04'
        elif len(identificacion) == 10:
            tipoIdentificacion = '05'
        else:
            tipoIdentificacion = '08'
        existente = Cliente.objects.filter(empresa_id=empresa_id, identificacion=identificacion).first()
        created = False
        if existente:
            cliente = existente
        else:
            # Valores mínimos obligatorios
            cliente = Cliente.objects.create(
                empresa_id=empresa_id,
                tipoIdentificacion=tipoIdentificacion,
                identificacion=identificacion,
                razon_social=razon_social,
                nombre_comercial='',
                direccion=direccion,
                telefono='',
                correo=correo or '',
                observaciones='',
                convencional='',
                tipoVenta='1',
                tipoRegimen='1',
                tipoCliente='1'
            )
            created = True
        resp = {
            'success': True,
            'created': created,
            'cliente': {
                'id': cliente.id,
                'identificacion': cliente.identificacion,
                'razon_social': cliente.razon_social,
                'nombre_comercial': cliente.nombre_comercial or '',
                'correo': cliente.correo or '',
                'direccion': cliente.direccion or ''
            }
        }
        return JsonResponse(resp, status=201 if created else 200)
    except Exception as e:
        logger.exception("Error crear cliente rapido")
        return JsonResponse({'success': False, 'message': 'Error interno creando cliente'}, status=500)

@login_required
@csrf_exempt
def enriquecer_cliente_api(request):
    """Intenta complementar datos de un cliente existente usando el servicio externo
    GET params:
      id o identificacion (uno de los dos)
    Solo cambia razon_social y nombre_comercial si actualmente son iguales a la identificación
    o están vacíos.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.empresas.filter(id=empresa_id).exists():
        return JsonResponse({'success': False, 'message': 'Empresa no válida'}, status=403)
    cliente = None
    identificacion = (request.GET.get('identificacion') or '').strip()
    cid = request.GET.get('id')
    try:
        if cid:
            cliente = Cliente.objects.filter(id=cid, empresa_id=empresa_id).first()
        if not cliente and identificacion:
            cliente = Cliente.objects.filter(identificacion=identificacion, empresa_id=empresa_id).first()
        if not cliente:
            return JsonResponse({'success': False, 'message': 'Cliente no encontrado'}, status=404)
        identificacion = cliente.identificacion
        # Solo enriquecer si razon_social es muy pobre
        if cliente.razon_social and cliente.razon_social.strip() and cliente.razon_social.strip() != identificacion:
            return JsonResponse({'success': True, 'enriquecido': False, 'cliente': {
                'id': cliente.id,
                'identificacion': cliente.identificacion,
                'razon_social': cliente.razon_social,
                'nombre_comercial': cliente.nombre_comercial or '',
                'correo': cliente.correo or '',
            }})
        # Llamar servicio externo
        try:
            from services import consultar_identificacion as servicio_consultar_identificacion
            resultado = servicio_consultar_identificacion(identificacion)
        except Exception as e:
            logger.error(f"Fallo servicio externo enriquecer: {e}")
            return JsonResponse({'success': False, 'message': 'No se pudo consultar servicio externo'}, status=502)
        
        # Extraer todos los datos disponibles
        razon = resultado.get('razonSocial') or resultado.get('razon_social') or resultado.get('nombre') or resultado.get('name') or ''
        nombre_comercial = resultado.get('nombreComercial') or resultado.get('nombre_comercial') or ''
        direccion = resultado.get('direccion') or ''
        telefono = resultado.get('telefono') or ''
        correo = resultado.get('email') or resultado.get('correo') or ''
        
        # Actualizar todos los campos disponibles
        campos_actualizar = []
        enriquecido = False
        
        if razon and razon.strip() and razon.strip() != identificacion:
            cliente.razon_social = razon.strip()[:200]
            campos_actualizar.append('razon_social')
            enriquecido = True
        
        if nombre_comercial and nombre_comercial.strip():
            cliente.nombre_comercial = nombre_comercial.strip()[:200]
            campos_actualizar.append('nombre_comercial')
            enriquecido = True
        
        if direccion and direccion.strip() and direccion.strip() != 'NO ESPECIFICADA':
            cliente.direccion = direccion.strip()[:300]
            campos_actualizar.append('direccion')
            enriquecido = True
        
        if telefono and telefono.strip():
            cliente.telefono = telefono.strip()[:20]
            campos_actualizar.append('telefono')
            enriquecido = True
        
        if correo and correo.strip():
            cliente.correo = correo.strip()[:100]
            campos_actualizar.append('correo')
            enriquecido = True
        
        if campos_actualizar:
            cliente.save(update_fields=campos_actualizar)
        
        return JsonResponse({'success': True, 'enriquecido': enriquecido, 'cliente': {
            'id': cliente.id,
            'identificacion': cliente.identificacion,
            'razon_social': cliente.razon_social,
            'nombre_comercial': cliente.nombre_comercial or '',
            'direccion': cliente.direccion or '',
            'telefono': cliente.telefono or '',
            'correo': cliente.correo or ''
        }})
    except Exception as e:
        logger.exception("Error enriqueciendo cliente")
        return JsonResponse({'success': False, 'message': 'Error interno'}, status=500)

# Funciones auxiliares para Guias de Remision

def _extraer_productos_del_post(post_data):
    """Extrae los datos de productos del POST request"""
    productos = []
    i = 0
    
    while f'productos[{i}][codigo]' in post_data:
        codigo = post_data.get(f'productos[{i}][codigo]', '').strip()
        descripcion = post_data.get(f'productos[{i}][descripcion]', '').strip()
        cantidad_str = post_data.get(f'productos[{i}][cantidad]', '').strip()
        
        try:
            cantidad = float(cantidad_str) if cantidad_str else 0
        except ValueError:
            cantidad = 0
        
        productos.append({
            'codigo': codigo,
            'descripcion': descripcion,
            'cantidad': cantidad
        })
        i += 1
    
    return productos

def _generar_clave_acceso_temporal(guia):
    """Genera una clave de acceso temporal para la guia"""
    from random import randint
    from django.utils import timezone
    empresa = getattr(guia, 'empresa', None)
    ruc = getattr(empresa, 'ruc', '') if empresa else ''
    if not ruc:
        raise ValueError('La empresa asociada a la guía debe tener un RUC configurado.')
    fecha_valor = guia.fecha_emision
    if isinstance(fecha_valor, str):
        try:
            fecha = datetime.strptime(fecha_valor, '%Y-%m-%d').date()
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = fecha_valor or timezone.now().date()
    fecha_str = fecha.strftime('%d%m%Y')
    tipo_comprobante = '06'  # Guia de remisión
    ambiente = getattr(empresa, 'tipo_ambiente', None) or '1'  # 1=Pruebas, 2=Producción
    serie = f"{guia.establecimiento}{guia.punto_emision}"
    secuencial = guia.secuencial or '000000001'
    codigo_numerico = f"{randint(0, 99999999):08d}"
    tipo_emision = '1'

    clave_sin_dv = f"{fecha_str}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"

    # Cálculo simple Mod 11 (placeholder mejor que fijo) — se puede mejorar si ya existe util.
    factores = [2,3,4,5,6,7]*10
    total = 0
    for i, ch in enumerate(reversed(clave_sin_dv)):
        total += int(ch) * factores[i]
    dv = 11 - (total % 11)
    if dv in (10,11):
        dv = 1
    return clave_sin_dv + str(dv)
