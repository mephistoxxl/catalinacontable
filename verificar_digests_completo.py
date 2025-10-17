from lxml import etree
import hashlib
import base64

# Cargar el XML firmado
xml_path = r"media\facturas\2390054060001\xml\factura_001-999-000000016_20251017_161628_firmado.xml"

with open(xml_path, 'rb') as f:
    doc = etree.parse(f)

root = doc.getroot()
ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#', 'xades': 'http://uri.etsi.org/01903/v1.3.2#'}

print("=" * 80)
print("VERIFICACIÓN COMPLETA DE DIGESTS - FACTURA 016 (con KeyValue)")
print("=" * 80)

# 1. Obtener todas las referencias
signed_info = root.find('.//ds:SignedInfo', ns)
references = signed_info.findall('.//ds:Reference', ns)

print(f"\n📋 Total referencias encontradas: {len(references)}\n")

for idx, ref in enumerate(references, 1):
    uri = ref.get('URI')
    ref_type = ref.get('Type', 'No type')
    digest_value_elem = ref.find('ds:DigestValue', ns)
    digest_in_xml = digest_value_elem.text.strip() if digest_value_elem is not None else 'N/A'
    
    print(f"\n{'='*60}")
    print(f"📌 REFERENCIA {idx}:")
    print(f"   URI: {uri}")
    print(f"   Type: {ref_type}")
    print(f"   Digest en XML: {digest_in_xml}")
    
    # Calcular digest real
    try:
        if uri == '#comprobante':
            # Referencia al elemento raíz <factura>
            factura = root
            # Aplicar enveloped-signature transform (eliminar firma)
            factura_sin_firma = etree.fromstring(etree.tostring(factura))
            signature = factura_sin_firma.find('.//ds:Signature', ns)
            if signature is not None:
                signature.getparent().remove(signature)
            # Canonicalizar
            c14n_bytes = etree.tostring(factura_sin_firma, method='c14n', exclusive=False, with_comments=False)
            digest_calculado = base64.b64encode(hashlib.sha1(c14n_bytes).digest()).decode()
            
            print(f"   🔍 Tipo: Documento (factura)")
            print(f"   ✅ Digest calculado: {digest_calculado}")
            print(f"   📏 Longitud C14N: {len(c14n_bytes)} bytes")
            
        elif uri.startswith('#') and 'KeyInfo' not in uri:
            # SignedProperties u otro elemento con ID
            element_id = uri[1:]  # Quitar el #
            elemento = root.find(f".//*[@Id='{element_id}']")
            
            if elemento is None:
                print(f"   ❌ ERROR: No se encontró elemento con Id='{element_id}'")
                continue
                
            # Canonicalizar sin transforms
            c14n_bytes = etree.tostring(elemento, method='c14n', exclusive=False, with_comments=False)
            digest_calculado = base64.b64encode(hashlib.sha1(c14n_bytes).digest()).decode()
            
            print(f"   🔍 Tipo: {elemento.tag}")
            print(f"   ✅ Digest calculado: {digest_calculado}")
            print(f"   📏 Longitud C14N: {len(c14n_bytes)} bytes")
            
        else:
            # KeyInfo
            element_id = uri[1:] if uri.startswith('#') else None
            if element_id:
                key_info = root.find(f".//ds:KeyInfo[@Id='{element_id}']", ns)
                
                if key_info is None:
                    print(f"   ❌ ERROR: No se encontró KeyInfo con Id='{element_id}'")
                    continue
                    
                # Canonicalizar
                c14n_bytes = etree.tostring(key_info, method='c14n', exclusive=False, with_comments=False)
                digest_calculado = base64.b64encode(hashlib.sha1(c14n_bytes).digest()).decode()
                
                print(f"   🔍 Tipo: KeyInfo")
                print(f"   ✅ Digest calculado: {digest_calculado}")
                print(f"   📏 Longitud C14N: {len(c14n_bytes)} bytes")
        
        # Comparar
        if digest_calculado == digest_in_xml:
            print(f"   ✅✅✅ CORRECTO ✅✅✅")
        else:
            print(f"   ❌❌❌ INCORRECTO ❌❌❌")
            print(f"   Expected: {digest_in_xml}")
            print(f"   Got:      {digest_calculado}")
            
    except Exception as e:
        print(f"   ❌ ERROR al calcular: {str(e)}")

print(f"\n{'='*80}")
print("FIN DE VERIFICACIÓN")
print("=" * 80)
