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

            # Normativa: enviar ND al SRI al emitirla.
            # Se hace fuera del `atomic()` para no perder la ND si falla el SRI.
            messages.success(request, f'Nota de Débito {nota_debito_numero} creada. Enviando al SRI...')
            try:
                from .integracion_sri_nd import IntegracionSRINotaDebito

                nota_debito = NotaDebito.objects.get(id=nota_debito_id, empresa_id=empresa_id)
                integracion = IntegracionSRINotaDebito(nota_debito)
                resultado = integracion.procesar_completo()

                if resultado.get('success'):
                    messages.success(request, '✅ Nota de Débito procesada correctamente en SRI.')
                else:
                    messages.error(
                        request,
                        f"❌ No se pudo autorizar en SRI: {resultado.get('mensaje', 'Error desconocido')}",
                    )
            except Exception as e:
                logger.exception('Error enviando ND automáticamente al SRI')
                messages.error(request, f'Error al enviar al SRI: {str(e)}')

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
                if (not ya_autorizada) and ahora_autorizada:
                    incrementar_contador_documentos(empresa)
                messages.success(request, 'Nota de Débito procesada correctamente en SRI.')
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
                autorizacion = respuesta.get('autorizacion')
                if isinstance(autorizacion, dict) and not estado:
                    estado = autorizacion.get('estado')
                if autorizacion and isinstance(autorizacion, dict):
                    nota_debito.numero_autorizacion = autorizacion.get('numeroAutorizacion') or autorizacion.get('numero_autorizacion')
                    nota_debito.fecha_autorizacion = autorizacion.get('fechaAutorizacion') or autorizacion.get('fecha_autorizacion')

            if estado:
                nota_debito.estado_sri = estado
            nota_debito.mensaje_sri = (str(respuesta) or '')[:2000]
            nota_debito.save(update_fields=['estado_sri', 'mensaje_sri', 'numero_autorizacion', 'fecha_autorizacion'])

            # Incrementar contador SOLO si se autorizó por primera vez vía consulta
            nota_debito.refresh_from_db(fields=['numero_autorizacion', 'fecha_autorizacion', 'estado_sri'])
            ahora_autorizada = bool(nota_debito.numero_autorizacion and nota_debito.fecha_autorizacion)
            if (not ya_autorizada) and ahora_autorizada:
                incrementar_contador_documentos(nota_debito.empresa)

            if nota_debito.estado_sri == 'AUTORIZADO':
                messages.success(request, f'✅ Estado SRI: {nota_debito.estado_sri}. Autorización: {nota_debito.numero_autorizacion or ""}')
            elif nota_debito.estado_sri in ('RECHAZADO', 'NO AUTORIZADO'):
                messages.error(request, f'❌ Estado SRI: {nota_debito.estado_sri}. {nota_debito.mensaje_sri or ""}')
            else:
                messages.info(request, f'ℹ️ Estado SRI: {nota_debito.estado_sri}. {nota_debito.mensaje_sri or ""}')

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
