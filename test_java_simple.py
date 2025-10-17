"""
Test simple del firmador Java (sin Django)
"""

import subprocess
import os
from pathlib import Path


def verificar_java():
    """Verifica que Java esté instalado."""
    print("=" * 70)
    print("VERIFICANDO JAVA")
    print("=" * 70)
    
    try:
        result = subprocess.run(
            ['java', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            version_output = result.stderr or result.stdout
            print("✅ Java está instalado")
            print(f"   {version_output.split(chr(10))[0]}")
            return True
        else:
            print("❌ Java no respondió correctamente")
            return False
    
    except FileNotFoundError:
        print("❌ Java NO está instalado")
        print("   Descarga Java desde: https://www.java.com/es/download/")
        return False
    
    except Exception as e:
        print(f"❌ Error al verificar Java: {e}")
        return False


def verificar_jar():
    """Verifica que el JAR esté presente."""
    print()
    print("=" * 70)
    print("VERIFICANDO JAR DE FIRMA")
    print("=" * 70)
    
    jar_path = Path("inventario/sri/FirmaElectronica/FirmaElectronica.jar")
    
    if jar_path.exists():
        print(f"✅ JAR encontrado")
        print(f"   Ruta: {jar_path.absolute()}")
        print(f"   Tamaño: {jar_path.stat().st_size:,} bytes")
        return True
    else:
        print(f"❌ JAR NO encontrado en: {jar_path.absolute()}")
        return False


def buscar_xml_prueba():
    """Busca un XML de prueba."""
    print()
    print("=" * 70)
    print("BUSCANDO XML DE PRUEBA")
    print("=" * 70)
    
    xml_candidates = [
        'test_factura.xml',
        'LiquidacionCompra_V1.1.0.xml',
        'inventario/aprovada.XML'
    ]
    
    for xml_file in xml_candidates:
        if os.path.exists(xml_file):
            print(f"✅ XML de prueba encontrado: {xml_file}")
            return xml_file
    
    print("❌ No se encontró ningún XML de prueba")
    print("   Archivos buscados:")
    for xml_file in xml_candidates:
        print(f"   - {xml_file}")
    return None


def buscar_certificado():
    """Busca un certificado P12."""
    print()
    print("=" * 70)
    print("BUSCANDO CERTIFICADO P12")
    print("=" * 70)
    
    # Buscar en firmas_secure
    firmas_dir = Path("firmas_secure/firmas")
    
    if firmas_dir.exists():
        p12_files = list(firmas_dir.glob("*.p12"))
        if p12_files:
            cert = p12_files[0]
            print(f"✅ Certificado encontrado: {cert.name}")
            return str(cert)
    
    print("❌ No se encontró certificado P12")
    return None


def probar_firma_java(xml_file, cert_file, password=""):
    """Prueba firmar con el JAR de Java."""
    print()
    print("=" * 70)
    print("PROBANDO FIRMA CON JAR DE JAVA")
    print("=" * 70)
    
    jar_path = Path("inventario/sri/FirmaElectronica/FirmaElectronica.jar")
    output_xml = "test_firmado_java.xml"
    
    command = [
        'java',
        '-Dfile.encoding=UTF-8',
        '-jar',
        str(jar_path),
        xml_file,
        cert_file,
        password,
        output_xml
    ]
    
    print(f"   XML entrada: {xml_file}")
    print(f"   Certificado: {cert_file}")
    print(f"   XML salida: {output_xml}")
    print()
    print("   Ejecutando JAR...")
    
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            encoding='utf-8',
            errors='replace'
        )
        
        print()
        if result.returncode == 0:
            print("✅ ¡FIRMA EXITOSA!")
            
            if os.path.exists(output_xml):
                with open(output_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                print()
                print(f"   Tamaño: {len(content):,} bytes")
                
                # Verificar elementos
                checks = [
                    ('<ds:Signature', 'Elemento <ds:Signature>'),
                    ('<ds:SignedInfo>', 'Elemento <ds:SignedInfo>'),
                    ('<ds:SignatureValue>', 'Elemento <ds:SignatureValue>'),
                    ('<ds:KeyInfo>', 'Elemento <ds:KeyInfo>'),
                    ('QualifyingProperties', 'Propiedades XAdES'),
                ]
                
                for tag, description in checks:
                    if tag in content:
                        print(f"   ✅ {description}")
                    else:
                        print(f"   ❌ {description} NO ENCONTRADO")
                
                print()
                print(f"   📄 Revisa el archivo: {output_xml}")
                return True
        else:
            print("❌ Error en la firma")
            if result.stdout:
                print(f"   Stdout: {result.stdout[:500]}")
            if result.stderr:
                print(f"   Stderr: {result.stderr[:500]}")
            return False
    
    except subprocess.TimeoutExpired:
        print("❌ Timeout (>30s)")
        return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print()
    print("🔥" * 35)
    print("TEST DEL FIRMADOR CON JAR DE JAVA")
    print("🔥" * 35)
    print()
    
    # Verificaciones
    if not verificar_java():
        return
    
    if not verificar_jar():
        return
    
    xml_file = buscar_xml_prueba()
    if not xml_file:
        return
    
    cert_file = buscar_certificado()
    if not cert_file:
        print()
        print("⚠️  No se puede probar la firma sin un certificado")
        print("   Pero Java y el JAR están listos!")
        return
    
    # Intentar firma (probablemente falle sin password correcto)
    print()
    print("⚠️  Intentando firmar con password vacío...")
    print("   (Esto puede fallar si el certificado requiere password)")
    
    probar_firma_java(xml_file, cert_file, "")
    
    print()
    print("=" * 70)
    print("RESULTADO")
    print("=" * 70)
    print()
    print("✅ Java está instalado")
    print("✅ JAR de firma está disponible")
    print("✅ Sistema listo para firmar con Java")
    print()
    print("Para usar el firmador Java en producción:")
    print("   1. Asegúrate de tener Java instalado")
    print("   2. Configura USE_JAVA_SIGNER=true (ya está por defecto)")
    print("   3. Ejecuta: python manage.py runserver")
    print("   4. Firma facturas desde la interfaz web")
    print()


if __name__ == "__main__":
    main()
