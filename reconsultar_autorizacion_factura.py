"""
Script para re-consultar autorización de facturas ya autorizadas
y actualizar la fecha_autorizacion en la base de datos
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura, Opciones
from inventario.sri.integracion_django import SRIIntegration

def reconsultar_factura(factura_id):
    """Re-consulta una factura autorizada para obtener fecha_autorizacion desde XML guardado"""
    
    try:
        factura = Factura.objects.get(id=factura_id)
    except Factura.DoesNotExist:
        print(f"❌ ERROR: No existe factura con ID {factura_id}")
        return False
    
    print("\n" + "="*80)
    print(f"🔄 EXTRAYENDO FECHA DE AUTORIZACIÓN DE FACTURA #{factura.id}")
    print("="*80 + "\n")
    
    print(f"📄 Factura: {factura.secuencia}")
    print(f"   Estado SRI actual: {factura.estado_sri}")
    print(f"   📅 Fecha emisión: {factura.fecha_emision}")
    print(f"   📅 Fecha autorización (ANTES): {factura.fecha_autorizacion}")
    print(f"   🔢 Número autorización: {factura.numero_autorizacion}")
    
    # ✅ EXTRAER DESDE XML GUARDADO
    if not factura.respuesta_sri:
        print(f"\n⚠️ ADVERTENCIA: La factura no tiene respuesta XML guardada")
        print(f"   Intentando consultar al SRI...")
        
        if not factura.clave_acceso:
            print(f"❌ ERROR: La factura tampoco tiene clave de acceso")
            return False
        
        # Consultar SRI
        try:
            sri = SRIIntegration(empresa=factura.empresa)
            resultado = sri.cliente.consultar_autorizacion(factura.clave_acceso)
            
            # Actualizar con resultado
            sri._actualizar_factura_con_resultado(factura, resultado, factura.clave_acceso)
            factura.refresh_from_db()
            
        except Exception as e:
            print(f"❌ ERROR al consultar SRI: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Parsear XML guardado
    print(f"\n🔍 Parseando XML de respuesta guardado...")
    
    try:
        from xml.etree import ElementTree as ET
        from datetime import datetime
        import pytz
        
        root = ET.fromstring(factura.respuesta_sri)
        
        # Buscar el elemento autorizacion
        ns = {'ns': 'http://ec.gob.sri.ws.autorizacion'}
        autorizacion = root.find('.//ns:autorizacion', ns)
        
        if not autorizacion:
            # Intentar sin namespace
            autorizacion = root.find('.//autorizacion')
        
        if not autorizacion:
            print(f"❌ ERROR: No se encontró elemento 'autorizacion' en el XML")
            print(f"   XML guardado:\n{factura.respuesta_sri[:500]}...")
            return False
        
        # Extraer datos
        estado = autorizacion.find('.//estado', ns) or autorizacion.find('.//estado')
        numero_aut = autorizacion.find('.//numeroAutorizacion', ns) or autorizacion.find('.//numeroAutorizacion')
        fecha_aut = autorizacion.find('.//fechaAutorizacion', ns) or autorizacion.find('.//fechaAutorizacion')
        
        print(f"\n📋 Datos extraídos del XML:")
        print(f"   Estado: {estado.text if estado is not None else 'No encontrado'}")
        print(f"   Número: {numero_aut.text if numero_aut is not None else 'No encontrado'}")
        print(f"   Fecha (raw): {fecha_aut.text if fecha_aut is not None else 'No encontrado'}")
        
        if fecha_aut is None or not fecha_aut.text:
            print(f"❌ ERROR: No se pudo extraer fechaAutorizacion del XML")
            return False
        
        # Parsear fecha
        fecha_str = fecha_aut.text.strip()
        fecha_parseada = None
        
        # Intentar diferentes formatos
        formatos = [
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
        ]
        
        for formato in formatos:
            try:
                fecha_parseada = datetime.strptime(fecha_str, formato)
                if fecha_parseada.tzinfo is None:
                    # Si no tiene timezone, asignar Ecuador
                    ecuador_tz = pytz.timezone('America/Guayaquil')
                    fecha_parseada = ecuador_tz.localize(fecha_parseada)
                break
            except:
                continue
        
        if not fecha_parseada:
            print(f"❌ ERROR: No se pudo parsear la fecha: {fecha_str}")
            return False
        
        print(f"   ✅ Fecha parseada: {fecha_parseada}")
        
        # Actualizar factura
        print(f"\n💾 Actualizando factura en BD...")
        
        if estado is not None:
            estado_normalizado = estado.text.upper().strip()
            if estado_normalizado == 'AUTORIZADO':
                estado_normalizado = 'AUTORIZADA'
            factura.estado_sri = estado_normalizado
        
        if numero_aut is not None:
            factura.numero_autorizacion = numero_aut.text.strip()
        
        factura.fecha_autorizacion = fecha_parseada
        factura.save()
        
        print(f"\n✅ FACTURA ACTUALIZADA:")
        print(f"   Estado SRI: {factura.estado_sri}")
        print(f"   📅 Fecha autorización: {factura.fecha_autorizacion}")
        print(f"   🔢 Número autorización: {factura.numero_autorizacion}")
        print(f"\n🎉 ¡ÉXITO! Ahora el RIDE mostrará: {factura.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S')}")
        
        return True
            
    except Exception as e:
        print(f"\n❌ ERROR parseando XML: {e}")
        import traceback
        traceback.print_exc()
        return False

def reconsultar_todas_autorizadas():
    """Re-consulta todas las facturas autorizadas sin fecha_autorizacion"""
    
    print("\n" + "="*80)
    print("🔄 RE-CONSULTANDO TODAS LAS FACTURAS AUTORIZADAS")
    print("="*80 + "\n")
    
    # Buscar facturas autorizadas sin fecha_autorizacion
    facturas = Factura.objects.filter(
        estado_sri__in=['AUTORIZADA', 'AUTORIZADO']
    ).exclude(
        fecha_autorizacion__isnull=False
    )
    
    if not facturas.exists():
        print("✅ No hay facturas autorizadas que necesiten actualización")
        print("   Todas las facturas autorizadas ya tienen fecha_autorizacion")
        return
    
    print(f"📋 Encontradas {facturas.count()} facturas autorizadas sin fecha_autorizacion\n")
    
    exitos = 0
    fallos = 0
    
    for factura in facturas:
        print(f"\n{'─'*80}")
        if reconsultar_factura(factura.id):
            exitos += 1
        else:
            fallos += 1
    
    print(f"\n" + "="*80)
    print(f"📊 RESUMEN:")
    print(f"   ✅ Exitosos: {exitos}")
    print(f"   ❌ Fallidos: {fallos}")
    print(f"   📊 Total: {exitos + fallos}")
    print("="*80 + "\n")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # Re-consultar factura específica por ID
        factura_id = int(sys.argv[1])
        reconsultar_factura(factura_id)
    else:
        # Re-consultar todas las facturas autorizadas sin fecha
        reconsultar_todas_autorizadas()
