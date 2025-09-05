from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction, models
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, date
import json
import logging

from .models import GuiaRemision, DetalleGuiaRemision, ConfiguracionGuiaRemision
from .ride_guia_generator import GuiaRemisionRIDEGenerator

logger = logging.getLogger(__name__)


@login_required
def listar_guias_remision(request):
    """
    Vista para listar todas las guías de remisión con filtros y paginación
    """
    # Obtener parámetros de filtro
    numero = request.GET.get('numero', '').strip()
    cliente = request.GET.get('cliente', '').strip()
    estado = request.GET.get('estado', '').strip()
    fecha = request.GET.get('fecha', '').strip()
    
    # Query base
    guias = GuiaRemision.objects.all()
    
    # Aplicar filtros
    if numero:
        guias = guias.filter(secuencial__icontains=numero)
    
    if cliente:
        guias = guias.filter(
            models.Q(destinatario_nombre__icontains=cliente) |
            models.Q(destinatario_identificacion__icontains=cliente)
        )
    
    if estado:
        guias = guias.filter(estado=estado)
    
    if fecha:
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
            guias = guias.filter(fecha_emision=fecha_obj)
        except ValueError:
            pass
    
    # Ordenar por fecha y secuencial
    guias = guias.order_by('-fecha_emision', '-secuencial')
    
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
    
    return render(request, 'inventario/guia_remision/listarGuiasRemision.html', context)


