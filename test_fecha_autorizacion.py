"""
Script para probar la obtención de fecha de autorización del SRI
"""
import os
import django
import sys

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura, Opciones
from inventario.sri.integracion_django import SRIIntegration

def test_fecha_autorizacion():
    # Obtener una factura autorizada reciente
    facturas = Factura.objects.filter(estado='AUTORIZADO').order_by('-id')[:5]
    
    if not facturas.exists():
        print("❌ No hay facturas autorizadas en el sistema")
        return
    
    print(f"\n📋 Encontradas {facturas.count()} facturas autorizadas\n")
    
    for factura in facturas:
        print(f"\n{'='*80}")
        print(f"🧾 Factura #{factura.secuencia}")
        print(f"   ID: {factura.id}")
        print(f"   Clave de acceso: {factura.clave_acceso}")
        print(f"   Fecha emisión: {factura.fecha_emision}")
        print(f"   Fecha autorización (BD actual): {factura.fecha_autorizacion}")
        print(f"   Número autorización: {factura.numero_autorizacion}")
        
        # Consultar en el SRI
        print(f"\n🔍 Consultando en el SRI...")
        
        opciones = Opciones.objects.filter(empresa=factura.empresa).first()
        sri = SRIIntegration(empresa=factura.empresa, opciones=opciones)
        
        resultado = sri.cliente.consultar_autorizacion(factura.clave_acceso)
        
        print(f"\n📡 Respuesta completa del SRI:")
        print(f"   Estado: {resultado.get('estado')}")
        print(f"   Raw response keys: {resultado.keys()}")
        
        # Extraer autorizaciones
        autorizaciones = resultado.get('autorizaciones')
        if autorizaciones:
            print(f"\n✅ Autorizaciones encontradas:")
            print(f"   Tipo: {type(autorizaciones)}")
            
            # Extraer primera autorización
            aut = None
            if isinstance(autorizaciones, list):
                aut = autorizaciones[0] if autorizaciones else None
            elif isinstance(autorizaciones, dict):
                aut_data = autorizaciones.get('autorizacion', autorizaciones)
                aut = aut_data[0] if isinstance(aut_data, list) else aut_data
            else:
                aut_data = getattr(autorizaciones, 'autorizacion', autorizaciones)
                aut = aut_data[0] if isinstance(aut_data, list) else aut_data
            
            if aut:
                print(f"\n📄 Datos de autorización:")
                if isinstance(aut, dict):
                    for key, value in aut.items():
                        print(f"   {key}: {value}")
                else:
                    for attr in dir(aut):
                        if not attr.startswith('_'):
                            try:
                                value = getattr(aut, attr)
                                if not callable(value):
                                    print(f"   {attr}: {value}")
                            except:
                                pass
                
                # Fecha específica
                fecha_aut = None
                if isinstance(aut, dict):
                    fecha_aut = aut.get('fechaAutorizacion') or aut.get('fecha_autorizacion')
                else:
                    fecha_aut = getattr(aut, 'fechaAutorizacion', None) or getattr(aut, 'fecha_autorizacion', None)
                
                print(f"\n🎯 FECHA DE AUTORIZACIÓN: {fecha_aut}")
                print(f"   Tipo: {type(fecha_aut)}")
                
        else:
            print(f"\n❌ No se encontraron autorizaciones en la respuesta")
        
        print(f"\n{'='*80}\n")
        
        # Solo mostrar la primera factura en detalle
        break

if __name__ == '__main__':
    test_fecha_autorizacion()
