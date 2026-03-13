"""Vistas para Notas de Débito (SRI codDoc 05).

Se implementa siguiendo el patrón de Nota de Crédito para que las plantillas
`inventario/nota_debito/*.html` funcionen (listar/crear/ver) y los botones
secundarios (autorizar/consultar/pdf) no rompan el flujo.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from inventario.forms import EmitirFacturaFormulario
from inventario.models import Almacen, Banco, Caja, Cliente, Empresa, Factura, FormaPago, Opciones, Secuencia
from inventario.utils_planes import obtener_estado_plan_y_notificar, incrementar_contador_documentos
from inventario.views import complementarContexto

from .models import DetalleNotaDebito, NotaDebito, TotalImpuestoNotaDebito

logger = logging.getLogger(__name__)

_nd_sri_envio_bg_jobs = {}
_nd_sri_envio_bg_lock = None


def _get_nd_sri_envio_bg_lock():
    global _nd_sri_envio_bg_lock
    if _nd_sri_envio_bg_lock is None:
        import threading
        _nd_sri_envio_bg_lock = threading.Lock()
    return _nd_sri_envio_bg_lock


def _normalizar_estado_nd_sri(valor):
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


def _enviar_email_automatico_nd(nota_debito):
    if not nota_debito.numero_autorizacion or not nota_debito.fecha_autorizacion:
        return False
    if nota_debito.email_enviado:
        return False

    from inventario.documentos_email.services import DocumentEmailService

    servicio = DocumentEmailService(nota_debito.empresa)
    nota_debito.email_envio_intentos = (nota_debito.email_envio_intentos or 0) + 1
    try:
        resultado = servicio.send_nota_debito(nota_debito)
        if not resultado.success:
            nota_debito.email_ultimo_error = resultado.message
            nota_debito.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
            logger.warning('[ND EMAIL] No se envió ND %s: %s', nota_debito.id, resultado.message)
            return False

        nota_debito.email_enviado = True
        nota_debito.email_enviado_at = timezone.now()
        nota_debito.email_ultimo_error = None
        nota_debito.save(update_fields=['email_enviado', 'email_enviado_at', 'email_envio_intentos', 'email_ultimo_error'])
        logger.info('[ND EMAIL] Nota de débito %s enviada a %s', nota_debito.id, ', '.join(resultado.recipients))
        return True
    except Exception as exc:
        nota_debito.email_ultimo_error = str(exc)
        nota_debito.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
        logger.exception('[ND EMAIL] Error enviando ND %s', nota_debito.id)
        return False


def _respuesta_nd_sigue_pendiente_sin_autorizacion(respuesta):
    estado = _normalizar_estado_nd_sri((respuesta or {}).get('estado'))
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
    return (
        'NO HA SIDO AUTORIZADO AÚN' in texto
        or 'NO HA SIDO AUTORIZADO AUN' in texto
        or 'NO EXISTE' in texto
        or estado in ('PENDIENTE', 'RECIBIDA')
    )


def _run_nd_sri_background(nota_debito_id, empresa_id, max_attempts=360, interval_seconds=10):
    import time
    from inventario.sri.sri_client import SRIClient
    from inventario.tenant.queryset import set_current_tenant
    from .integracion_sri_nd import IntegracionSRINotaDebito

    key = f'{empresa_id}:{nota_debito_id}'
    logger.info('[ND SRI BG] Inicio envío en background para ND %s (empresa %s)', nota_debito_id, empresa_id)
    try:
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if empresa is None:
            logger.warning('[ND SRI BG] Empresa %s no existe', empresa_id)
            return

        ya_contabilizada = False

        for _ in range(max_attempts):
            try:
                try:
                    set_current_tenant(empresa)
                except Exception:
                    logger.warning('[ND SRI BG] No se pudo establecer tenant para empresa %s', empresa_id)
                nota_debito = NotaDebito.objects.get(id=nota_debito_id, empresa_id=empresa_id)
            except NotaDebito.DoesNotExist:
                logger.warning('[ND SRI BG] ND %s no existe en empresa %s', nota_debito_id, empresa_id)
                break

            try:
                if nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion:
                    if not ya_contabilizada:
                        try:
                            incrementar_contador_documentos(empresa)
                        except Exception as exc:
                            logger.warning('[ND SRI BG] No se pudo incrementar contador para ND %s: %s', nota_debito_id, exc)
                        ya_contabilizada = True
                    _enviar_email_automatico_nd(nota_debito)
                    break

                integracion = IntegracionSRINotaDebito(nota_debito)
                estado_actual = _normalizar_estado_nd_sri(nota_debito.estado_sri)

                if estado_actual in ('AUTORIZADO', 'AUTORIZADA', 'RECHAZADO'):
                    logger.info('[ND SRI BG] ND %s ya en estado final %s', nota_debito_id, estado_actual)
                    break

                if estado_actual in ('RECIBIDA', 'PENDIENTE') and nota_debito.clave_acceso:
                    opciones = Opciones.objects.for_tenant(empresa).first()
                    if not opciones:
                        logger.warning('[ND SRI BG] No se encontró Opciones para empresa %s', empresa_id)
                        break

                    ambiente = 'pruebas' if str(getattr(opciones, 'tipo_ambiente', '1')) == '1' else 'produccion'
                    cliente = SRIClient(ambiente=ambiente)
                    respuesta = cliente.consultar_autorizacion(nota_debito.clave_acceso)
                    estado = _normalizar_estado_nd_sri(integracion._actualizar_con_respuesta(respuesta))
                    logger.info('[ND SRI BG] ND %s consulta autorización, estado=%s', nota_debito_id, estado or 'SIN_ESTADO')

                    if _respuesta_nd_sigue_pendiente_sin_autorizacion(respuesta):
                        logger.info('[ND SRI BG] ND %s sigue sin autorización final; se realiza reenvío automático completo', nota_debito_id)
                        resultado = integracion.procesar_completo()
                        estado = _normalizar_estado_nd_sri(resultado.get('estado'))
                        logger.info('[ND SRI BG] ND %s reenvío automático, estado=%s success=%s', nota_debito_id, estado or 'SIN_ESTADO', resultado.get('success'))
                else:
                    resultado = integracion.procesar_completo()
                    estado = _normalizar_estado_nd_sri(resultado.get('estado'))
                    logger.info('[ND SRI BG] ND %s intento envío, estado=%s success=%s', nota_debito_id, estado or 'SIN_ESTADO', resultado.get('success'))

                try:
                    nota_debito.refresh_from_db(fields=['estado_sri', 'numero_autorizacion', 'fecha_autorizacion'])
                except Exception:
                    pass

                if nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion:
                    if not ya_contabilizada:
                        try:
                            incrementar_contador_documentos(empresa)
                        except Exception as exc:
                            logger.warning('[ND SRI BG] No se pudo incrementar contador para ND %s: %s', nota_debito_id, exc)
                        ya_contabilizada = True
                    _enviar_email_automatico_nd(nota_debito)
                    break

                if estado in ('AUTORIZADO', 'AUTORIZADA', 'RECHAZADO'):
                    break

            except Exception as exc:
                logger.exception('[ND SRI BG] Error procesando ND %s en background: %s', nota_debito_id, exc)

            time.sleep(interval_seconds)
    finally:
        logger.info('[ND SRI BG] Fin envío en background para ND %s', nota_debito_id)
        lock = _get_nd_sri_envio_bg_lock()
        with lock:
            _nd_sri_envio_bg_jobs.pop(key, None)


def _start_nd_sri_background(nota_debito_id, empresa_id):
    key = f'{empresa_id}:{nota_debito_id}'
    lock = _get_nd_sri_envio_bg_lock()
    with lock:
        job = _nd_sri_envio_bg_jobs.get(key)
        if job and job.is_alive():
            logger.info('[ND SRI BG] Job ya en ejecución para %s', key)
            return False

        import threading
        job = threading.Thread(
            target=_run_nd_sri_background,
            args=(nota_debito_id, empresa_id),
            daemon=True,
        )
        _nd_sri_envio_bg_jobs[key] = job
        job.start()
        logger.info('[ND SRI BG] Job iniciado para %s', key)
        return True


class ListarNotasDebito(LoginRequiredMixin, View):
    """Vista para listar todas las notas de débito"""

    login_url = '/inventario/login'

    def get(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')

        q = request.GET.get('q', '')
        estado = request.GET.get('estado', '')

        notas_debito = (
            NotaDebito.objects.filter(empresa_id=empresa_id)
            .select_related('factura_modificada', 'factura_modificada__cliente')
            .order_by('-fecha_emision', '-secuencial')
        )

        if q:
            notas_debito = notas_debito.filter(
                factura_modificada__cliente__razon_social__icontains=q
            ) | notas_debito.filter(secuencial__icontains=q)

        if estado:
            notas_debito = notas_debito.filter(estado_sri=estado)

        contexto = {
            'notas_debito': notas_debito,
            'titulo': 'Notas de Débito',
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/nota_debito/listar.html', contexto)


class CrearNotaDebito(LoginRequiredMixin, View):
    """Vista para crear una Nota de Débito desde una factura autorizada"""

    login_url = '/inventario/login'
    SECUENCIA_TIPO_DOCUMENTO = '05'  # Nota de Débito

    def _calcular_datos_secuencia(self, empresa: Empresa, secuencia: Secuencia):
        if not empresa or not secuencia:
            return None

        # NotaDebito.establecimiento / punto_emision se guardan como strings zero-padded ("001").
        # Secuencia suele almacenar enteros (1). Para calcular el siguiente correctamente,
        # debemos comparar usando el mismo formato.
        establecimiento_str = f"{int(secuencia.establecimiento):03d}"
        punto_emision_str = f"{int(secuencia.punto_emision):03d}"

        max_existente = (
            NotaDebito.objects.filter(
                empresa=empresa,
                establecimiento=establecimiento_str,
                punto_emision=punto_emision_str,
            ).aggregate(m=Max('secuencial'))['m']
            or 0
        )

        base = secuencia.secuencial or 0
        if max_existente:
            siguiente = int(max_existente) + 1
        else:
            siguiente = max(int(base), 1)

        if siguiente > 999_999_999:
            raise ValueError('El secuencial ha alcanzado el valor máximo permitido (999999999).')

        return {
            'secuencia': secuencia,
            'establecimiento': establecimiento_str,
            'punto_emision': punto_emision_str,
            'valor': siguiente,
            'establecimiento_str': establecimiento_str,
            'punto_emision_str': punto_emision_str,
            'valor_str': f"{int(siguiente):09d}",
        }

    def _obtener_siguiente_secuencia(
        self,
        empresa: Empresa,
        secuencia_id: int | None = None,
        prefer_establecimiento: str | None = None,
        prefer_punto_emision: str | None = None,
    ):
        if not empresa:
            return None

        qs = Secuencia.objects.filter(
            empresa=empresa,
            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
            activo=True,
        )
        if secuencia_id:
            qs = qs.filter(id=secuencia_id)
        else:
            # Si la factura ya tiene establecimiento/punto, preferir esa secuencia (mismo patrón de UX esperado).
            try:
                estab_int = int(str(prefer_establecimiento or '').strip() or 0)
                punto_int = int(str(prefer_punto_emision or '').strip() or 0)
            except Exception:
                estab_int, punto_int = 0, 0
            if estab_int and punto_int:
                preferida = qs.filter(establecimiento=estab_int, punto_emision=punto_int).first()
                if preferida:
                    return self._calcular_datos_secuencia(empresa, preferida)

        secuencia = qs.order_by('establecimiento', 'punto_emision').first()
        if not secuencia:
            return None

        return self._calcular_datos_secuencia(empresa, secuencia)

    def get(self, request, factura_id=None):
        if factura_id is None:
            factura_id = request.GET.get('factura_id')

        if not factura_id:
            messages.error(request, 'Debe especificar una factura.')
            return redirect('inventario:listarFacturas')

        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')

        # Mantener la misma restricción de NC: requiere facturador autenticado
        facturador_id = request.session.get('facturador_id')
        if not facturador_id:
            next_url = f'/inventario/notas-debito/crear/{factura_id}/' if factura_id else '/inventario/notas-debito/crear/'
            return redirect(f'/inventario/login_facturador/?next={next_url}')

        empresa = get_object_or_404(Empresa, id=empresa_id)

        # Cajas + formas de pago + bancos (igual que NC)
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
            'Pichincha',
            'Produbanco',
            'Pacifico',
            'Machala',
            'Guayaquil',
            'Banecuador',
            'Internacional',
            'Procredit',
            'Austro',
            'Bolivariano',
            'Loja',
            'Amazonas',
            'Ruminahui',
        }
        lista_bancos = sorted({*(bancos_db or set()), *bancos_fallback})

        factura = get_object_or_404(Factura, id=factura_id, empresa=empresa)
        if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
            messages.error(request, 'Solo se pueden crear Notas de Débito para facturas AUTORIZADAS por el SRI.')
            return redirect('inventario:verFactura', p=factura_id)

        secuencia_info = self._obtener_siguiente_secuencia(
            empresa,
            prefer_establecimiento=getattr(factura, 'establecimiento', None),
            prefer_punto_emision=getattr(factura, 'punto_emision', None),
        )

        cedulas = Cliente.objects.filter(empresa=empresa).values_list('id', 'identificacion')
        almacenes = Almacen.objects.filter(activo=True, empresa=empresa)
        secuencias = Secuencia.objects.filter(
            empresa=empresa,
            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
            activo=True,
        ).order_by('establecimiento', 'punto_emision')

        initial = {
            'fecha_emision': date.today(),
            'fecha_vencimiento': date.today(),
            'identificacion_cliente': factura.identificacion_cliente or '',
            'nombre_cliente': factura.nombre_cliente or '',
        }
        if getattr(factura, 'almacen_id', None):
            initial['almacen'] = str(factura.almacen_id)

        # Correo del cliente: priorizar el correo guardado en la factura; fallback al cliente.
        correo_cliente = ''
        try:
            correo_cliente = (getattr(factura, 'correo', None) or '').strip()
        except Exception:
            correo_cliente = ''

        if not correo_cliente and getattr(factura, 'cliente', None):
            correo_cliente = (getattr(factura.cliente, 'correo', None) or '').strip()
            if not correo_cliente:
                # Compatibilidad defensiva si existiera un campo/propiedad alterna.
                correo_cliente = (getattr(factura.cliente, 'email', None) or '').strip()

        initial['correo_cliente'] = correo_cliente

        if secuencia_info:
            initial.update(
                {
                    'establecimiento': secuencia_info['establecimiento_str'],
                    'punto_emision': secuencia_info['punto_emision_str'],
                    'secuencia_valor': secuencia_info['valor_str'],
                    'secuencia': secuencia_info['secuencia'].id,
                }
            )

        form = EmitirFacturaFormulario(cedulas=cedulas, secuencias=secuencias, initial=initial)
        for campo in ('establecimiento', 'punto_emision', 'secuencia_valor'):
            if campo in form.fields:
                widget = form.fields[campo].widget
                clases_actuales = widget.attrs.get('class', '').strip()
                widget.attrs['class'] = f"{clases_actuales} bg-gray-100".strip()
                widget.attrs['readonly'] = 'readonly'
                widget.attrs['tabindex'] = '-1'

        # ✅ En Nota de Débito, el cliente viene de la factura sustento: bloquear edición.
        for campo in ('identificacion_cliente', 'nombre_cliente', 'correo_cliente'):
            if campo in form.fields:
                widget = form.fields[campo].widget
                clases_actuales = widget.attrs.get('class', '').strip()
                widget.attrs['class'] = f"{clases_actuales} bg-gray-100".strip()
                widget.attrs['readonly'] = 'readonly'
                widget.attrs['tabindex'] = '-1'

        # ✅ Igual que Nota de Crédito: cargar almacenes al select (IDs como string) y precargar el almacén de la factura.
        if 'almacen' in form.fields:
            form.fields['almacen'].choices = [('', '...')] + [(str(a.id), a.descripcion) for a in almacenes]
            if getattr(factura, 'almacen_id', None):
                form.fields['almacen'].initial = str(factura.almacen_id)

        # NOTA DE DÉBITO: NO copiar productos de la factura.
        # La ND agrega nuevos items/servicios para AUMENTAR el valor, así que la tabla inicia vacía.
        productos_factura: list[dict] = []
        total_general = Decimal('0.00')

        contexto = {
            'factura': factura,
            'opciones': Opciones.objects.for_tenant(empresa).first(),
            'form': form,
            'secuencias': secuencias,
            'secuencia_info': secuencia_info,
            'productos_factura': productos_factura,
            'productos_factura_json': '[]',
            'total_general': float(total_general),
            'today': date.today(),
            'titulo': f'Nueva Nota de Débito - Factura {factura.numero_completo}',
            'cajas': cajas_activas,
            'formas_pago_sri': formas_pago_sri,
            'bancos_lista_nombres': lista_bancos,
            'bancos_db': Banco.objects.filter(activo=True, empresa_id=empresa_id).order_by('banco'),
            'now': timezone.now(),
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/nota_debito/crear.html', contexto)

    def post(self, request, factura_id=None):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return JsonResponse({'success': False, 'message': 'Empresa no válida'})

        empresa = get_object_or_404(Empresa, id=empresa_id)

        try:
            nota_debito_id = None
            nota_debito_numero = None

            with transaction.atomic():
                factura_id_url = factura_id
                factura_id_hidden = request.POST.get('factura_modificada')
                factura_id_alt = request.POST.get('factura_id')

                factura_id = factura_id_url or factura_id_hidden or factura_id_alt
                if not factura_id:
                    messages.error(request, 'Debe especificar la factura a la que aplica la Nota de Débito.')
                    return redirect('inventario:listarFacturas')

                # Seguridad/consistencia: si viene factura_id por URL, debe coincidir con el hidden del formulario.
                if factura_id_url and factura_id_hidden and str(factura_id_url) != str(factura_id_hidden):
                    messages.error(
                        request,
                        'La factura seleccionada no coincide con el formulario (recargue e intente nuevamente).',
                    )
                    return redirect('inventario:listarFacturas')

                factura = get_object_or_404(Factura, id=factura_id, empresa=empresa)
                if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
                    messages.error(request, 'ERROR: La factura no está autorizada por el SRI. No se puede crear ND.')
                    return redirect('inventario:verFactura', p=factura_id)
                if not factura.clave_acceso:
                    messages.error(request, 'ERROR: La factura no tiene clave de acceso del SRI.')
                    return redirect('inventario:verFactura', p=factura_id)

                motivo = (request.POST.get('motivo') or '').strip()
                fecha_emision = request.POST.get('fecha_emision')
                if not motivo:
                    messages.error(request, 'Debe ingresar el motivo de la Nota de Débito.')
                    return redirect('inventario:notas_debito_crear_factura', factura_id=factura_id)

                productos = json.loads(request.POST.get('productos', '[]'))
                if not productos:
                    messages.error(request, 'Debe seleccionar al menos un producto.')
                    return redirect('inventario:notas_debito_crear_factura', factura_id=factura_id)

                subtotal = Decimal('0.00')
                total_iva = Decimal('0.00')
                subtotales_iva: dict[str, Decimal] = {}

                for prod in productos:
                    cantidad = Decimal(str(prod['cantidad']))
                    precio = Decimal(str(prod['precio_unitario']))
                    descuento = Decimal(str(prod.get('descuento', 0)))
                    tarifa = Decimal(str(prod.get('tarifa_iva', 15)))

                    subtotal_item = (cantidad * precio) - descuento
                    iva_item = subtotal_item * (tarifa / Decimal('100'))

                    subtotal += subtotal_item
                    total_iva += iva_item

                    tarifa_key = str(tarifa)
                    subtotales_iva[tarifa_key] = subtotales_iva.get(tarifa_key, Decimal('0.00')) + subtotal_item

                valor_total = subtotal + total_iva
                if valor_total <= 0:
                    messages.error(request, 'El total de la Nota de Débito debe ser mayor a 0.')
                    return redirect('inventario:notas_debito_crear_factura', factura_id=factura_id)

                # ================== SECUENCIA / ESTAB / PUNTO (copiar comportamiento de NC pero consistente con el form) ==================
                secuencia_id = (request.POST.get('secuencia') or '').strip()

                establecimiento = (request.POST.get('establecimiento') or '').strip() or (factura.establecimiento or '')
                punto_emision = (request.POST.get('punto_emision') or '').strip() or (factura.punto_emision or '')

                # Si el usuario seleccionó una Secuencia (tipo doc 05), usarla como fuente de verdad.
                secuencia_obj = None
                if secuencia_id.isdigit():
                    try:
                        secuencia_obj = Secuencia.objects.get(
                            id=int(secuencia_id),
                            empresa=empresa,
                            activo=True,
                            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
                        )
                        establecimiento = secuencia_obj.get_establecimiento_formatted()
                        punto_emision = secuencia_obj.get_punto_emision_formatted()
                    except Secuencia.DoesNotExist:
                        secuencia_obj = None

                # Calcular el siguiente secuencial de forma segura (igual idea que NC: máximo existente; si hay Secuencia, respetar base).
                max_existente = (
                    NotaDebito.objects.filter(
                        empresa=empresa,
                        establecimiento=establecimiento,
                        punto_emision=punto_emision,
                    ).aggregate(m=Max('secuencial'))['m']
                    or 0
                )
                base = int(getattr(secuencia_obj, 'secuencial', 0) or 0)
                if int(max_existente or 0) > 0:
                    siguiente = int(max_existente) + 1
                else:
                    siguiente = max(base, 1)
                if siguiente > 999_999_999:
                    raise ValueError('El secuencial ha alcanzado el valor máximo permitido (999999999).')
                nuevo_secuencial = f"{siguiente:09d}"

                nota_debito = NotaDebito.objects.create(
                    empresa=empresa,
                    factura_modificada=factura,
                    establecimiento=establecimiento,
                    punto_emision=punto_emision,
                    secuencial=nuevo_secuencial,
                    fecha_emision=fecha_emision,
                    cod_doc_modificado='01',
                    num_doc_modificado=factura.numero_completo,
                    fecha_emision_doc_sustento=factura.fecha_emision,
                    motivo=motivo,
                    subtotal_sin_impuestos=subtotal,
                    total_iva=total_iva,
                    valor_modificacion=valor_total,
                    estado_sri='PENDIENTE',
                    creado_por=request.user,
                )

                for prod in productos:
                    cantidad = Decimal(str(prod['cantidad']))
                    precio = Decimal(str(prod['precio_unitario']))
                    descuento = Decimal(str(prod.get('descuento', 0)))
                    codigo_iva = str(prod.get('codigo_iva', '4') or '4').strip()
                    tarifa = Decimal(str(prod.get('tarifa_iva', 15)))

                    base = (cantidad * precio) - descuento
                    valor_iva = base * (tarifa / Decimal('100'))
                    total = base + valor_iva

                    DetalleNotaDebito.objects.create(
                        nota_debito=nota_debito,
                        empresa=empresa,
                        codigo_principal=prod['codigo'],
                        descripcion=prod['descripcion'],
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento=descuento,
                        codigo_iva=codigo_iva,
                        tarifa_iva=tarifa,
                        base_imponible=base,
                        valor_iva=valor_iva,
                        total=total,
                    )

                for tarifa_str, base in subtotales_iva.items():
                    tarifa_dec = Decimal(tarifa_str)
                    valor_imp = base * (tarifa_dec / Decimal('100'))
                    TotalImpuestoNotaDebito.objects.create(
                        nota_debito=nota_debito,
                        codigo='2',
                        codigo_porcentaje=self._get_codigo_porcentaje(tarifa_dec),
                        tarifa=tarifa_dec,
                        base_imponible=base,
                        valor=valor_imp,
                    )

                nota_debito_id = nota_debito.id
                nota_debito_numero = nota_debito.numero_completo

            started = _start_nd_sri_background(nota_debito_id, empresa.id)
            if started:
                messages.success(
                    request,
                    f'Nota de Débito {nota_debito_numero} creada. Se iniciaron reintentos automáticos al SRI hasta que quede AUTORIZADA o NO AUTORIZADA.'
                )
            else:
                messages.success(request, f'Nota de Débito {nota_debito_numero} creada correctamente.')

            return redirect('inventario:notas_debito_ver', pk=nota_debito_id)

        except Exception as e:
            logger.exception('Error creando nota de débito')
            messages.error(request, f'Error al crear la nota de débito: {str(e)}')
            return redirect('inventario:listarFacturas')

    def _get_codigo_porcentaje(self, tarifa: Decimal) -> str:
        mapeo = {
            Decimal('0'): '0',
            Decimal('5'): '5',
            Decimal('13'): '10',
            Decimal('14'): '3',
            Decimal('15'): '4',
        }
        if tarifa == Decimal('12'):
            return '4'
        return mapeo.get(tarifa, '4')


class VerNotaDebito(LoginRequiredMixin, View):
    """Vista para ver detalle de una nota de débito"""

    login_url = '/inventario/login'

    def get(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Debe seleccionar una empresa.')
            return redirect('inventario:panel')

        nota_debito = get_object_or_404(
            NotaDebito.objects.select_related('factura_modificada', 'factura_modificada__cliente'),
            id=pk,
            empresa_id=empresa_id,
        )

        contexto = {
            'nota_debito': nota_debito,
            'titulo': f'Nota de Débito {nota_debito.numero_completo}',
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/nota_debito/ver.html', contexto)


class AutorizarNotaDebito(LoginRequiredMixin, View):
    """Autoriza ND en SRI (si el módulo XML/RIDE está implementado)."""

    login_url = '/inventario/login'

    def get(self, request, pk):
        return self.post(request, pk)

    def post(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:panel')

        nota_debito = get_object_or_404(NotaDebito, id=pk, empresa_id=empresa_id)
        if nota_debito.estado_sri == 'AUTORIZADO':
            messages.info(request, 'Esta nota de débito ya está autorizada.')
            return redirect('inventario:notas_debito_ver', pk=pk)

        # Control de plan: bloquear autorización si se alcanzó límite
        empresa = nota_debito.empresa
        estado_plan = obtener_estado_plan_y_notificar(empresa)
        if estado_plan.get('tiene_plan') and not estado_plan.get('puede_autorizar', True):
            messages.error(
                request,
                f"🚫 Ha alcanzado el límite de {estado_plan.get('limite_documentos')} documentos de su plan. "
                "No se puede autorizar una nueva Nota de Débito."
            )
            return redirect('inventario:notas_debito_ver', pk=pk)

        ya_autorizada = bool(nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion)

        try:
            from .integracion_sri_nd import IntegracionSRINotaDebito

            integracion = IntegracionSRINotaDebito(nota_debito)
            resultado = integracion.procesar_completo()

            if resultado.get('success'):
                # Incrementar contador SOLO si queda autorizada por primera vez
                nota_debito.refresh_from_db(fields=['numero_autorizacion', 'fecha_autorizacion', 'estado_sri'])
                ahora_autorizada = bool(nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion)
                estado_actual = _normalizar_estado_nd_sri(nota_debito.estado_sri)
                if (not ya_autorizada) and ahora_autorizada:
                    incrementar_contador_documentos(empresa)
                if ahora_autorizada:
                    _enviar_email_automatico_nd(nota_debito)
                    messages.success(request, 'Nota de Débito autorizada correctamente en SRI.')
                elif estado_actual == 'RECHAZADO':
                    messages.error(request, f'Nota de Débito no autorizada por el SRI. {nota_debito.mensaje_sri or ""}')
                else:
                    started = _start_nd_sri_background(nota_debito.id, empresa.id)
                    if started:
                        messages.info(request, 'La Nota de Débito fue enviada al SRI. El sistema seguirá reintentando automáticamente hasta que quede AUTORIZADA o NO AUTORIZADA.')
                    else:
                        messages.info(request, 'La Nota de Débito ya tiene un proceso automático en marcha hasta que el SRI responda AUTORIZADA o NO AUTORIZADA.')
            else:
                messages.error(request, f"Error al autorizar: {resultado.get('mensaje', 'Error desconocido')}")

        except NotImplementedError as e:
            messages.info(request, f'Autorizar ND: pendiente de implementación. {str(e)}')
        except Exception as e:
            logger.exception('Error autorizando ND')
            messages.error(request, f'Error al autorizar: {str(e)}')

        return redirect('inventario:notas_debito_ver', pk=pk)


class ConsultarEstadoNotaDebito(LoginRequiredMixin, View):
    """Consulta el estado SRI de la ND (sin reenviar)."""

    login_url = '/inventario/login'

    def get(self, request, pk):
        return self.post(request, pk)

    def post(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:panel')

        nota_debito = get_object_or_404(NotaDebito, id=pk, empresa_id=empresa_id)
        ya_autorizada = bool(nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion)
        if not nota_debito.clave_acceso:
            messages.error(request, 'Esta nota de débito no tiene clave de acceso. No se puede consultar el estado en el SRI.')
            return redirect('inventario:notas_debito_ver', pk=pk)

        try:
            opciones = Opciones.objects.for_tenant(nota_debito.empresa).first()
            if not opciones:
                messages.error(request, 'No se encontró configuración de opciones para la empresa.')
                return redirect('inventario:notas_debito_ver', pk=pk)

            ambiente = 'pruebas' if str(getattr(opciones, 'tipo_ambiente', '1')) == '1' else 'produccion'
            from inventario.sri.sri_client import SRIClient

            cliente = SRIClient(ambiente=ambiente)
            respuesta = cliente.consultar_autorizacion(nota_debito.clave_acceso)

            # Interpretación defensiva (estructura puede variar según implementación de SRIClient)
            estado = None
            if isinstance(respuesta, dict):
                estado = respuesta.get('estado') or respuesta.get('estado_autorizacion')

                autorizaciones = respuesta.get('autorizaciones') or []
                aut0 = autorizaciones[0] if isinstance(autorizaciones, list) and autorizaciones else {}
                if isinstance(aut0, dict):
                    if not estado:
                        estado = aut0.get('estado')
                    nota_debito.numero_autorizacion = aut0.get('numeroAutorizacion') or aut0.get('numero_autorizacion')

                    fecha_aut_raw = aut0.get('fechaAutorizacion') or aut0.get('fecha_autorizacion')
                    if fecha_aut_raw:
                        from datetime import datetime

                        fecha_aut_raw = str(fecha_aut_raw).strip()
                        fecha_aut = None
                        try:
                            fecha_aut = datetime.fromisoformat(fecha_aut_raw.replace('Z', '+00:00'))
                        except Exception:
                            try:
                                fecha_aut = datetime.strptime(fecha_aut_raw, '%d/%m/%Y %H:%M:%S')
                            except Exception:
                                fecha_aut = None

                        if fecha_aut:
                            nota_debito.fecha_autorizacion = fecha_aut

            estado = _normalizar_estado_nd_sri(estado)
            if estado:
                nota_debito.estado_sri = estado
            nota_debito.mensaje_sri = (str(respuesta) or '')[:2000]
            nota_debito.save(update_fields=['estado_sri', 'mensaje_sri', 'numero_autorizacion', 'fecha_autorizacion'])

            # Incrementar contador SOLO si se autorizó por primera vez vía consulta
            nota_debito.refresh_from_db(fields=['numero_autorizacion', 'fecha_autorizacion', 'estado_sri'])
            ahora_autorizada = bool(nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion)
            if (not ya_autorizada) and ahora_autorizada:
                incrementar_contador_documentos(nota_debito.empresa)
            if ahora_autorizada:
                _enviar_email_automatico_nd(nota_debito)

            if nota_debito.estado_sri == 'AUTORIZADO':
                messages.success(request, f'✅ Estado SRI: AUTORIZADO. Autorización: {nota_debito.numero_autorizacion or ""}')
            elif nota_debito.estado_sri in ('RECHAZADO', 'NO AUTORIZADO', 'NO_AUTORIZADO'):
                messages.error(request, f'❌ Estado SRI: NO AUTORIZADO. {nota_debito.mensaje_sri or ""}')
            else:
                started = _start_nd_sri_background(nota_debito.id, nota_debito.empresa_id)
                if started:
                    messages.info(request, 'La Nota de Débito sigue en proceso. El sistema continuará automáticamente hasta obtener AUTORIZADO o NO AUTORIZADO.')
                else:
                    messages.info(request, 'La Nota de Débito sigue en proceso automático hasta obtener AUTORIZADO o NO AUTORIZADO.')

        except Exception as e:
            logger.exception('Error consultando estado SRI de ND')
            messages.error(request, f'Error al consultar estado SRI: {str(e)}')

        return redirect('inventario:notas_debito_ver', pk=pk)


class DescargarPDFNotaDebito(LoginRequiredMixin, View):
    """Descarga el RIDE de la ND (si está implementado)."""

    login_url = '/inventario/login'

    def get(self, request, pk):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            messages.error(request, 'Empresa no válida.')
            return redirect('inventario:notas_debito_listar')

        nota_debito = get_object_or_404(NotaDebito, id=pk, empresa_id=empresa_id)
        try:
            from .ride_generator_nd import RIDENotaDebitoGenerator

            opciones = Opciones.objects.for_tenant(nota_debito.empresa).first()
            generator = RIDENotaDebitoGenerator(nota_debito, opciones)
            pdf_buffer = generator.generar_pdf()

            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f'ND_{nota_debito.numero_completo.replace("-", "_")}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except NotImplementedError as e:
            messages.info(request, f'PDF ND: pendiente de implementación. {str(e)}')
            return redirect('inventario:notas_debito_ver', pk=pk)
        except Exception as e:
            logger.exception('Error generando PDF de ND')
            messages.error(request, f'Error al generar PDF: {str(e)}')
            return redirect('inventario:notas_debito_ver', pk=pk)
