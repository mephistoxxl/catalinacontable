# ANÁLISIS DEL ERROR 39 PERSISTENTE

## 🔍 XML Recibido por el SRI (de los logs):

```xml
<ds:SignedInfo>
  <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
  <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
  
  <ds:Reference Id="Reference1_..." URI="#comprobante">
    <ds:Transforms>
      <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
    </ds:Transforms>
    <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
    <ds:DigestValue>9/ybwkeZTAP2jDvycv0+pvEnb98=</ds:DigestValue>
  </ds:Reference>
  
  <ds:Reference URI="#id5a0172ff87f34402a2241d78a00794a0_73">
    <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
    <ds:DigestValue>GMi14xbgOITLuQXDQ7o61tlUPHE=</ds:DigestValue>
  </ds:Reference>
  
  <ds:Reference Id="SignedProperties-Reference_..." Type="http://uri.etsi.org/01903#SignedProperties" URI="#idad432fa82b1449beb9c6ba0fb0d14e75_19">
    <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
    <ds:DigestValue>+4XN7JnSav6dDUqhVexfwX4hBSU=</ds:DigestValue>
  </ds:Reference>
</ds:SignedInfo>
```

✅ **Estructura CORRECTA**:
- Inclusive C14N
- 3 referencias (factura, KeyInfo, SignedProperties)
- Solo enveloped-signature en factura
- Sin transforms en SignedProperties

## ⚠️ PROBLEMA DETECTADO:

En los datos del XML hay caracteres corruptos:
```
<campoAdicional nombre="TELÉFONO">  ← Correcto en el firmado
<campoAdicional nombre="TELÃ‰FONO">  ← Corrupto en respuesta SRI
```

**PERO** esto es solo en la respuesta del SRI (recodificación). El XML original debe estar bien.

## 🔍 POSIBLES CAUSAS DEL ERROR 39:

1. **Digest del KeyInfo incorrecto**: 
   - Estamos calculando digest del KeyInfo DESPUÉS de crearlo
   - Pero el SRI podría estar calculándolo de forma diferente
   - En facturas autorizadas, el KeyInfo tiene Id pero la referencia podría calcularse diferente

2. **Orden de las referencias**:
   - Factura AUTORIZADA: factura → KeyInfo → SignedProperties
   - Nuestra implementación: factura → KeyInfo → SignedProperties ✅ (correcto)

3. **Canonicalización del KeyInfo**:
   - Podríamos estar canonicalizando incorrectamente el KeyInfo
   - Necesitamos verificar byte por byte

4. **El certificado en sí**:
   - El certificado de ANDREA MERCEDES MICHELENA PUMALPA (1750848333)
   - ¿Es el mismo que usó la factura AUTORIZADA?
   - La autorizada usa el mismo certificado (serial: 981015562)

## 🎯 ACCIÓN INMEDIATA:

Necesito verificar cómo se calcula el digest del KeyInfo en facturas autorizadas vs nuestro código.

**Hipótesis**: El problema está en que calculamos el digest del KeyInfo COMPLETO, pero tal vez el SRI espera solo el digest del CERTIFICADO (X509Certificate) no del KeyInfo entero.