@login_required
def emitir_guia_remision(request):
    """
    Vista para crear una nueva guía de remisión
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obtener configuración
                config = ConfiguracionGuiaRemision.get_configuracion()
                
                # Crear la guía
                guia = GuiaRemision(
                    establecimiento=config.establecimiento_defecto,
                    punto_emision=config.punto_emision_defecto,
                    fecha_emision=request.POST.get('fecha_emision'),
                    fecha_inicio_traslado=request.POST.get('fecha_inicio_traslado'),
                    fecha_fin_traslado=request.POST.get('fecha_fin_traslado') or None,
                    motivo_traslado=request.POST.get('motivo_traslado'),
                    destinatario_identificacion=request.POST.get('destinatario_identificacion'),
                    destinatario_nombre=request.POST.get('destinatario_nombre'),
                    direccion_partida=request.POST.get('direccion_partida'),
                    direccion_destino=request.POST.get('direccion_destino'),
                    transportista_ruc=request.POST.get('transportista_ruc'),
                    transportista_nombre=request.POST.get('transportista_nombre'),
                    placa=request.POST.get('placa'),
                    transportista_observaciones=request.POST.get('transportista_observaciones', ''),
                    usuario_creacion=request.user,
                    estado='autorizada'  # Por ahora crear directamente como autorizada
                )
                guia.save()
                
                # Procesar productos
                productos_data = _extraer_productos_del_post(request.POST)
                for i, producto in enumerate(productos_data, 1):
                    if producto['codigo'] and producto['descripcion'] and producto['cantidad']:
                        DetalleGuiaRemision.objects.create(
                            guia=guia,
                            orden=i,
                            codigo_producto=producto['codigo'],
                            descripcion_producto=producto['descripcion'],
                            cantidad=producto['cantidad']
                        )
                
                # Generar clave de acceso (simplificada por ahora)
                guia.clave_acceso = _generar_clave_acceso_temporal(guia)
                guia.numero_autorizacion = guia.clave_acceso
                guia.fecha_autorizacion = timezone.now()
                guia.save()
                
                messages.success(request, f'Guía de remisión {guia.numero_completo} creada exitosamente.')
                return redirect('inventario:ver_guia_remision', guia_id=guia.id)
                
        except Exception as e:
            logger.error(f"Error al crear guía de remisión: {str(e)}")
            messages.error(request, f'Error al crear la guía: {str(e)}')
    
    # GET request - mostrar formulario
    context = {
        'fecha_hoy': date.today().isoformat(),
        'configuracion': ConfiguracionGuiaRemision.get_configuracion(),
    }
    
    return render(request, 'inventario/guia_remision/emitirGuiaRemision.html', context)


@login_required
def ver_guia_remision(request, guia_id):
    """
    Vista para ver los detalles de una guía de remisión
    """
    guia = get_object_or_404(GuiaRemision, id=guia_id)
    
    context = {
        'guia': guia,
    }
    
    return render(request, 'inventario/guia_remision/verGuiaRemision.html', context)


@login_required
def editar_guia_remision(request, guia_id):
    """
    Vista para editar una guía de remisión (solo si está en borrador)
    """
    guia = get_object_or_404(GuiaRemision, id=guia_id)
    
    if not guia.puede_editarse():
        messages.error(request, 'No se puede editar una guía que no está en borrador.')
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
                            orden=i,
                            codigo_producto=producto['codigo'],
                            descripcion_producto=producto['descripcion'],
                            cantidad=producto['cantidad']
                        )
                
                messages.success(request, f'Guía de remisión {guia.numero_completo} actualizada exitosamente.')
                return redirect('inventario:ver_guia_remision', guia_id=guia.id)
                
        except Exception as e:
            logger.error(f"Error al actualizar guía de remisión: {str(e)}")
            messages.error(request, f'Error al actualizar la guía: {str(e)}')
    
    # GET request - mostrar formulario con datos
    context = {
        'guia': guia,
        'configuracion': ConfiguracionGuiaRemision.get_configuracion(),
    }
    
    return render(request, 'inventario/guia_remision/editarGuiaRemision.html', context)


@login_required
@require_http_methods(["POST"])
def anular_guia_remision(request, guia_id):
    """
    Vista para anular una guía de remisión
    """
    guia = get_object_or_404(GuiaRemision, id=guia_id)
    
    if not guia.puede_anularse():
        return JsonResponse({
            'success': False,
            'message': 'No se puede anular esta guía en su estado actual.'
        })
    
    try:
        guia.estado = 'anulada'
        guia.usuario_modificacion = request.user
        guia.save()
        
        logger.info(f"Guía de remisión {guia.numero_completo} anulada por {request.user.username}")
        
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


@login_required
def descargar_guia_pdf(request, guia_id):
    """
    Vista para descargar el PDF de una guía de remisión
    """
    guia = get_object_or_404(GuiaRemision, id=guia_id)
    
    if guia.estado != 'autorizada':
        messages.error(request, 'Solo se puede descargar PDF de guías autorizadas.')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)
    
    try:
        # Generar PDF usando el generador RIDE
        generator = GuiaRemisionRIDEGenerator()
        pdf_buffer = generator.generar_ride_guia_remision(guia)
        
        # Preparar respuesta HTTP
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="guia_remision_{guia.numero_completo}.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error al generar PDF de guía {guia_id}: {str(e)}")
        messages.error(request, f'Error al generar PDF: {str(e)}')
        return redirect('inventario:ver_guia_remision', guia_id=guia.id)


@login_required
@csrf_exempt
def buscar_cliente_ajax(request):
    """
    Vista AJAX para buscar clientes por identificación
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    identificacion = request.POST.get('identificacion', '').strip()
    
    if not identificacion:
        return JsonResponse({'success': False, 'message': 'Identificación requerida'})
    
    try:
        # TODO: Integrar con el modelo de clientes existente
        # Por ahora retornar datos de ejemplo
        cliente_data = {
            'identificacion': identificacion,
            'nombre': f'Cliente Ejemplo {identificacion}',
            'direccion': 'Dirección de ejemplo',
        }
        
        return JsonResponse({
            'success': True,
            'cliente': cliente_data
        })
        
    except Exception as e:
        logger.error(f"Error al buscar cliente {identificacion}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error al buscar cliente: {str(e)}'
        })


# Funciones auxiliares

def _extraer_productos_del_post(post_data):
    """
    Extrae los datos de productos del POST request
    """
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
    """
    Genera una clave de acceso temporal para la guía
    TODO: Implementar algoritmo oficial del SRI
    """
    fecha_str = guia.fecha_emision.strftime('%d%m%Y')
    tipo_comprobante = '06'  # Código SRI para guía de remisión
    ruc = '1234567890001'  # TODO: Obtener del modelo de empresa
    ambiente = '1'  # Pruebas
    serie = f"{guia.establecimiento}{guia.punto_emision}"
    secuencial = guia.secuencial
    codigo_numerico = '12345678'  # Número aleatorio de 8 dígitos
    tipo_emision = '1'
    
    # Construir clave sin dígito verificador
    clave_sin_dv = fecha_str + tipo_comprobante + ruc + ambiente + serie + secuencial + codigo_numerico + tipo_emision
    
    # TODO: Calcular dígito verificador según algoritmo módulo 11
    digito_verificador = '1'  # Temporal
    
    return clave_sin_dv + digito_verificador
