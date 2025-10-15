import os
import sys
import random
import types

os.environ.setdefault('DATABASE_URL', 'sqlite:///test_db.sqlite3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

import django
import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.db import connection, models as dj_models
from django.conf import settings

django.setup()

from inventario.models import Empresa, Opciones
from inventario.sri import firmador_xades


@pytest.fixture(scope='session', autouse=True)
def _ensure_schema():
    with connection.schema_editor() as schema_editor:
        existing = set(connection.introspection.table_names())
        for model in apps.get_models():
            if not model._meta.managed:
                continue
            table = model._meta.db_table
            if table in existing:
                continue
            try:
                schema_editor.create_model(model)
            except Exception:
                continue
            existing.add(table)


def test_firmar_xml_usa_certificado_por_empresa(monkeypatch, tmp_path):
    """Cada empresa debe utilizar su propio PKCS#12 al firmar."""

    # Aislar almacenamiento de firmas en directorio temporal
    firmas_root = tmp_path / 'firmas'
    firmas_root.mkdir()
    monkeypatch.setattr(settings, 'FIRMAS_ROOT', str(firmas_root), raising=False)

    # Evitar validaciones costosas del modelo durante la prueba
    def simple_save(self, *args, **kwargs):
        dj_models.Model.save(self, *args, **kwargs)

    monkeypatch.setattr(Opciones, 'save', simple_save, raising=False)

    ruc_a = f"{random.randint(1000000000000, 9999999999999)}"
    ruc_b = f"{random.randint(1000000000000, 9999999999999)}"

    empresa_a = Empresa.objects.create(razon_social='Empresa A', ruc=ruc_a)
    empresa_b = Empresa.objects.create(razon_social='Empresa B', ruc=ruc_b)

    opciones_a = Opciones.objects.create(
        empresa=empresa_a,
        identificacion=empresa_a.ruc,
        password_firma='claveA',
    )
    opciones_b = Opciones.objects.create(
        empresa=empresa_b,
        identificacion=empresa_b.ruc,
        password_firma='claveB',
    )

    opciones_a.firma_electronica.save('empresa_a.p12', ContentFile(b'PKCS12-A'), save=True)
    opciones_b.firma_electronica.save('empresa_b.p12', ContentFile(b'PKCS12-B'), save=True)

    # Fijar implementación de endesive para que la prueba no dependa de la librería real
    captured_p12_bytes = []

    class DummyPrivateKey:
        def sign(self, data, _padding, _algorithm):
            return b'signature'

    class DummyCertificate:
        def public_bytes(self, _encoding):
            return b'certificate-der'

    def fake_load_key_and_certificates(p12_bytes, password, backend=None):
        captured_p12_bytes.append(p12_bytes)
        return DummyPrivateKey(), DummyCertificate(), []

    monkeypatch.setattr(
        firmador_xades.pkcs12,
        'load_key_and_certificates',
        fake_load_key_and_certificates,
    )

    class DummyBES:
        def enveloped(self, xml_data, certificate, cert_der, signproc, tspurl=None, tspcred=None):
            from lxml import etree

            root = etree.fromstring(xml_data)
            ns = 'http://www.w3.org/2000/09/xmldsig#'
            signature = etree.Element(f'{{{ns}}}Signature')
            signed_info = etree.SubElement(signature, f'{{{ns}}}SignedInfo')
            etree.SubElement(
                signed_info,
                f'{{{ns}}}CanonicalizationMethod',
                Algorithm='http://www.w3.org/2001/10/xml-exc-c14n#',
            )
            etree.SubElement(
                signed_info,
                f'{{{ns}}}SignatureMethod',
                Algorithm='http://www.w3.org/2001/04/xmldsig-more#rsa-sha256',
            )
            reference = etree.SubElement(signed_info, f'{{{ns}}}Reference', URI='')
            transforms = etree.SubElement(reference, f'{{{ns}}}Transforms')
            etree.SubElement(
                transforms,
                f'{{{ns}}}Transform',
                Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature',
            )
            etree.SubElement(
                transforms,
                f'{{{ns}}}Transform',
                Algorithm='http://www.w3.org/2001/10/xml-exc-c14n#',
            )
            etree.SubElement(
                reference,
                f'{{{ns}}}DigestMethod',
                Algorithm='http://www.w3.org/2001/04/xmlenc#sha256',
            )
            etree.SubElement(reference, f'{{{ns}}}DigestValue').text = ''
            etree.SubElement(signature, f'{{{ns}}}SignatureValue').text = ''
            root.append(signature)
            return etree.ElementTree(root)

    fake_endesive = types.ModuleType('endesive')
    fake_xades = types.ModuleType('endesive.xades')
    fake_xades.BES = DummyBES
    fake_endesive.xades = fake_xades
    monkeypatch.setitem(sys.modules, 'endesive', fake_endesive)
    monkeypatch.setitem(sys.modules, 'endesive.xades', fake_xades)

    xml_path = tmp_path / 'factura.xml'
    xml_path.write_text('<factura></factura>', encoding='utf-8')
    xml_firmado = tmp_path / 'factura_firmada.xml'

    # Firmar con cada empresa y asegurar que se usa el archivo correcto
    firmador_xades.firmar_xml_xades_bes(str(xml_path), str(xml_firmado), empresa=empresa_a)
    firmador_xades.firmar_xml_xades_bes(str(xml_path), str(xml_firmado), empresa=empresa_b)

    assert captured_p12_bytes == [b'PKCS12-A', b'PKCS12-B']

    opciones_a.firma_electronica.delete(save=False)
    opciones_b.firma_electronica.delete(save=False)
    opciones_a.delete()
    opciones_b.delete()
    empresa_a.delete()
    empresa_b.delete()
