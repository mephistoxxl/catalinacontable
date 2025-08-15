# Test para validar coherencia acumulada en GuardarFormaPagoView
import os
import sys
import django
from decimal import Decimal
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from inventario.models import Factura, FormaPago, Caja

def test_guardar_forma_pago_coherencia():
    """Test que verifica que GuardarFormaPagoView valida coherencia acumulada"""
    
    print("🧪 Iniciando test de coherencia acumulada en GuardarFormaPagoView")
    
    # Crear usuario de prueba
    user = User.objects.create_user(username='test', password='test123')
    
    # Crear caja activa
    caja = Caja.objects.create(
        descripcion='CAJA TEST',
        activo=True
    )
    
    # Crear factura de prueba
    factura = Factura.objects.create(
        numero='001',
        monto_general=Decimal('100.00'),
        sub_monto=Decimal('89.29'),
        # ... otros campos necesarios
    )
    
    print(f"✅ Factura creada: ID={factura.id}, Total=${factura.monto_general}")
    
    # Configurar cliente con sesión
    client = Client()
    client.login(username='test', password='test123')
    
    # URL de la vista
    url = reverse('inventario:guardarFormaPago', kwargs={'factura_id': factura.id})
    
    # TEST 1: Crear primer pago válido (50% del total)
    print("\n📋 TEST 1: Primer pago válido ($50.00 de $100.00)")
    
    response = client.post(url, {
        'forma_pago': '01',  # Sin utilización del sistema financiero
        'caja': caja.id,
        'monto_recibido': '50.00'
    })
    
    data = response.json()
    print(f"Response: {data}")
    
    assert data['success'] == True, "Primer pago debería ser exitoso"
    assert 'Faltan $50.00' in data['message'], "Debería indicar faltante"
    print("✅ Primer pago creado correctamente")
    
    # TEST 2: Crear segundo pago que complete exactamente
    print("\n📋 TEST 2: Segundo pago que completa exactamente ($50.00)")
    
    response = client.post(url, {
        'forma_pago': '01',
        'caja': caja.id,
        'monto_recibido': '50.00'
    })
    
    data = response.json()
    print(f"Response: {data}")
    
    assert data['success'] == True, "Segundo pago debería ser exitoso"
    assert 'completamente pagada' in data['message'], "Debería indicar completado"
    assert data['completado'] == True, "Flag completado debería ser True"
    print("✅ Segundo pago completó correctamente")
    
    # TEST 3: Intentar agregar pago que exceda (debería fallar)
    print("\n📋 TEST 3: Intento de pago que excede total (debería fallar)")
    
    response = client.post(url, {
        'forma_pago': '01',
        'caja': caja.id,
        'monto_recibido': '10.00'  # Esto excedería el total
    })
    
    data = response.json()
    print(f"Response: {data}")
    
    assert data['success'] == False, "Pago que excede debería fallar"
    assert 'SUMA EXCEDE TOTAL' in data['message'], "Debería indicar exceso"
    print("✅ Exceso rechazado correctamente")
    
    # TEST 4: Validar códigos SRI inválidos
    print("\n📋 TEST 4: Código SRI inválido (debería fallar)")
    
    # Crear nueva factura para este test
    factura2 = Factura.objects.create(
        numero='002',
        monto_general=Decimal('50.00'),
        sub_monto=Decimal('44.64')
    )
    
    url2 = reverse('inventario:guardarFormaPago', kwargs={'factura_id': factura2.id})
    
    response = client.post(url2, {
        'forma_pago': '99',  # Código inválido
        'caja': caja.id,
        'monto_recibido': '50.00'
    })
    
    data = response.json()
    print(f"Response: {data}")
    
    assert data['success'] == False, "Código inválido debería fallar"
    assert 'no válido' in data['message'], "Debería indicar código inválido"
    print("✅ Código SRI inválido rechazado correctamente")
    
    # TEST 5: Caja inactiva (debería fallar)
    print("\n📋 TEST 5: Caja inactiva (debería fallar)")
    
    caja_inactiva = Caja.objects.create(
        descripcion='CAJA INACTIVA',
        activo=False
    )
    
    response = client.post(url2, {
        'forma_pago': '01',
        'caja': caja_inactiva.id,
        'monto_recibido': '50.00'
    })
    
    data = response.json()
    print(f"Response: {data}")
    
    assert data['success'] == False, "Caja inactiva debería fallar"
    assert 'inactiva' in data['message'], "Debería indicar caja inactiva"
    print("✅ Caja inactiva rechazada correctamente")
    
    # Verificar estado final de la base de datos
    print("\n📊 Verificación final de base de datos:")
    
    pagos_factura1 = FormaPago.objects.filter(factura=factura)
    suma_factura1 = sum(p.total for p in pagos_factura1)
    print(f"Factura 1: {pagos_factura1.count()} pagos, Suma: ${suma_factura1}, Total: ${factura.monto_general}")
    
    pagos_factura2 = FormaPago.objects.filter(factura=factura2)
    suma_factura2 = sum(p.total for p in pagos_factura2)
    print(f"Factura 2: {pagos_factura2.count()} pagos, Suma: ${suma_factura2}, Total: ${factura2.monto_general}")
    
    assert suma_factura1 == factura.monto_general, "Factura 1 debería estar completamente pagada"
    assert suma_factura2 == 0, "Factura 2 no debería tener pagos válidos"
    
    print("\n🎯 ¡TODOS LOS TESTS PASARON!")
    print("✅ GuardarFormaPagoView ahora valida coherencia acumulada correctamente")
    print("✅ Rechaza excesos, códigos inválidos y cajas inactivas")
    print("✅ Proporciona información clara sobre el estado de pagos")

if __name__ == "__main__":
    test_guardar_forma_pago_coherencia()
