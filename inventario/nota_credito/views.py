"""
Vistas para Notas de Crédito
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import date
import json
import logging

from .models import NotaCredito, DetalleNotaCredito, TotalImpuestoNotaCredito
from inventario.models import (
    Factura,
    Empresa,
    Opciones,
    DetalleFactura,
    Cliente,
    Almacen,
    Secuencia,
    Facturador,
    Caja,
    FormaPago,
    Banco,
)
from inventario.views import complementarContexto
from inventario.forms import EmitirFacturaFormulario
from django.db.models import Max
from inventario.utils_planes import obtener_estado_plan_y_notificar, incrementar_contador_documentos

logger = logging.getLogger(__name__)

_nc_sri_envio_bg_jobs = {}
_nc_sri_envio_bg_lock = None


def _get_nc_sri_envio_bg_lock():
    global _nc_sri_envio_bg_lock
    if _nc_sri_envio_bg_lock is None:
        import threading
        _nc_sri_envio_bg_lock = threading.Lock()
    return _nc_sri_envio_bg_lock


def _normalizar_estado_nc_sri(valor):
    estado = str(valor or '').strip().upper().replace(' ', '_')
    mapa = {
        'NO_AUTORIZADO': 'RECHAZADO',
        'NO_AUTORIZADA': 'RECHAZADO',
        'RECIBIDO': 'RECIBIDA',
        'EN_PROCESAMIENTO': 'RECIBIDA',
        'PROCESANDO': 'RECIBIDA',
        'PROCESAMIENTO': 'RECIBIDA',
    }
    return mapa.get(estado, estado)


def _enviar_email_automatico_nc(nota_credito):
    if not nota_credito.numero_autorizacion or not nota_credito.fecha_autorizacion:
        return False

    if nota_credito.email_enviado:
        return False

    from inventario.documentos_email.services import DocumentEmailService

    servicio = DocumentEmailService(nota_credito.empresa)
    nota_credito.email_envio_intentos = (nota_credito.email_envio_intentos or 0) + 1
    try:
        resultado = servicio.send_nota_credito(nota_credito)
        if not resultado.success:
            nota_credito.email_ultimo_error = resultado.message
            nota_credito.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
            logger.warning('[NC EMAIL] No se envió NC %s: %s', nota_credito.id, resultado.message)
            return False

        nota_credito.email_enviado = True
        nota_credito.email_enviado_at = timezone.now()
        nota_credito.email_ultimo_error = None
        nota_credito.save(update_fields=['email_enviado', 'email_enviado_at', 'email_envio_intentos', 'email_ultimo_error'])
        logger.info('[NC EMAIL] Nota de crédito %s enviada a %s', nota_credito.id, ', '.join(resultado.recipients))
        return True
    except Exception as exc:
        nota_credito.email_ultimo_error = str(exc)
        nota_credito.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
        logger.exception('[NC EMAIL] Error enviando NC %s', nota_credito.id)
        return False


def _run_nc_sri_background(nota_credito_id, empresa_id, max_attempts=360, interval_seconds=10):
    import time
    from inventario.tenant.queryset import set_current_tenant
    from .integracion_sri_nc import IntegracionSRINotaCredito
    from inventario.sri.sri_client import SRIClient

    def _respuesta_sigue_pendiente_sin_autorizacion(respuesta):
        estado = _normalizar_estado_nc_sri((respuesta or {}).get('estado'))
        if estado in ('AUTORIZADO', 'AUTORIZADA', 'RECHAZADO'):
            return False

        autorizaciones = (respuesta or {}).get('autorizaciones') or []
        if autorizaciones:
            return False

        mensajes = (respuesta or {}).get('mensajes') or []
        texto = ' '.join(
            str(item.get('mensaje') if isinstance(item, dict) else item or '') + ' ' +
            str(item.get('informacionAdicional') if isinstance(item, dict) else '')
            for item in mensajes
        ).upper()
        return 'NO HA SIDO AUTORIZADO AÚN' in texto or 'NO HA SIDO AUTORIZADO AUN' in texto or 'NO EXISTE' in texto or estado in ('PENDIENTE', 'RECIBIDA')

    key = f'{empresa_id}:{nota_credito_id}'
    logger.info('[NC SRI BG] Inicio envío en background para NC %s (empresa %s)', nota_credito_id, empresa_id)
    try:
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if empresa is None:
            logger.warning('[NC SRI BG] Empresa %s no existe', empresa_id)
            return

        ya_contabilizada = False

        for _ in range(max_attempts):
            try:
                try:
                    set_current_tenant(empresa)
                except Exception:
                    logger.warning('[NC SRI BG] No se pudo establecer tenant para empresa %s', empresa_id)
                nota_credito = NotaCredito.objects.get(id=nota_credito_id, empresa_id=empresa_id)
            except NotaCredito.DoesNotExist:
                logger.warning('[NC SRI BG] NC %s no existe en empresa %s', nota_credito_id, empresa_id)
                break

            try:
                if nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion:
                    if not ya_contabilizada:
                        try:
                            incrementar_contador_documentos(empresa)
                        except Exception as exc:
                            logger.warning('[NC SRI BG] No se pudo incrementar contador para NC %s: %s', nota_credito_id, exc)
                        ya_contabilizada = True
                    _enviar_email_automatico_nc(nota_credito)
                    break

                integracion = IntegracionSRINotaCredito(nota_credito)
                estado_actual = _normalizar_estado_nc_sri(nota_credito.estado_sri)

                if estado_actual in ('AUTORIZADO', 'AUTORIZADA', 'RECHAZADO'):
                    logger.info('[NC SRI BG] NC %s ya en estado final %s', nota_credito_id, estado_actual)
                    break

                if estado_actual in ('RECIBIDA', 'PENDIENTE') and nota_credito.clave_acceso:
                    opciones = Opciones.objects.for_tenant(empresa).first()
                    if not opciones:
                        logger.warning('[NC SRI BG] No se encontró Opciones para empresa %s', empresa_id)
                        break

                    ambiente = 'pruebas' if str(getattr(opciones, 'tipo_ambiente', '1')) == '1' else 'produccion'
                    cliente = SRIClient(ambiente=ambiente)
                    respuesta = cliente.consultar_autorizacion(nota_credito.clave_acceso)
                    estado = _normalizar_estado_nc_sri(integracion.procesar_respuesta(respuesta))
                    logger.info('[NC SRI BG] NC %s consulta autorización, estado=%s', nota_credito_id, estado or 'SIN_ESTADO')

                    if _respuesta_sigue_pendiente_sin_autorizacion(respuesta):
                        logger.info('[NC SRI BG] NC %s sigue sin autorización final; se realiza reenvío automático completo', nota_credito_id)
                        resultado = integracion.procesar_completo()
                        estado = _normalizar_estado_nc_sri(resultado.get('estado'))
                        logger.info('[NC SRI BG] NC %s reenvío automático, estado=%s success=%s', nota_credito_id, estado or 'SIN_ESTADO', resultado.get('success'))
                else:
                    resultado = integracion.procesar_completo()
                    estado = _normalizar_estado_nc_sri(resultado.get('estado'))
                    logger.info('[NC SRI BG] NC %s intento envío, estado=%s success=%s', nota_credito_id, estado or 'SIN_ESTADO', resultado.get('success'))

                try:
                    nota_credito.refresh_from_db(fields=['estado_sri', 'numero_autorizacion', 'fecha_autorizacion'])
                except Exception:
                    pass

                if nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion:
                    if not ya_contabilizada:
                        try:
                            incrementar_contador_documentos(empresa)
                        except Exception as exc:
                            logger.warning('[NC SRI BG] No se pudo incrementar contador para NC %s: %s', nota_credito_id, exc)
                        ya_contabilizada = True
                    _enviar_email_automatico_nc(nota_credito)
                    break

                if estado in ('AUTORIZADO', 'AUTORIZADA', 'RECHAZADO'):
                    break

            except Exception as exc:
                logger.exception('[NC SRI BG] Error procesando NC %s en background: %s', nota_credito_id, exc)

            time.sleep(interval_seconds)
    finally:
        logger.info('[NC SRI BG] Fin envío en background para NC %s', nota_credito_id)
        lock = _get_nc_sri_envio_bg_lock()
        with lock:
            _nc_sri_envio_bg_jobs.pop(key, None)


def _start_nc_sri_background(nota_credito_id, empresa_id):
    key = f'{empresa_id}:{nota_credito_id}'
    lock = _get_nc_sri_envio_bg_lock()
    with lock:
        job = _nc_sri_envio_bg_jobs.get(key)
        if job and job.is_alive():
            logger.info('[NC SRI BG] Job ya en ejecución para %s', key)
            return False

        import threading
        job = threading.Thread(
            target=_run_nc_sri_background,
            args=(nota_credito_id, empresa_id),
            daemon=True,
        )
        _nc_sri_envio_bg_jobs[key] = job
        job.start()
        logger.info('[NC SRI BG] Job iniciado para %s', key)
        return True


class ListarNotasCredito(LoginRequiredMixin, View):
    """Vista para listar todas las notas de crédito"""
    login_url = '/inventario/login'
    
    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')
        
        # Filtros
        q = request.GET.get('q', '')
        estado = request.GET.get('estado', '')
        
        notas_credito = NotaCredito.objects.filter(
            empresa_id=empresa_id
        ).select_related('factura_modificada', 'factura_modificada__cliente').order_by('-fecha_emision', '-secuencial')
        
        if q:
            notas_credito = notas_credito.filter(
                factura_modificada__cliente__razon_social__icontains=q
            ) | notas_credito.filter(secuencial__icontains=q)
        
        if estado:
            notas_credito = notas_credito.filter(estado_sri=estado)
        
        contexto = {
            'notas_credito': notas_credito,
            'titulo': 'Notas de Crédito'
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/nota_credito/listar.html', contexto)


class CrearNotaCredito(LoginRequiredMixin, View):
    """Vista para crear una nueva nota de crédito desde una factura"""
    login_url = '/inventario/login'
    SECUENCIA_TIPO_DOCUMENTO = "04"  # Nota de Crédito
    
    def _calcular_datos_secuencia(self, empresa, secuencia):
        """Calcula el siguiente secuencial disponible - IGUAL QUE LIQUIDACIÓN"""
        if not empresa or not secuencia:
            return None

        max_existente = NotaCredito.objects.filter(
            empresa=empresa,
            establecimiento=secuencia.establecimiento,
            punto_emision=secuencia.punto_emision,
        ).aggregate(m=Max("secuencial"))["m"] or 0

        base = secuencia.secuencial or 0
        if max_existente > 0:
            siguiente = max_existente + 1
        else:
            siguiente = max(base, 1)
        if siguiente > 999_999_999:
            raise ValueError("El secuencial ha alcanzado el valor máximo permitido (999999999).")

        return {
            "secuencia": secuencia,
            "establecimiento": secuencia.establecimiento,
            "punto_emision": secuencia.punto_emision,
            "valor": siguiente,
            "establecimiento_str": f"{secuencia.establecimiento:03d}",
            "punto_emision_str": f"{secuencia.punto_emision:03d}",
            "valor_str": f"{siguiente:09d}",
        }

    def _obtener_siguiente_secuencia(self, empresa, secuencia_id=None):
        """Obtiene la siguiente secuencia disponible - IGUAL QUE LIQUIDACIÓN"""
        if not empresa:
            return None

        qs = Secuencia.objects.filter(
            empresa=empresa,
            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
            activo=True,
        )
        if secuencia_id:
            qs = qs.filter(id=secuencia_id)

        secuencia = qs.order_by("establecimiento", "punto_emision").first()
        if not secuencia:
            return None

        return self._calcular_datos_secuencia(empresa, secuencia)
    
    def get(self, request, factura_id=None):
        # Aceptar factura_id desde URL o query string
        if factura_id is None:
            factura_id = request.GET.get('factura_id')
        
        if not factura_id:
            messages.error(request, 'Debe especificar una factura.')
            return redirect('inventario:listarFacturas')
        
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')
        
        # ✅ VALIDAR AUTENTICACIÓN DE FACTURADOR
        facturador_id = request.session.get('facturador_id')
        if not facturador_id:
            # Si no hay facturador logueado, redirigir al login con next
            next_url = f'/inventario/notas-credito/crear/{factura_id}/' if factura_id else '/inventario/notas-credito/crear/'
            return redirect(f'/inventario/login_facturador/?next={next_url}')
        
        empresa = get_object_or_404(Empresa, id=empresa_id)

        # ✅ Cajas + formas de pago SRI + bancos (igual que EmitirFactura)
        cajas_activas = Caja.objects.filter(activo=True, empresa_id=empresa_id).order_by('descripcion')
        formas_pago_sri = getattr(FormaPago, 'FORMAS_PAGO_CHOICES', [])

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
        
        # Obtener la factura - Solo facturas autorizadas pueden tener NC
        factura = get_object_or_404(
            Factura, 
            id=factura_id, 
            empresa=empresa
        )
        
        # Validar estado autorizado (puede ser AUTORIZADO o AUTORIZADA)
        if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
            messages.error(request, 'Solo se pueden crear Notas de Crédito para facturas AUTORIZADAS por el SRI.')
            return redirect('inventario:verFactura', p=factura_id)
        
        # Verificar que hay saldo disponible
        if factura.saldo_nota_credito <= 0:
            messages.error(request, 'Esta factura no tiene saldo disponible para notas de crédito.')
            return redirect('inventario:verFactura', p=factura_id)
        
        # ✅ CALCULAR SECUENCIA EN EL SERVIDOR (como liquidación)
        secuencia_info = self._obtener_siguiente_secuencia(empresa)
        
        # Obtener clientes y almacenes de la empresa
        cedulas = Cliente.objects.filter(empresa=empresa).values_list('id', 'identificacion')
        almacenes = Almacen.objects.filter(activo=True, empresa=empresa)
        
        # ✅ Obtener secuencias para el select
        secuencias = Secuencia.objects.filter(
            empresa=empresa, 
            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
            activo=True
        ).order_by('establecimiento', 'punto_emision')
        
        # ✅ Preparar initial data con los valores calculados
        from datetime import date
        initial = {
            'fecha_emision': date.today(),
            'fecha_vencimiento': date.today(),
            # Pre-cargar datos del cliente de la factura
            'identificacion_cliente': factura.identificacion_cliente or '',
            'nombre_cliente': factura.nombre_cliente or '',
        }

        # Pre-cargar almacén desde la factura (mismo patrón que EditarFactura)
        if getattr(factura, 'almacen_id', None):
            initial['almacen'] = str(factura.almacen_id)
        
        # Obtener correo del cliente si existe
        if factura.cliente:
            initial['correo_cliente'] = (
                getattr(factura.cliente, 'correo', '')
                or getattr(factura.cliente, 'email', '')
                or ''
            )
        
        if secuencia_info:
            initial.update({
                "establecimiento": secuencia_info["establecimiento_str"],
                "punto_emision": secuencia_info["punto_emision_str"],
                "secuencia_valor": secuencia_info["valor_str"],
                "secuencia": secuencia_info["secuencia"].id,  # ID de la secuencia seleccionada
            })
        
        # Crear formulario con initial data
        form = EmitirFacturaFormulario(cedulas=cedulas, secuencias=secuencias, initial=initial)
        
        # ✅ Hacer campos de secuencia READONLY (como liquidación)
        for campo in ("establecimiento", "punto_emision", "secuencia_valor"):
            if campo in form.fields:
                widget = form.fields[campo].widget
                clases_actuales = widget.attrs.get("class", "").strip()
                widget.attrs["class"] = f"{clases_actuales} bg-gray-100".strip()
                widget.attrs["readonly"] = "readonly"
                widget.attrs["tabindex"] = "-1"
        
        # Actualizar el campo de almacenes dinámicamente
        # Importante: usar IDs como string para que el "initial" haga match en el HTML.
        if 'almacen' in form.fields:
            form.fields['almacen'].choices = [('', '...')] + [
                (str(a.id), a.descripcion) for a in almacenes
            ]
            if getattr(factura, 'almacen_id', None):
                form.fields['almacen'].initial = str(factura.almacen_id)
        
        # ✅ Pre-cargar productos de la factura como JSON
        productos_factura = []
        print(f"🔍 DEBUG: Factura ID: {factura.id}, Detalles: {factura.detallefactura_set.count()}")
        
        for detalle in factura.detallefactura_set.all():
            # Mapeo de códigos IVA a tarifas
            tarifas_iva = {
                '0': 0, '2': 15, '3': 14, '4': 15, '5': 5,
                '6': 0, '7': 0, '8': 0, '10': 13,
            }
            
            if detalle.producto:
                codigo = detalle.producto.codigo
                descripcion = detalle.producto.descripcion
                precio = float(detalle.precio_unitario or detalle.producto.precio or 0)
                codigo_iva = detalle.iva_codigo or detalle.producto.iva or '4'
                producto_id = detalle.producto_id
                servicio_id = None
            elif detalle.servicio:
                codigo = detalle.servicio.codigo
                descripcion = detalle.servicio.descripcion
                precio = float(detalle.precio_unitario or detalle.servicio.precio1 or 0)
                codigo_iva = detalle.iva_codigo or detalle.servicio.iva or '4'
                producto_id = None
                servicio_id = detalle.servicio_id
            else:
                codigo = 'SIN_CODIGO'
                descripcion = 'Sin descripción'
                precio = float(detalle.precio_unitario or 0)
                codigo_iva = '4'
                producto_id = None
                servicio_id = None

            # ✅ IVA vigente: si viene '2' (12%) convertir a '4' (15%) para emisiones actuales
            if str(codigo_iva) == '2':
                codigo_iva = '4'
            
            productos_factura.append({
                'producto_id': producto_id,
                'servicio_id': servicio_id,
                'codigo': codigo,
                'descripcion': descripcion,
                'cantidad': float(detalle.cantidad),
                'precio_unitario': precio,
                'descuento': float(detalle.descuento or 0),
                'subtotal': float(detalle.sub_total or 0),
                'codigo_iva': codigo_iva,
                'tarifa_iva': tarifas_iva.get(str(codigo_iva), 15),
            })
        
        print(f"✅ DEBUG: Productos cargados: {len(productos_factura)}")
        print(f"📦 DEBUG: Productos JSON: {json.dumps(productos_factura)[:200]}...")  # Primeros 200 caracteres

        # Totales para render server-side (fallback si el JS no corre)
        from decimal import Decimal
        subtotal_sum = Decimal('0.00')
        iva_sum = Decimal('0.00')
        for p in productos_factura:
            sub = Decimal(str(p.get('subtotal', 0) or 0))
            tarifa = Decimal(str(p.get('tarifa_iva', 0) or 0))
            subtotal_sum += sub
            if tarifa > 0:
                iva_sum += sub * (tarifa / Decimal('100'))
        total_general = subtotal_sum + iva_sum
        
        contexto = {
            'factura': factura,
            'opciones': Opciones.objects.for_tenant(empresa).first(),
            'form': form,
            'secuencias': secuencias,
            'secuencia_info': secuencia_info,  # ✅ Info de la secuencia calculada
            'productos_factura': productos_factura,  # ✅ Lista para render server-side
            'productos_factura_json': json.dumps(productos_factura),  # ✅ Productos como JSON
            'total_general': float(total_general),
            'today': date.today(),
            'titulo': f'Nueva Nota de Crédito - Factura {factura.numero_completo}',
            'cajas': cajas_activas,
            'formas_pago_sri': formas_pago_sri,
            'bancos_lista_nombres': lista_bancos,
            'bancos_db': Banco.objects.filter(activo=True, empresa_id=empresa_id).order_by('banco'),
            'now': timezone.now(),
            'motivo_choices': getattr(NotaCredito, 'MOTIVO_CHOICES', []),
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/nota_credito/crear.html', contexto)
    
    def post(self, request, factura_id=None):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return JsonResponse({'success': False, 'message': 'Empresa no válida'})
        
        empresa = get_object_or_404(Empresa, id=empresa_id)
        
        try:
            nota_credito_id = None
            nota_credito_numero = None
            with transaction.atomic():
                # Obtener datos del formulario
                factura_id = factura_id or request.POST.get('factura_modificada') or request.POST.get('factura_id')
                if not factura_id:
                    messages.error(request, 'Debe especificar la factura a la que aplica la Nota de Crédito.')
                    return redirect('inventario:listarFacturas')
                factura = get_object_or_404(Factura, id=factura_id, empresa=empresa)
                
                # ========== VALIDACIONES CRÍTICAS (Error 68 SRI) ==========
                # 1. Validar que la factura esté AUTORIZADA
                if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
                    messages.error(request, 'ERROR: La factura no está autorizada por el SRI. No se puede crear NC.')
                    return redirect('inventario:verFactura', p=factura_id)
                
                # 2. Validar que la factura tenga clave de acceso (existe en SRI)
                if not factura.clave_acceso:
                    messages.error(request, 'ERROR: La factura no tiene clave de acceso del SRI.')
                    return redirect('inventario:verFactura', p=factura_id)
                
                # Por ahora no pedimos "tipo de motivo" en UI.
                # Guardamos un valor fijo para mantener consistencia y evitar que el tipo controle comportamiento.
                tipo_motivo = 'CORRECCION'
                motivo = (request.POST.get('motivo') or '').strip()
                fecha_emision = request.POST.get('fecha_emision')

                # Fecha efectiva IVA 15% (SRI): desde 2024-04-01
                try:
                    fecha_emision_dt = date.fromisoformat(str(fecha_emision))
                except Exception:
                    fecha_emision_dt = date.today()

                # Validar motivo (requerido por el modelo)
                if not motivo:
                    messages.error(request, 'Debe ingresar el motivo de la Nota de Crédito.')
                    return redirect('inventario:notas_credito_crear_factura', factura_id=factura_id)

                # Validación defensiva (por si cambian choices en el futuro)
                try:
                    valid_motivos = {c for c, _ in NotaCredito.MOTIVO_CHOICES}
                    if tipo_motivo not in valid_motivos:
                        tipo_motivo = 'CORRECCION'
                except Exception:
                    pass
                
                # Obtener productos seleccionados
                productos_json = request.POST.get('productos', '[]')
                productos = json.loads(productos_json)
                
                if not productos:
                    messages.error(request, 'Debe seleccionar al menos un producto.')
                    return redirect('inventario:notas_credito_crear_factura', factura_id=factura_id)
                
                # Calcular totales
                from decimal import ROUND_HALF_UP
                dos_decimales = Decimal('0.01')

                subtotal = Decimal('0.00')
                total_iva = Decimal('0.00')
                subtotales_iva = {}
                
                for prod in productos:
                    cantidad = Decimal(str(prod['cantidad']))
                    precio = Decimal(str(prod['precio_unitario']))
                    descuento = Decimal(str(prod.get('descuento', 0)))
                    tarifa = Decimal(str(prod.get('tarifa_iva', 15)))

                    # ✅ Normalizar IVA vigente: si llega 12%/código '2' en fechas no vigentes, convertir a 15% ('4')
                    codigo_iva_in = str(prod.get('codigo_iva', '4') or '4').strip()
                    if fecha_emision_dt >= date(2024, 4, 1) and (codigo_iva_in == '2' or tarifa == Decimal('12')):
                        codigo_iva_in = '4'
                        tarifa = Decimal('15')
                        prod['codigo_iva'] = '4'
                        prod['tarifa_iva'] = '15'
                    
                    subtotal_item = (cantidad * precio) - descuento
                    subtotal_item = subtotal_item.quantize(dos_decimales, rounding=ROUND_HALF_UP)
                    iva_item = (subtotal_item * (tarifa / Decimal('100'))).quantize(dos_decimales, rounding=ROUND_HALF_UP)
                    
                    subtotal += subtotal_item
                    total_iva += iva_item
                    
                    # Agrupar por tarifa
                    tarifa_key = str(tarifa)
                    if tarifa_key not in subtotales_iva:
                        subtotales_iva[tarifa_key] = Decimal('0.00')
                    subtotales_iva[tarifa_key] += subtotal_item
                
                subtotal = subtotal.quantize(dos_decimales, rounding=ROUND_HALF_UP)
                total_iva = total_iva.quantize(dos_decimales, rounding=ROUND_HALF_UP)
                valor_total = (subtotal + total_iva).quantize(dos_decimales, rounding=ROUND_HALF_UP)
                
                # 3. Validar que no exceda el saldo disponible
                saldo_disponible = factura.saldo_nota_credito
                if valor_total > saldo_disponible:
                    messages.error(
                        request, 
                        f'El valor de la NC (${valor_total}) excede el saldo disponible (${saldo_disponible}).'
                    )
                    return redirect('inventario:verFactura', p=factura_id)
                
                # Obtener establecimiento y punto de emisión desde la factura original
                establecimiento = factura.establecimiento  # Usar mismo de la factura
                punto_emision = factura.punto_emision      # Usar mismo de la factura
                
                ultimo_secuencial = NotaCredito.objects.filter(
                    empresa=empresa,
                    establecimiento=establecimiento,
                    punto_emision=punto_emision
                ).order_by('-secuencial').first()
                
                if ultimo_secuencial:
                    nuevo_secuencial = str(int(ultimo_secuencial.secuencial) + 1).zfill(9)
                else:
                    nuevo_secuencial = '000000001'
                
                # Crear la Nota de Crédito
                nota_credito = NotaCredito.objects.create(
                    empresa=empresa,
                    factura_modificada=factura,
                    establecimiento=establecimiento,
                    punto_emision=punto_emision,
                    secuencial=nuevo_secuencial,
                    fecha_emision=fecha_emision,
                    cod_doc_modificado='01',
                    num_doc_modificado=factura.numero_completo,
                    fecha_emision_doc_sustento=factura.fecha_emision,
                    tipo_motivo=tipo_motivo,
                    motivo=motivo,
                    subtotal_sin_impuestos=subtotal,
                    total_iva=total_iva,
                    valor_modificacion=valor_total,
                    estado_sri='PENDIENTE',
                    creado_por=request.user
                )
                
                # Crear detalles
                for prod in productos:
                    codigo_iva = str(prod.get('codigo_iva', '4') or '4').strip()
                    tarifa = Decimal(str(prod.get('tarifa_iva', 15)))
                    if fecha_emision_dt >= date(2024, 4, 1) and (codigo_iva == '2' or tarifa == Decimal('12')):
                        codigo_iva = '4'
                        tarifa = Decimal('15')
                    DetalleNotaCredito.objects.create(
                        nota_credito=nota_credito,
                        empresa=empresa,
                        producto_id=prod.get('producto_id'),
                        servicio_id=prod.get('servicio_id'),
                        codigo_principal=prod['codigo'],
                        descripcion=prod['descripcion'],
                        cantidad=Decimal(str(prod['cantidad'])),
                        precio_unitario=Decimal(str(prod['precio_unitario'])),
                        descuento=Decimal(str(prod.get('descuento', 0))),
                        codigo_iva=codigo_iva,
                        tarifa_iva=tarifa
                    )
                
                # Crear totales de impuestos
                for tarifa, base in subtotales_iva.items():
                    tarifa_dec = Decimal(tarifa)
                    if fecha_emision_dt >= date(2024, 4, 1) and tarifa_dec == Decimal('12'):
                        tarifa_dec = Decimal('15')
                    valor_imp = (base * (tarifa_dec / Decimal('100'))).quantize(dos_decimales, rounding=ROUND_HALF_UP)
                    TotalImpuestoNotaCredito.objects.create(
                        nota_credito=nota_credito,
                        empresa=empresa,
                        codigo='2',  # IVA
                        codigo_porcentaje=self._get_codigo_porcentaje(tarifa_dec),
                        tarifa=tarifa_dec,
                        base_imponible=base,
                        valor=valor_imp
                    )
                
                nota_credito_id = nota_credito.id
                nota_credito_numero = nota_credito.numero_completo

            nota_credito = NotaCredito.objects.get(id=nota_credito_id, empresa_id=empresa.id)
            ya_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)

            try:
                from .integracion_sri_nc import IntegracionSRINotaCredito

                integracion = IntegracionSRINotaCredito(nota_credito)
                resultado = integracion.procesar_completo()
                nota_credito.refresh_from_db(fields=['estado_sri', 'numero_autorizacion', 'fecha_autorizacion', 'mensaje_sri'])
                ahora_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)
                estado_actual = _normalizar_estado_nc_sri(nota_credito.estado_sri)

                if (not ya_autorizada) and ahora_autorizada:
                    incrementar_contador_documentos(empresa)

                if ahora_autorizada:
                    _enviar_email_automatico_nc(nota_credito)
                    messages.success(
                        request,
                        f'Nota de Crédito {nota_credito_numero} creada y autorizada automáticamente. Autorización: {nota_credito.numero_autorizacion or ""}'
                    )
                elif estado_actual == 'RECHAZADO':
                    messages.error(
                        request,
                        f'Nota de Crédito {nota_credito_numero} no autorizada por el SRI. {nota_credito.mensaje_sri or ""}'
                    )
                else:
                    started = _start_nc_sri_background(nota_credito_id, empresa.id)
                    if started:
                        messages.info(
                            request,
                            f'Nota de Crédito {nota_credito_numero} creada y enviada automáticamente al SRI. El sistema seguirá reintentando hasta que quede AUTORIZADA o NO AUTORIZADA.'
                        )
                    else:
                        messages.info(
                            request,
                            f'Nota de Crédito {nota_credito_numero} creada correctamente. El proceso automático ya está en marcha hasta obtener respuesta final del SRI.'
                        )
            except Exception:
                logger.exception('Error procesando automáticamente la NC %s tras su creación', nota_credito_id)
                started = _start_nc_sri_background(nota_credito_id, empresa.id)
                if started:
                    messages.warning(
                        request,
                        f'Nota de Crédito {nota_credito_numero} creada. La autorización automática continuará en segundo plano hasta que el SRI responda.'
                    )
                else:
                    messages.success(request, f'Nota de Crédito {nota_credito_numero} creada correctamente.')

            return redirect('inventario:notas_credito_ver', pk=nota_credito_id)
        
        except Exception as e:
            logger.exception("Error creando nota de crédito")
            messages.error(request, f'Error al crear la nota de crédito: {str(e)}')
            return redirect('inventario:listarFacturas')
    
    def _get_codigo_porcentaje(self, tarifa):
        """Obtiene el código de porcentaje según la tarifa"""
        mapeo = {
            Decimal('0'): '0',
            Decimal('5'): '5',
            Decimal('13'): '10',
            Decimal('14'): '3',
            Decimal('15'): '4',
        }
        # Desde 2024, 12% (código '2') no está vigente para emisiones actuales.
        if tarifa == Decimal('12'):
            return '4'
        return mapeo.get(tarifa, '4')


class VerNotaCredito(LoginRequiredMixin, View):
    """Vista para ver detalle de una nota de crédito"""
    login_url = '/inventario/login'
    
    def get(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')
        
        nota_credito = get_object_or_404(
            NotaCredito.objects.select_related('factura_modificada', 'factura_modificada__cliente'),
            id=pk,
            empresa_id=empresa_id
        )
        
        contexto = {
            'nota_credito': nota_credito,
            'titulo': f'Nota de Crédito {nota_credito.numero_completo}'
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/nota_credito/ver.html', contexto)


class ObtenerDetallesFacturaView(LoginRequiredMixin, View):
    """API para obtener los detalles de una factura (AJAX)"""
    login_url = '/inventario/login'
    
    def get(self, request, factura_id):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return JsonResponse({'success': False, 'message': 'Empresa no válida'})
        
        try:
            factura = get_object_or_404(
                Factura,
                id=factura_id,
                empresa_id=empresa_id,
                estado_sri='AUTORIZADO'
            )
            
            detalles = []
            for d in factura.detallefactura_set.all():
                codigo_iva = d.iva_codigo or (d.producto.iva if d.producto else d.servicio.iva if d.servicio else '4')
                if str(codigo_iva) == '2':
                    codigo_iva = '4'
                detalles.append({
                    'id': d.id,
                    'producto_id': d.producto_id,
                    'servicio_id': d.servicio_id,
                    'codigo': d.producto.codigo if d.producto else d.servicio.codigo if d.servicio else '',
                    'descripcion': d.producto.descripcion if d.producto else d.servicio.descripcion if d.servicio else '',
                    'cantidad': float(d.cantidad),
                    'cantidad_disponible': float(d.cantidad),  # TODO: Restar NCs anteriores
                    'precio_unitario': float(d.precio_unitario or (d.producto.precio if d.producto else d.servicio.precio1 if d.servicio else 0)),
                    'descuento': float(d.descuento or 0),
                    'subtotal': float(d.sub_total or 0),
                    'codigo_iva': codigo_iva,
                    'tarifa_iva': self._get_tarifa_from_codigo(codigo_iva),
                })
            
            return JsonResponse({
                'success': True,
                'factura': {
                    'id': factura.id,
                    'numero': factura.numero_completo,
                    'fecha': factura.fecha_emision.strftime('%d/%m/%Y'),
                    'cliente': factura.nombre_cliente,
                    'identificacion': factura.identificacion,
                    'total': float(factura.total),
                    'saldo_disponible': float(factura.saldo_para_nc),
                },
                'detalles': detalles
            })
        
        except Exception as e:
            logger.exception("Error obteniendo detalles de factura")
            return JsonResponse({'success': False, 'message': str(e)})
    
    def _get_tarifa_from_codigo(self, codigo):
        """Obtiene la tarifa según el código de IVA"""
        mapeo = {
            '0': 0,
            '5': 5,
            '2': 15,
            '10': 13,
            '3': 14,
            '4': 15,
            '6': 0,  # No objeto
            '7': 0,  # Exento
        }
        return mapeo.get(str(codigo), 15)


class AutorizarNotaCredito(LoginRequiredMixin, View):
    """Vista para autorizar NC en el SRI"""
    login_url = '/inventario/login'
    
    def get(self, request, pk):
        """Redirige al POST"""
        return self.post(request, pk)
    
    def post(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:panel')
        
        nota_credito = get_object_or_404(
            NotaCredito,
            id=pk,
            empresa_id=empresa_id
        )
        
        if nota_credito.estado_sri == 'AUTORIZADO':
            messages.info(request, 'Esta nota de crédito ya está autorizada.')
            return redirect('inventario:notas_credito_ver', pk=pk)

        # Control de plan: bloquear autorización si se alcanzó límite
        empresa = nota_credito.empresa
        estado_plan = obtener_estado_plan_y_notificar(empresa)
        if estado_plan.get('tiene_plan') and not estado_plan.get('puede_autorizar', True):
            messages.error(
                request,
                f"🚫 Ha alcanzado el límite de {estado_plan.get('limite_documentos')} documentos de su plan. "
                "No se puede autorizar una nueva Nota de Crédito."
            )
            return redirect('inventario:notas_credito_ver', pk=pk)

        ya_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)
        
        try:
            from .integracion_sri_nc import IntegracionSRINotaCredito
            
            integracion = IntegracionSRINotaCredito(nota_credito)
            resultado = integracion.procesar_completo()
            
            if resultado['success']:
                nota_credito.refresh_from_db(fields=['numero_autorizacion', 'fecha_autorizacion', 'estado_sri'])
                ahora_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)
                estado_actual = _normalizar_estado_nc_sri(nota_credito.estado_sri)
                if (not ya_autorizada) and ahora_autorizada:
                    incrementar_contador_documentos(empresa)
                if ahora_autorizada:
                    _enviar_email_automatico_nc(nota_credito)
                    messages.success(request, f'Nota de Crédito autorizada correctamente. Autorización: {resultado.get("numero_autorizacion", "")}')
                elif estado_actual == 'RECHAZADO':
                    messages.error(request, f'Nota de Crédito no autorizada por el SRI. {nota_credito.mensaje_sri or ""}')
                else:
                    started = _start_nc_sri_background(nota_credito.id, empresa.id)
                    if started:
                        messages.info(request, 'La Nota de Crédito fue enviada al SRI. El sistema seguirá reintentando automáticamente hasta que quede AUTORIZADA o NO AUTORIZADA.')
                    else:
                        messages.info(request, 'La Nota de Crédito ya tiene un proceso automático en marcha hasta que el SRI responda AUTORIZADA o NO AUTORIZADA.')
            else:
                messages.error(request, f'Error al autorizar: {resultado.get("mensaje", "Error desconocido")}')
        
        except Exception as e:
            logger.exception("Error autorizando NC")
            messages.error(request, f'Error al autorizar: {str(e)}')
        
        return redirect('inventario:notas_credito_ver', pk=pk)


class ConsultarEstadoNotaCredito(LoginRequiredMixin, View):
    """Consulta el estado actual de la Nota de Crédito en el SRI (sin reenviar)."""
    login_url = '/inventario/login'

    def get(self, request, pk):
        return self.post(request, pk)

    def post(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:panel')

        nota_credito = get_object_or_404(
            NotaCredito,
            id=pk,
            empresa_id=empresa_id
        )

        ya_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)

        if not nota_credito.clave_acceso:
            messages.error(request, 'Esta nota de crédito no tiene clave de acceso. No se puede consultar el estado en el SRI.')
            return redirect('inventario:notas_credito_ver', pk=pk)

        try:
            opciones = Opciones.objects.for_tenant(nota_credito.empresa).first()
            if not opciones:
                messages.error(request, 'No se encontró configuración de opciones para la empresa.')
                return redirect('inventario:notas_credito_ver', pk=pk)

            ambiente = 'pruebas' if str(getattr(opciones, 'tipo_ambiente', '1')) == '1' else 'produccion'

            from inventario.sri.sri_client import SRIClient
            from .integracion_sri_nc import IntegracionSRINotaCredito

            cliente = SRIClient(ambiente=ambiente)
            respuesta = cliente.consultar_autorizacion(nota_credito.clave_acceso)

            integracion = IntegracionSRINotaCredito(nota_credito)
            estado = _normalizar_estado_nc_sri(integracion.procesar_respuesta(respuesta))

            # Contar solo una vez cuando pasa a AUTORIZADO
            try:
                nota_credito.refresh_from_db(fields=['numero_autorizacion', 'fecha_autorizacion', 'estado_sri'])
            except Exception:
                pass
            ahora_autorizada = bool(nota_credito.numero_autorizacion and nota_credito.fecha_autorizacion)
            if (not ya_autorizada) and ahora_autorizada:
                incrementar_contador_documentos(nota_credito.empresa)
            if ahora_autorizada:
                _enviar_email_automatico_nc(nota_credito)

            if estado == 'AUTORIZADO':
                messages.success(request, f'✅ Estado SRI: AUTORIZADO. Autorización: {nota_credito.numero_autorizacion or ""}')
            elif estado in ('RECHAZADO', 'NO AUTORIZADO', 'NO_AUTORIZADO'):
                messages.error(request, f'❌ Estado SRI: NO AUTORIZADO. {nota_credito.mensaje_sri or ""}')
            else:
                started = _start_nc_sri_background(nota_credito.id, nota_credito.empresa_id)
                if started:
                    messages.info(request, 'La Nota de Crédito sigue en proceso. El sistema continuará automáticamente hasta obtener AUTORIZADO o NO AUTORIZADO.')
                else:
                    messages.info(request, 'La Nota de Crédito sigue en proceso automático hasta obtener AUTORIZADO o NO AUTORIZADO.')

        except Exception as e:
            logger.exception('Error consultando estado SRI de NC')
            messages.error(request, f'Error al consultar estado SRI: {str(e)}')

        return redirect('inventario:notas_credito_ver', pk=pk)


class DescargarPDF(LoginRequiredMixin, View):
    """Vista para descargar el RIDE de la NC"""
    login_url = '/inventario/login'
    
    def get(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:notas_credito_listar')
        
        nota_credito = get_object_or_404(
            NotaCredito,
            id=pk,
            empresa_id=empresa_id
        )
        
        try:
            from .ride_generator_nc import RIDEGeneratorNotaCredito
            
            opciones = Opciones.objects.for_tenant(nota_credito.empresa).first()
            generator = RIDEGeneratorNotaCredito(nota_credito, opciones)
            pdf_buffer = generator.generar_pdf()
            
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f'NC_{nota_credito.numero_completo.replace("-", "_")}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
        
        except Exception as e:
            logger.exception("Error generando PDF de NC")
            messages.error(request, f'Error al generar PDF: {str(e)}')
            return redirect('inventario:notas_credito_ver', pk=pk)
