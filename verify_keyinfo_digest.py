from lxml import etree
import hashlib, base64

xml_path = r'C:\Users\CORE I7\Desktop\catalinafact\media\facturas\2390054060001\xml\factura_001-999-000000014_20251017_151233_firmado.xml'

tree = etree.parse(xml_path)
root = tree.getroot()
ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}

# Encontrar KeyInfo
ki = root.find('.//ds:KeyInfo', ns)
ki_id = ki.get('Id')

print("Verificando digest del KeyInfo...")
print(f"KeyInfo Id: {ki_id}")

# Calc digest del KeyInfo
ki_c14n = etree.tostring(ki, method='c14n', exclusive=False, with_comments=False)
digest_calc = base64.b64encode(hashlib.sha1(ki_c14n).digest()).decode()

# Buscar digest en SignedInfo
print(f"\nBuscando referencia con URI='#{ki_id}'...")

all_refs = root.findall('.//ds:Reference', ns)
print(f"\nTotal referencias: {len(all_refs)}")

for i, ref in enumerate(all_refs, 1):
    uri = ref.get('URI', '')
    ref_type = ref.get('Type', '')
    digest = ref.find('.//ds:DigestValue', ns)
    digest_val = digest.text if digest is not None else 'N/A'
    print(f"{i}. URI='{uri}', Type='{ref_type}', Digest={digest_val}")
    
    if uri == f'#{ki_id}':
        print(f"   ✅ MATCH - Esta es la referencia al KeyInfo")
        ki_c14n = etree.tostring(ki, method='c14n', exclusive=False, with_comments=False)
        digest_calc = base64.b64encode(hashlib.sha1(ki_c14n).digest()).decode()
        print(f"   Digest calculado: {digest_calc}")
        print(f"   Digest en XML:     {digest_val}")
        print(f"   Match: {digest_calc == digest_val}")
