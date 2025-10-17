# ANÁLISIS: FACTURA AUTORIZADA vs NUESTRA IMPLEMENTACIÓN

## 📊 FACTURA AUTORIZADA POR EL SRI (Ambiente Producción - misma empresa)

### CanonicalizationMethod:
```xml
<ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315" />
```
❌ **USA INCLUSIVE C14N** (la que teníamos antes)

### Transform en Reference de Factura:
```xml
<ds:Reference Id="Reference-ID-583374" URI="#comprobante">
  <ds:Transforms>
    <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature" />
  </ds:Transforms>
  <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1" />
  <ds:DigestValue>mWHVE6kTcsfVTVc/D8eXavpOoFA=</ds:DigestValue>
</ds:Reference>
```
✅ **USA SOLO ENVELOPED-SIGNATURE** (no usa Exclusive C14N como segundo transform)

### Reference a SignedProperties:
```xml
<ds:Reference Id="SignedPropertiesID147900" Type="http://uri.etsi.org/01903#SignedProperties" URI="#Signature367875-SignedProperties283262">
  <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1" />
  <ds:DigestValue>9K5d68Jabi2hCNE9xpPgaoF1F2o=</ds:DigestValue>
</ds:Reference>
```
❌ **NO TIENE TRANSFORMS** (nuestra implementación nueva tiene Exclusive C14N)

### Reference adicional al certificado:
```xml
<ds:Reference URI="#Certificate708726">
  <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1" />
  <ds:DigestValue>d7wC39w7vy+bzY3EpCp1doRfqAU=</ds:DigestValue>
</ds:Reference>
```
⚠️ **TIENE 3 REFERENCIAS** (nosotros solo tenemos 2: factura + SignedProperties)

### KeyInfo:
```xml
<ds:KeyInfo Id="Certificate708726">
  <ds:X509Data>
    <ds:X509Certificate>MIIMMTCCChmg...</ds:X509Certificate>
  </ds:X509Data>
  <ds:KeyValue>
    <ds:RSAKeyValue>
      <ds:Modulus>taEHdHAm...</ds:Modulus>
      <ds:Exponent>AQAB</ds:Exponent>
    </ds:RSAKeyValue>
  </ds:KeyValue>
</ds:KeyInfo>
```
✅ **Tiene Id en KeyInfo** (nosotros también)
✅ **Incluye RSAKeyValue** (nosotros NO lo incluimos - podría no ser necesario)

---

## 🔍 NUESTRA IMPLEMENTACIÓN ACTUAL (después de los cambios)

### CanonicalizationMethod:
```xml
<ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
```
❌ **USAMOS EXCLUSIVE C14N** (INCORRECTO - debería ser Inclusive)

### Transform en Reference de Factura:
```xml
<ds:Reference Id="Reference1_..." URI="#comprobante">
  <ds:Transforms>
    <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
    <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
  </ds:Transforms>
  <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
  <ds:DigestValue>...</ds:DigestValue>
</ds:Reference>
```
❌ **TENEMOS 2 TRANSFORMS** (solo debería ser enveloped-signature)

### Reference a SignedProperties:
```xml
<ds:Reference Id="..." Type="http://uri.etsi.org/01903#SignedProperties" URI="#...">
  <ds:Transforms>
    <ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
  </ds:Transforms>
  <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
  <ds:DigestValue>...</ds:DigestValue>
</ds:Reference>
```
❌ **TENEMOS TRANSFORM** (no debería tener ninguno)

### Referencias:
❌ **SOLO TENEMOS 2 REFERENCIAS** (la autorizada tiene 3: factura, KeyInfo, SignedProperties)

---

## 📋 CONCLUSIÓN - CAMBIOS NECESARIOS:

1. ✅ **REVERTIR a Inclusive C14N**: `http://www.w3.org/TR/2001/REC-xml-c14n-20010315`
   
2. ✅ **Reference 1 (factura)**: Solo `enveloped-signature` transform (sin C14N adicional)

3. ✅ **Reference 2 (KeyInfo/Certificate)**: Agregar referencia al KeyInfo con su digest

4. ✅ **Reference 3 (SignedProperties)**: SIN transforms

5. ⚠️ **KeyInfo**: Incluir `RSAKeyValue` además del certificado (opcional pero lo tienen)

6. ✅ **Canonicalización**: Usar Inclusive C14N (method="c14n" exclusive=False)

---

## 🎯 RESUMEN:

**El problema NO era usar Exclusive C14N** - era todo lo contrario. El SRI autorizado usa:
- **Inclusive C14N** como método de canonicalización
- **Solo enveloped-signature** transform en la referencia a la factura
- **3 referencias**: factura, certificado, SignedProperties
- **No usa transforms** en la referencia a SignedProperties

Nuestra implementación anterior estaba más cerca de lo correcto, pero nos faltaba la tercera referencia al KeyInfo.
