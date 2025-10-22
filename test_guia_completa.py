"""
Script de prueba para verificar la guía de remisión completa
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import GuiaRemision, Empresa, Opciones, DestinatarioGuia, DetalleDestinatarioGuia
from inventario.guia_remision.xml_generator_guia import XMLGeneratorGuiaRemision
from datetime import date
from decimal import Decimal

def test_xml_completo():
    """Prueba generación de XML completo con todos los elementos"""
    
    print("=" * 80)
    print("PRUEBA DE GENERACIÓN DE XML GUÍA DE REMISIÓN V1.1.0 - COMPLETO")
    print("=" * 80)
    
    # Obtener empresa
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresas en el sistema")
        return
    
    print(f"✅ Empresa: {empresa.razon_social}")
    
    # Variable para saber si se creó opciones temporal
    opciones_temporal = False
    
    # Obtener opciones (intentar primero por empresa, luego por RUC)
    opciones = Opciones.objects.filter(empresa=empresa).first()
    
    if not opciones:
        print("⚠️ No hay opciones por empresa, buscando por RUC...")
        # Intentar buscar por RUC usando all_objects (sin filtro de tenant)
        ruc_empresa = empresa.ruc if hasattr(empresa, 'ruc') else '9999999999001'
        opciones = Opciones.all_objects.filter(identificacion=ruc_empresa).first()
        
        if opciones:
            print(f"✅ Opciones encontradas por RUC: {opciones.razon_social}")
        else:
            print("⚠️ No hay opciones, creando temporales para prueba")
            # Usar un RUC único para la prueba
            opciones_temporal = True
            opciones = Opciones.objects.create(
                empresa=empresa,
                identificacion='9999999999099',  # RUC temporal único
                razon_social=empresa.razon_social,
                nombre_comercial=getattr(empresa, 'nombre_negocio', 'EMPRESA PRUEBA'),
                direccion_establecimiento=getattr(empresa, 'direccion_matriz', 'AV. PRINCIPAL 123'),
                correo='test@empresa.com',
                telefono='0987654321',
                obligado='NO',
                tipo_ambiente='1',
                tipo_emision='1'
            )
            print(f"✅ Opciones temporales creadas")
    
    print(f"✅ Opciones: RUC {opciones.ruc if hasattr(opciones, 'ruc') else 'default'}")
    
    # Limpiar guías anteriores de prueba
    GuiaRemision.objects.filter(
        empresa=empresa,
        establecimiento='001',
        punto_emision='999',
        secuencial='000000001'
    ).delete()
    print("🧹 Guías de prueba anteriores eliminadas")
    
    # Crear guía de prueba
    guia = GuiaRemision.objects.create(
        empresa=empresa,
        establecimiento='001',
        punto_emision='999',
        secuencial='000000001',
        transportista_ruc='1717328168',
        transportista_nombre='JUAN PEREZ TRANSPORTES',
        tipo_identificacion_transportista='05',
        direccion_partida='AV. AMAZONAS Y RIO COCA, QUITO',
        direccion_destino='AV. OCCIDENTAL Y CALLE 10, QUITO',
        dir_establecimiento='AV. QUITO MATRIZ, QUITO',
        fecha_inicio_traslado=date.today(),
        fecha_fin_traslado=date.today(),
        placa='PXA-1234',
        rise='',
        obligado_contabilidad='NO',
        contribuyente_especial='',
        correo_envio='test@ejemplo.com',
        informacion_adicional='Guía de prueba generada automáticamente',
        ruta='Quito - Norte - Sur',
        usuario_creacion=None
    )
    
    print(f"✅ Guía creada: {guia.numero_completo}")
    
    # Generar clave de acceso
    xml_gen = XMLGeneratorGuiaRemision(guia, empresa, opciones)
    guia.clave_acceso = xml_gen.generar_clave_acceso()
    guia.save()
    
    print(f"✅ Clave de acceso: {guia.clave_acceso}")
    
    # Crear destinatario
    destinatario = DestinatarioGuia.objects.create(
        guia=guia,
        identificacion_destinatario='1790000000001',
        razon_social_destinatario='EMPRESA DESTINO S.A.',
        dir_destinatario='AV. OCCIDENTAL 123, QUITO',
        motivo_traslado='01',
        doc_aduanero_unico='',
        cod_estab_destino='001',
        ruta='Ruta Norte'
    )
    
    print(f"✅ Destinatario creado: {destinatario.razon_social_destinatario}")
    
    # Crear productos del destinatario
    productos = [
        {
            'codigo': 'PROD001',
            'descripcion': 'PRODUCTO DE PRUEBA 1',
            'cantidad': Decimal('10.500000')
        },
        {
            'codigo': 'PROD002',
            'descripcion': 'PRODUCTO DE PRUEBA 2',
            'cantidad': Decimal('25.250000')
        },
        {
            'codigo': 'SERV001',
            'descripcion': 'SERVICIO DE TRANSPORTE',
            'cantidad': Decimal('1.000000')
        }
    ]
    
    for prod in productos:
        DetalleDestinatarioGuia.objects.create(
            destinatario=destinatario,
            codigo_interno=prod['codigo'],
            descripcion=prod['descripcion'],
            cantidad=prod['cantidad']
        )
        print(f"  ✅ Producto: {prod['codigo']} - {prod['descripcion']} x {prod['cantidad']}")
    
    # Generar XML
    print("\n" + "=" * 80)
    print("GENERANDO XML...")
    print("=" * 80)
    
    xml_string = xml_gen.generar_xml()
    
    # Guardar XML en archivo
    filename = f'guia_test_{guia.numero_completo.replace("-", "_")}.xml'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(xml_string)
    
    print(f"\n✅ XML generado exitosamente: {filename}")
    print(f"   Tamaño: {len(xml_string)} bytes")
    
    # Mostrar primeras líneas del XML
    print("\n" + "=" * 80)
    print("PRIMERAS LÍNEAS DEL XML:")
    print("=" * 80)
    lines = xml_string.split('\n')
    for line in lines[:30]:
        print(line)
    
    # Verificar elementos críticos
    print("\n" + "=" * 80)
    print("VERIFICACIÓN DE ELEMENTOS CRÍTICOS:")
    print("=" * 80)
    
    checks = {
        '<guiaRemision': 'Elemento raíz guiaRemision',
        'version="1.1.0"': 'Versión 1.1.0',
        'id="comprobante"': 'ID comprobante',
        '<infoTributaria>': 'Información tributaria',
        '<codDoc>06</codDoc>': 'Código documento 06',
        '<infoGuiaRemision>': 'Información guía remisión',
        '<tipoIdentificacionTransportista>': 'Tipo ID transportista (CRÍTICO)',
        '<destinatarios>': 'Destinatarios',
        '<destinatario>': 'Destinatario',
        '<detalles>': 'Detalles (productos)',
        '<detalle>': 'Detalle individual',
        '<infoAdicional>': 'Información adicional'
    }
    
    for key, desc in checks.items():
        if key in xml_string:
            print(f"✅ {desc}: OK")
        else:
            print(f"❌ {desc}: FALTA")
    
    print("\n" + "=" * 80)
    print("LIMPIANDO DATOS DE PRUEBA...")
    print("=" * 80)
    
    # Limpiar
    guia.delete()
    print("✅ Guía eliminada")
    
    # Limpiar opciones temporales si se crearon
    if opciones_temporal and opciones:
        opciones.delete()
        print("✅ Opciones temporales eliminadas")
    
    print("\n" + "=" * 80)
    print("PRUEBA COMPLETADA EXITOSAMENTE ✅")
    print("=" * 80)

if __name__ == '__main__':
    test_xml_completo()
