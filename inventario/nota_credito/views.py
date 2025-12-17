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
from inventario.models import Factura, Empresa, Opciones, DetalleFactura
from inventario.views import complementarContexto

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
        
        # Obtener establecimiento y punto de emisión desde la factura original
        opciones = Opciones.objects.for_tenant(empresa).first()
        establecimiento = factura.establecimiento  # Usar mismo establecimiento de la factura
        punto_emision = factura.punto_emision      # Usar mismo punto de emisión de la factura
        
        ultimo_secuencial = NotaCredito.objects.filter(
            empresa=empresa,
            establecimiento=establecimiento,
            punto_emision=punto_emision
        ).order_by('-secuencial').first()
        
        siguiente_secuencial = int(ultimo_secuencial.secuencial) + 1 if ultimo_secuencial else 1
        
        from datetime import date
        
        contexto = {
            'factura': factura,
            'opciones': opciones,
            'siguiente_secuencial': siguiente_secuencial,
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
