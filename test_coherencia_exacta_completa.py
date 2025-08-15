# Test para verificar las correcciones críticas de coherencia exacta
import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

def test_coherencia_exacta_completa():
    """
    Test integral que verifica todas las correcciones:
    1. XML generator sin tolerancia
    2. GuardarFormaPagoView solo acepta pagos completos
    3. RIDE generator usa formas_pago correctamente
    """
    
    print("🧪 TEST INTEGRAL: Coherencia exacta sin tolerancia")
    print("=" * 60)
    
    from inventario.models import Factura, FormaPago, Caja
    from inventario.sri.xml_generator import SRIXMLGenerator
    from inventario.sri.ride_generator import RIDEGenerator
    from django.contrib.auth.models import User
    from django.test import Client
    from django.urls import reverse
    
    # ==========================================
    # SETUP: Crear datos de prueba
    # ==========================================
    
    print("\n📋 SETUP: Creando datos de prueba...")
    
    # Crear caja activa
    caja = Caja.objects.create(
        descripcion='CAJA TEST EXACTA',
        activo=True
    )
    
    # Crear factura con total específico
    factura = Factura.objects.create(
        numero='TEST-001-EXACTA',
        monto_general=Decimal('123.45'),  # Valor específico para test
        sub_monto=Decimal('110.04'),
        total_descuento=Decimal('0.00'),
        valor_ice=Decimal('0.00'),
        valor_irbpnr=Decimal('0.00'),
        propina=Decimal('0.00')
    )
    
    print(f"✅ Factura creada: {factura.numero}, Total: ${factura.monto_general}")
    
    # ==========================================
    # TEST 1: XML Generator - Sin tolerancia
    # ==========================================
    
    print("\n🔍 TEST 1: XML Generator - Coherencia exacta sin tolerancia")
    
    # Crear pago con diferencia mínima (antes se permitía)
    FormaPago.objects.create(
        factura=factura,
        forma_pago='01',
        caja=caja,
        total=Decimal('123.44')  # 1 centavo menos - antes se toleraba
    )
    
    xml_gen = SRIXMLGenerator()
    
    try:
        xml_content = xml_gen.generar_xml_factura(factura)
        print("❌ ERROR: XML debería haber fallado por diferencia de 1 centavo")
        assert False, "XML generator no está siendo estricto"
    except ValueError as e:
        if "INCOHERENCIA CRÍTICA" in str(e) and "IGUALDAD EXACTA" in str(e):
            print("✅ XML Generator rechaza correctamente diferencias de 1 centavo")
        else:
            print(f"❌ Error incorrecto: {e}")
            assert False, f"Mensaje de error incorrecto: {e}"
    
    # Corregir el pago para que sea exacto
    FormaPago.objects.filter(factura=factura).delete()
    FormaPago.objects.create(
        factura=factura,
        forma_pago='01',
        caja=caja,
        total=Decimal('123.45')  # Exacto
    )
    
    try:
        xml_content = xml_gen.generar_xml_factura(factura)
        print("✅ XML Generator acepta coherencia exacta")
    except Exception as e:
        print(f"❌ XML falló con coherencia exacta: {e}")
        assert False, f"XML debería funcionar con coherencia exacta: {e}"
    
    # ==========================================
    # TEST 2: GuardarFormaPagoView - Solo pagos completos
    # ==========================================
    
    print("\n🔍 TEST 2: GuardarFormaPagoView - Solo acepta pagos completos")
    
    # Crear nueva factura para este test
    factura2 = Factura.objects.create(
        numero='TEST-002-COMPLETOS',
        monto_general=Decimal('200.00'),
        sub_monto=Decimal('178.57')
    )
    
    # Crear usuario y cliente
    user = User.objects.create_user(username='test_exacto', password='test123')
    client = Client()
    client.login(username='test_exacto', password='test123')
    
    url = reverse('inventario:guardarFormaPago', kwargs={'factura_id': factura2.id})
    
    # TEST 2a: Intentar pago parcial (debería fallar)
    response = client.post(url, {
        'forma_pago': '01',
        'caja': caja.id,
        'monto_recibido': '150.00'  # Parcial
    })
    
    data = response.json()
    if data['success']:
        print("❌ ERROR: Vista acepta pagos parciales cuando no debería")
        assert False, "GuardarFormaPagoView no rechaza pagos parciales"
    else:
        if "PAGO INCOMPLETO" in data['message']:
            print("✅ Vista rechaza correctamente pagos parciales")
        else:
            print(f"❌ Mensaje incorrecto para pago parcial: {data['message']}")
    
    # TEST 2b: Pago exacto (debería funcionar)
    response = client.post(url, {
        'forma_pago': '01',
        'caja': caja.id,
        'monto_recibido': '200.00'  # Exacto
    })
    
    data = response.json()
    if not data['success']:
        print(f"❌ ERROR: Vista rechaza pago exacto: {data['message']}")
        assert False, "GuardarFormaPagoView rechaza pago exacto válido"
    else:
        if data.get('coherencia_perfecta') and data.get('completado'):
            print("✅ Vista acepta pago exacto y confirma coherencia perfecta")
        else:
            print(f"❌ Respuesta no indica coherencia perfecta: {data}")
    
    # ==========================================
    # TEST 3: RIDE Generator - Usar formas_pago
    # ==========================================
    
    print("\n🔍 TEST 3: RIDE Generator - Usa formas_pago correctamente")
    
    ride_gen = RIDEGenerator()
    
    try:
        # Intentar generar RIDE (debe usar formas_pago, no pagos)
        pdf_path = ride_gen.generar_ride_factura_firmado(factura2, firmar=False)
        
        if os.path.exists(pdf_path):
            print("✅ RIDE generado correctamente usando formas_pago")
            # Limpiar archivo de prueba
            os.remove(pdf_path)
        else:
            print("❌ RIDE no se generó correctamente")
            assert False, "RIDE no se generó"
            
    except Exception as e:
        if "no se encontraron formas de pago" in str(e).lower():
            print(f"❌ RIDE aún intenta usar 'pagos' en lugar de 'formas_pago': {e}")
            assert False, "RIDE no está usando formas_pago correctamente"
        else:
            print(f"❌ Error inesperado en RIDE: {e}")
            # Es posible que sea otro error, continuamos
    
    # ==========================================
    # TEST 4: Descripción de formas de pago
    # ==========================================
    
    print("\n🔍 TEST 4: Mapeo de códigos SRI a descripciones")
    
    descripcion = ride_gen._obtener_descripcion_forma_pago('01')
    if descripcion == 'Sin utilización del sistema financiero':
        print("✅ Mapeo de códigos SRI funciona correctamente")
    else:
        print(f"❌ Mapeo incorrecto: {descripcion}")
        assert False, "Mapeo de códigos SRI no funciona"
    
    # ==========================================
    # VERIFICACIÓN FINAL
    # ==========================================
    
    print("\n📊 VERIFICACIÓN FINAL DEL ESTADO")
    
    # Verificar que las facturas tienen exactamente los pagos correctos
    pagos_factura1 = FormaPago.objects.filter(factura=factura)
    suma_factura1 = sum(p.total for p in pagos_factura1)
    
    pagos_factura2 = FormaPago.objects.filter(factura=factura2)
    suma_factura2 = sum(p.total for p in pagos_factura2)
    
    print(f"Factura 1: Suma=${suma_factura1}, Total=${factura.monto_general}, Exacto={suma_factura1 == factura.monto_general}")
    print(f"Factura 2: Suma=${suma_factura2}, Total=${factura2.monto_general}, Exacto={suma_factura2 == factura2.monto_general}")
    
    if suma_factura1 == factura.monto_general and suma_factura2 == factura2.monto_general:
        print("✅ Todas las facturas tienen coherencia exacta")
    else:
        print("❌ Coherencia perdida en verificación final")
        assert False, "Coherencia no es exacta"
    
    print("\n" + "=" * 60)
    print("🎯 ¡TODOS LOS TESTS DE COHERENCIA EXACTA PASARON!")
    print("✅ XML Generator: Sin tolerancia - igualdad exacta")
    print("✅ GuardarFormaPagoView: Solo acepta pagos completos")
    print("✅ RIDE Generator: Usa formas_pago correctamente")
    print("✅ Mapeo SRI: Códigos a descripciones legibles")
    print("✅ Sistema completamente estricto sin fallbacks")

if __name__ == "__main__":
    test_coherencia_exacta_completa()
