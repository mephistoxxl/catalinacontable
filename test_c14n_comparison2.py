#!/usr/bin/env python
# -*- coding: utf-8 -*-
from lxml import etree

# XML autorizado de producción
with open('xml_autorizado_produccion.xml', 'rb') as f:
    xml_auth = f.read()

tree_auth = etree.fromstring(xml_auth)
sig_auth = tree_auth.xpath('//ds:SignedInfo', namespaces={'ds':'http://www.w3.org/2000/09/xmldsig#'})[0]
c14n_auth = etree.tostring(sig_auth, method='c14n', exclusive=False, with_comments=False)

print("="*80)
print("CANONICALIZACIÓN XML AUTORIZADO (SRI)")
print("="*80)
print(f"Longitud: {len(c14n_auth)} bytes")
print(f"\nPrimeros 300 bytes:")
print(c14n_auth[:300])
print(f"\nÚltimos 300 bytes:")
print(c14n_auth[-300:])

# El del error actual  
with open('xml_error39_ultimo.xml', 'rb') as f:
    xml_error = f.read()

tree_error = etree.fromstring(xml_error)
sig_error = tree_error.xpath('//ds:SignedInfo', namespaces={'ds':'http://www.w3.org/2000/09/xmldsig#'})[0]
c14n_error = etree.tostring(sig_error, method='c14n', exclusive=False, with_comments=False)

print("\n" + "="*80)
print("CANONICALIZACIÓN XML CON ERROR 39")
print("="*80)
print(f"Longitud: {len(c14n_error)} bytes")
print(f"\nPrimeros 300 bytes:")
print(c14n_error[:300])
print(f"\nÚltimos 300 bytes:")
print(c14n_error[-300:])

print("\n" + "="*80)
print("COMPARACIÓN")
print("="*80)
print(f"Longitudes iguales: {len(c14n_auth) == len(c14n_error)}")
print(f"C14N idénticos: {c14n_auth == c14n_error}")

if c14n_auth != c14n_error:
    print("\n¡DIFERENCIAS ENCONTRADAS!")
    
    # Si longitudes distintas
    if len(c14n_auth) != len(c14n_error):
        print(f"\nLongitudes diferentes:")
        print(f"  Autorizado: {len(c14n_auth)} bytes")
        print(f"  Error 39:   {len(c14n_error)} bytes")
        print(f"  Diferencia: {len(c14n_error) - len(c14n_auth)} bytes")
    
    # Buscar primer byte diferente
    min_len = min(len(c14n_auth), len(c14n_error))
    for i in range(min_len):
        if c14n_auth[i] != c14n_error[i]:
            print(f"\nPrimera diferencia en byte {i}:")
            print(f"  Autorizado: {chr(c14n_auth[i]) if 32 <= c14n_auth[i] < 127 else f'0x{c14n_auth[i]:02x}'} (byte {c14n_auth[i]})")
            print(f"  Error 39:   {chr(c14n_error[i]) if 32 <= c14n_error[i] < 127 else f'0x{c14n_error[i]:02x}'} (byte {c14n_error[i]})")
            print(f"\nContexto autorizado (bytes {max(0,i-80)}:{i+80}):")
            print(c14n_auth[max(0,i-80):i+80])
            print(f"\nContexto error (bytes {max(0,i-80)}:{i+80}):")
            print(c14n_error[max(0,i-80):i+80])
            break
    else:
        # No hay diferencias en los bytes comunes, uno es más largo
        print(f"\nPrimeros {min_len} bytes son idénticos.")
        if len(c14n_auth) > len(c14n_error):
            print(f"Autorizado tiene bytes extra: {c14n_auth[min_len:]}")
        else:
            print(f"Error tiene bytes extra: {c14n_error[min_len:]}")
