from __future__ import annotations

import shutil
import tempfile
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase

from inventario.utils.media_paths import (
    build_factura_media_paths,
    build_proforma_media_paths,
)


class MediaPathsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self._tempdir = tempfile.mkdtemp(prefix="media-paths-")
        self._old_location = getattr(default_storage, "location", None)
        self._old_base_location = getattr(default_storage, "base_location", None)
        # FileSystemStorage exposes location/base_location used for path joins.
        default_storage.location = self._tempdir
        if hasattr(default_storage, "base_location"):
            default_storage.base_location = self._tempdir

    def tearDown(self):
        if self._old_location is not None:
            default_storage.location = self._old_location
        if hasattr(default_storage, "base_location") and self._old_base_location is not None:
            default_storage.base_location = self._old_base_location
        shutil.rmtree(self._tempdir, ignore_errors=True)
        super().tearDown()

    def _dummy_factura(self, ruc: str, secuencia: int = 1):
        empresa = SimpleNamespace(ruc=ruc)
        return SimpleNamespace(
            empresa=empresa,
            establecimiento="001",
            punto_emision="002",
            secuencia=str(secuencia).zfill(9),
        )

    def _dummy_proforma(self, ruc: str, numero: int = 1):
        empresa = SimpleNamespace(ruc=ruc)
        return SimpleNamespace(empresa=empresa, numero=numero)

    def test_factura_media_paths_are_normalized_per_company(self):
        empresas = ["1111111111111", "2222222222222"]
        for idx, ruc in enumerate(empresas, start=1):
            factura = self._dummy_factura(ruc, idx)
            paths = build_factura_media_paths(factura)

            self.assertEqual(paths.xml_dir, f"facturas/{ruc}/xml")
            self.assertEqual(paths.pdf_dir, f"facturas/{ruc}/pdf")

            xml_name = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.xml"
            xml_storage_path = f"{paths.xml_dir}/{xml_name}"
            default_storage.delete(xml_storage_path)
            saved_xml = default_storage.save(xml_storage_path, ContentFile(b"<xml/>"))
            self.assertEqual(saved_xml, xml_storage_path)

            pdf_name = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.pdf"
            pdf_storage_path = f"{paths.pdf_dir}/{pdf_name}"
            default_storage.delete(pdf_storage_path)
            saved_pdf = default_storage.save(pdf_storage_path, ContentFile(b"%PDF-1.4"))
            self.assertEqual(saved_pdf, pdf_storage_path)

    def test_proforma_media_paths_are_normalized_per_company(self):
        empresas = ["3333333333333", "4444444444444"]
        for idx, ruc in enumerate(empresas, start=1):
            proforma = self._dummy_proforma(ruc, idx)
            paths = build_proforma_media_paths(proforma)

            self.assertEqual(paths.pdf_dir, f"proformas/{ruc}/pdf")

            filename = f"PROFORMA_{proforma.numero}.pdf"
            storage_path = f"{paths.pdf_dir}/{filename}"
            default_storage.delete(storage_path)
            saved_path = default_storage.save(storage_path, ContentFile(b"%PDF-1.4"))
            self.assertEqual(saved_path, storage_path)
