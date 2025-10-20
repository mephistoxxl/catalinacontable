"""
Script para probar el envío manual de email
Ejecutar: python test_envio_email_manual.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration

print("=" * 60)
print("TEST: ENVÍO MANUAL DE EMAIL")
print("=" * 60)

# Buscar facturas AUTORIZADAS
facturas_autorizadas = Factura.objects.filter(estado_sri='AUTORIZADA').order_by('-id')[:5]

if not facturas_autorizadas.exists():
    print("\n❌ No hay facturas AUTORIZADAS en la base de datos")
    print("   Primero debes enviar y autorizar una factura al SRI")
else:
    print(f"\n✅ Se encontraron {facturas_autorizadas.count()} facturas AUTORIZADAS")
    
    for factura in facturas_autorizadas:
        print(f"\n📄 Factura #{factura.id}:")
        print(f"   Número: {factura.numero}")
        print(f"   Cliente: {factura.nombre_cliente}")
        print(f"   Email cliente: {getattr(factura.cliente, 'correo', 'SIN EMAIL')}")
        print(f"   Estado SRI: {factura.estado_sri}")
        print(f"   Autorización: {factura.numero_autorizacion or 'N/A'}")
        print(f"   RIDE guardado: {'✅ Sí' if getattr(factura, 'ride_autorizado', None) else '❌ No'}")
    
    # Intentar enviar la primera factura
    factura_test = facturas_autorizadas.first()
    print(f"\n" + "="*60)
    print(f"INTENTANDO ENVIAR EMAIL PARA FACTURA #{factura_test.id}")
    print("="*60)
    
    cliente_email = getattr(factura_test.cliente, 'correo', None)
    if not cliente_email:
        print("\n⚠️ El cliente NO tiene email configurado")
        print("   Debes agregar un email al cliente antes de enviar")
    else:
        print(f"\n📧 Destinatario: {cliente_email}")
        
        sri = SRIIntegration()
        resultado = sri.enviar_factura_email(factura_test)
        
        print(f"\n{'='*60}")
        print("RESULTADO:")
        print(f"{'='*60}")
        
        if resultado.get('success'):
            print(f"✅ {resultado.get('message')}")
        else:
            print(f"❌ {resultado.get('message')}")
