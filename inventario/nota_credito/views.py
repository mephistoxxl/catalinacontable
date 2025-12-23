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
import json
import logging

from .models import NotaCredito, DetalleNotaCredito, TotalImpuestoNotaCredito
from inventario.models import Factura, Empresa, Opciones, DetalleFactura, Cliente, Almacen, Secuencia, Facturador
from inventario.views import complementarContexto
from inventario.forms import EmitirFacturaFormulario
from django.db.models import Max

logger = logging.getLogger(__name__)


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
        if factura.cliente and hasattr(factura.cliente, 'email'):
            initial['correo_cliente'] = factura.cliente.email or ''
        
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
                '0': 0, '2': 12, '3': 14, '4': 15, '5': 5,
                '6': 0, '7': 0, '8': 0, '10': 13,
            }
            
            if detalle.producto:
                codigo = detalle.producto.codigo
                descripcion = detalle.producto.descripcion
                precio = float(detalle.precio_unitario or detalle.producto.precio or 0)
                codigo_iva = detalle.iva_codigo or detalle.producto.iva or '2'
                producto_id = detalle.producto_id
                servicio_id = None
            elif detalle.servicio:
                codigo = detalle.servicio.codigo
                descripcion = detalle.servicio.descripcion
                precio = float(detalle.precio_unitario or detalle.servicio.precio1 or 0)
                codigo_iva = detalle.iva_codigo or detalle.servicio.iva or '2'
                producto_id = None
                servicio_id = detalle.servicio_id
            else:
                codigo = 'SIN_CODIGO'
                descripcion = 'Sin descripción'
                precio = float(detalle.precio_unitario or 0)
                codigo_iva = '2'
                producto_id = None
                servicio_id = None
            
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
            'titulo': f'Nueva Nota de Crédito - Factura {factura.numero_completo}'
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/nota_credito/crear.html', contexto)
    
    def post(self, request):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return JsonResponse({'success': False, 'message': 'Empresa no válida'})
        
        empresa = get_object_or_404(Empresa, id=empresa_id)
        
        try:
            with transaction.atomic():
                # Obtener datos del formulario
                factura_id = request.POST.get('factura_modificada')
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
                
                tipo_motivo = request.POST.get('tipo_motivo')
                motivo = request.POST.get('motivo')
                fecha_emision = request.POST.get('fecha_emision')
                
                # Obtener productos seleccionados
                productos_json = request.POST.get('productos', '[]')
                productos = json.loads(productos_json)
                
                if not productos:
                    messages.error(request, 'Debe seleccionar al menos un producto.')
                    return redirect('inventario:notas_credito_crear', factura_id=factura_id)
                
                # Calcular totales
                subtotal = Decimal('0.00')
                total_iva = Decimal('0.00')
                subtotales_iva = {}
                
                for prod in productos:
                    cantidad = Decimal(str(prod['cantidad']))
                    precio = Decimal(str(prod['precio_unitario']))
                    descuento = Decimal(str(prod.get('descuento', 0)))
                    tarifa = Decimal(str(prod.get('tarifa_iva', 15)))
                    
                    subtotal_item = (cantidad * precio) - descuento
                    iva_item = subtotal_item * (tarifa / Decimal('100'))
                    
                    subtotal += subtotal_item
                    total_iva += iva_item
                    
                    # Agrupar por tarifa
                    tarifa_key = str(tarifa)
                    if tarifa_key not in subtotales_iva:
                        subtotales_iva[tarifa_key] = Decimal('0.00')
                    subtotales_iva[tarifa_key] += subtotal_item
                
                valor_total = subtotal + total_iva
                
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
                        codigo_iva=prod.get('codigo_iva', '4'),
                        tarifa_iva=Decimal(str(prod.get('tarifa_iva', 15)))
                    )
                
                # Crear totales de impuestos
                for tarifa, base in subtotales_iva.items():
                    valor_imp = base * (Decimal(tarifa) / Decimal('100'))
                    TotalImpuestoNotaCredito.objects.create(
                        nota_credito=nota_credito,
                        empresa=empresa,
                        codigo='2',  # IVA
                        codigo_porcentaje=self._get_codigo_porcentaje(Decimal(tarifa)),
                        tarifa=Decimal(tarifa),
                        base_imponible=base,
                        valor=valor_imp
                    )
                
                messages.success(request, f'Nota de Crédito {nota_credito.numero_completo} creada correctamente.')
                return redirect('inventario:notas_credito_ver', pk=nota_credito.id)
        
        except Exception as e:
            logger.exception("Error creando nota de crédito")
            messages.error(request, f'Error al crear la nota de crédito: {str(e)}')
            return redirect('inventario:listarFacturas')
    
    def _get_codigo_porcentaje(self, tarifa):
        """Obtiene el código de porcentaje según la tarifa"""
        mapeo = {
            Decimal('0'): '0',
            Decimal('5'): '5',
            Decimal('12'): '2',
            Decimal('13'): '10',
            Decimal('14'): '3',
            Decimal('15'): '4',
        }
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
                    'codigo_iva': d.iva_codigo or (d.producto.iva if d.producto else d.servicio.iva if d.servicio else '4'),
                    'tarifa_iva': self._get_tarifa_from_codigo(d.iva_codigo or (d.producto.iva if d.producto else d.servicio.iva if d.servicio else '4')),
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
            '2': 12,
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
        
        try:
            from .integracion_sri_nc import IntegracionSRINotaCredito
            
            integracion = IntegracionSRINotaCredito(nota_credito)
            resultado = integracion.procesar_completo()
            
            if resultado['success']:
                messages.success(request, f'Nota de Crédito autorizada correctamente. Autorización: {resultado.get("numero_autorizacion", "")}')
            else:
                messages.error(request, f'Error al autorizar: {resultado.get("mensaje", "Error desconocido")}')
        
        except Exception as e:
            logger.exception("Error autorizando NC")
            messages.error(request, f'Error al autorizar: {str(e)}')
        
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
