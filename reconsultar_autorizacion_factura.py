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
    """Re-consulta una factura autorizada para obtener fecha_autorizacion"""
    
    try:
        factura = Factura.objects.get(id=factura_id)
    except Factura.DoesNotExist:
        print(f"❌ ERROR: No existe factura con ID {factura_id}")
        return False
    
    print("\n" + "="*80)
    print(f"🔄 RE-CONSULTANDO AUTORIZACIÓN DE FACTURA #{factura.id}")
    print("="*80 + "\n")
    
    print(f"📄 Factura: {factura.secuencia}")
    print(f"   Estado SRI actual: {factura.estado_sri}")
    print(f"   Clave de acceso: {factura.clave_acceso}")
    print(f"   📅 Fecha emisión: {factura.fecha_emision}")
    print(f"   📅 Fecha autorización (ANTES): {factura.fecha_autorizacion}")
    print(f"   🔢 Número autorización: {factura.numero_autorizacion}")
    
    if not factura.clave_acceso:
        print(f"\n❌ ERROR: La factura no tiene clave de acceso")
        return False
    
    # Consultar en el SRI
    print(f"\n🔍 Consultando estado en el SRI...")
    
    try:
        opciones = Opciones.objects.filter(empresa=factura.empresa).first()
        sri = SRIIntegration(empresa=factura.empresa)
        
        # Consultar autorización
        resultado = sri.cliente.consultar_autorizacion(factura.clave_acceso)
        
        print(f"\n📡 Respuesta del SRI:")
        print(f"   Estado: {resultado.get('estado')}")
        
        # Actualizar factura con el resultado
        print(f"\n💾 Actualizando factura en BD...")
        sri._actualizar_factura_con_resultado(factura, resultado, factura.clave_acceso)
        
        # Recargar desde BD
        factura.refresh_from_db()
        
        print(f"\n✅ FACTURA ACTUALIZADA:")
        print(f"   Estado SRI: {factura.estado_sri}")
        print(f"   📅 Fecha autorización (DESPUÉS): {factura.fecha_autorizacion}")
        print(f"   🔢 Número autorización: {factura.numero_autorizacion}")
        
        if factura.fecha_autorizacion:
            print(f"\n🎉 ¡ÉXITO! La fecha de autorización se guardó correctamente")
            print(f"   Ahora el RIDE mostrará: {factura.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S')}")
            return True
        else:
            print(f"\n⚠️ ADVERTENCIA: La fecha de autorización sigue siendo None")
            print(f"   Verifica los logs del sistema para más detalles")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR al consultar: {e}")
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
