from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from xml.dom import minidom
import xml.etree.ElementTree as ET


class RetencionXMLGenerator:
    """Generador de XML para comprobante de retención codDoc 07."""

    VERSION_BASICA = "1.0.0"
    VERSION_ATS = "2.0.0"

    CODIGO_PORCENTAJE_IVA = {
        Decimal("10.00"): "9",
        Decimal("20.00"): "10",
        Decimal("30.00"): "1",
        Decimal("50.00"): "11",
        Decimal("70.00"): "2",
        Decimal("100.00"): "3",
        Decimal("0.00"): "7",
    }

    @staticmethod
    def _money(value: Decimal | float | int | str) -> Decimal:
        return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _pct(value: Decimal | float | int | str) -> Decimal:
        return Decimal(value or 0).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _fmt(value: Decimal | float | int | str, decimales: int = 2) -> str:
        quantum = Decimal("1") if decimales == 0 else Decimal(f"1.{'0' * decimales}")
        val = Decimal(value or 0).quantize(quantum, rounding=ROUND_HALF_UP)
        texto = f"{val:.{decimales}f}"
        if len(texto) > 14 and decimales == 2:
            raise ValueError(f"Valor monetario excede 14 caracteres: {texto}")
        return texto

    def _validar_reglas(self, retencion):
        total_sin = self._money(retencion.total_sin_impuestos_doc)

        for impuesto in retencion.impuestos.all():
            esperado = self._money(Decimal(impuesto.base_imponible or 0) * (Decimal(impuesto.porcentaje_retener or 0) / Decimal("100")))
            actual = self._money(impuesto.valor_retenido)
            if esperado != actual:
                raise ValueError(
                    f"Error en diferencias para código {impuesto.codigo}/{impuesto.codigo_retencion}: "
                    f"esperado {esperado} y recibido {actual}."
                )

        if retencion.version_xml == self.VERSION_ATS:
            suma_bases_renta = sum(
                (Decimal(i.base_imponible or 0) for i in retencion.impuestos.all() if i.codigo == "1"),
                Decimal("0.00"),
            )
            if self._money(suma_bases_renta) != total_sin:
                raise ValueError(
                    "En versión 2.0.0, la suma de bases de renta en retenciones "
                    "debe coincidir con totalSinImpuestos del documento sustento."
                )

    def _append_info_tributaria(self, root, retencion):
        info = ET.SubElement(root, "infoTributaria")
        opciones = retencion.empresa.opciones.first() if hasattr(retencion.empresa, "opciones") else None

        ambiente = str(getattr(opciones, "tipo_ambiente", "1") or "1")
        tipo_emision = str(getattr(opciones, "tipo_emision", "1") or "1")
        razon_social = (
            getattr(opciones, "razon_social", None)
            or getattr(retencion.empresa, "razon_social", "")
            or "SIN RAZON SOCIAL"
        )
        nombre_comercial = getattr(opciones, "nombre_comercial", "") or ""
        ruc = (getattr(opciones, "identificacion", "") or getattr(retencion.empresa, "ruc", "")).zfill(13)
        dir_matriz = getattr(opciones, "direccion_establecimiento", "") or "SIN DIRECCION"

        ET.SubElement(info, "ambiente").text = ambiente
        ET.SubElement(info, "tipoEmision").text = tipo_emision
        ET.SubElement(info, "razonSocial").text = razon_social[:300]
        if nombre_comercial:
            ET.SubElement(info, "nombreComercial").text = nombre_comercial[:300]
        ET.SubElement(info, "ruc").text = ruc
        ET.SubElement(info, "claveAcceso").text = retencion.clave_acceso
        ET.SubElement(info, "codDoc").text = "07"
        ET.SubElement(info, "estab").text = f"{int(retencion.establecimiento):03d}"
        ET.SubElement(info, "ptoEmi").text = f"{int(retencion.punto_emision):03d}"
        ET.SubElement(info, "secuencial").text = f"{int(retencion.secuencia):09d}"
        ET.SubElement(info, "dirMatriz").text = dir_matriz[:300]

    def _append_info_comp_retencion(self, root, retencion, include_ats_fields: bool):
        info = ET.SubElement(root, "infoCompRetencion")
        opciones = retencion.empresa.opciones.first() if hasattr(retencion.empresa, "opciones") else None

        ET.SubElement(info, "fechaEmision").text = retencion.fecha_emision.strftime("%d/%m/%Y")
        if opciones and opciones.direccion_establecimiento:
            ET.SubElement(info, "dirEstablecimiento").text = opciones.direccion_establecimiento[:300]
        ET.SubElement(info, "obligadoContabilidad").text = "SI" if getattr(opciones, "obligado", "NO") == "SI" else "NO"
        ET.SubElement(info, "tipoIdentificacionSujetoRetenido").text = retencion.tipo_identificacion_sujeto_retenido

        if include_ats_fields:
            ET.SubElement(info, "tipoSujetoRetenido").text = "01"
            ET.SubElement(info, "parteRel").text = "NO"

        ET.SubElement(info, "razonSocialSujetoRetenido").text = retencion.razon_social_sujeto_retenido[:300]
        ET.SubElement(info, "identificacionSujetoRetenido").text = retencion.identificacion_sujeto_retenido
        ET.SubElement(info, "periodoFiscal").text = retencion.periodo_fiscal

    def _append_info_adicional(self, root, retencion):
        campos = list(retencion.campos_adicionales.all())
        if not campos:
            return

        info = ET.SubElement(root, "infoAdicional")
        for campo in campos:
            tag = ET.SubElement(info, "campoAdicional", {"nombre": (campo.nombre or "Campo")[:300]})
            tag.text = (campo.valor or "")[:300]

    def _generar_v100(self, retencion):
        root = ET.Element("comprobanteRetencion", {"id": "comprobante", "version": self.VERSION_BASICA})
        self._append_info_tributaria(root, retencion)
        self._append_info_comp_retencion(root, retencion, include_ats_fields=False)

        impuestos = ET.SubElement(root, "impuestos")
        for imp in retencion.impuestos.all():
            nodo = ET.SubElement(impuestos, "impuesto")
            ET.SubElement(nodo, "codigo").text = imp.codigo
            ET.SubElement(nodo, "codigoRetencion").text = imp.codigo_retencion
            ET.SubElement(nodo, "baseImponible").text = self._fmt(imp.base_imponible)
            ET.SubElement(nodo, "porcentajeRetener").text = self._fmt(imp.porcentaje_retener, decimales=2).rstrip("0").rstrip(".")
            ET.SubElement(nodo, "valorRetenido").text = self._fmt(imp.valor_retenido)
            ET.SubElement(nodo, "codDocSustento").text = retencion.cod_doc_sustento
            ET.SubElement(nodo, "numDocSustento").text = retencion.num_doc_sustento
            ET.SubElement(nodo, "fechaEmisionDocSustento").text = retencion.fecha_emision_doc_sustento.strftime("%d/%m/%Y")
            if retencion.num_aut_doc_sustento:
                ET.SubElement(nodo, "numAutDocSustento").text = retencion.num_aut_doc_sustento

        self._append_info_adicional(root, retencion)
        return root

    def _codigo_porcentaje_doc_sustento(self, retencion):
        total_sin = Decimal(retencion.total_sin_impuestos_doc or 0)
        total_iva = Decimal(retencion.total_iva_doc or 0)
        if total_sin <= 0 or total_iva <= 0:
            return "0", Decimal("0.00")

        tarifa = (total_iva / total_sin * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        codigo = "4" if tarifa == Decimal("15.00") else "2"
        return codigo, tarifa

    def _generar_v200(self, retencion):
        root = ET.Element("comprobanteRetencion", {"id": "comprobante", "version": self.VERSION_ATS})
        self._append_info_tributaria(root, retencion)
        self._append_info_comp_retencion(root, retencion, include_ats_fields=True)

        docs = ET.SubElement(root, "docsSustento")
        doc = ET.SubElement(docs, "docSustento")

        ET.SubElement(doc, "codSustento").text = "01"
        ET.SubElement(doc, "codDocSustento").text = retencion.cod_doc_sustento
        ET.SubElement(doc, "numDocSustento").text = retencion.num_doc_sustento
        ET.SubElement(doc, "fechaEmisionDocSustento").text = retencion.fecha_emision_doc_sustento.strftime("%d/%m/%Y")
        ET.SubElement(doc, "pagoLocExt").text = "01"
        ET.SubElement(doc, "totalSinImpuestos").text = self._fmt(retencion.total_sin_impuestos_doc)
        ET.SubElement(doc, "importeTotal").text = self._fmt(retencion.importe_total_doc)
        if retencion.num_aut_doc_sustento:
            ET.SubElement(doc, "numAutDocSustento").text = retencion.num_aut_doc_sustento

        codigo_porcentaje, tarifa = self._codigo_porcentaje_doc_sustento(retencion)
        impuestos_doc = ET.SubElement(doc, "impuestosDocSustento")
        imp_doc = ET.SubElement(impuestos_doc, "impuestoDocSustento")
        ET.SubElement(imp_doc, "codImpuestoDocSustento").text = "2"
        ET.SubElement(imp_doc, "codigoPorcentaje").text = codigo_porcentaje
        ET.SubElement(imp_doc, "baseImponible").text = self._fmt(retencion.total_sin_impuestos_doc)
        ET.SubElement(imp_doc, "tarifa").text = self._fmt(tarifa)
        ET.SubElement(imp_doc, "valorImpuesto").text = self._fmt(retencion.total_iva_doc)

        retenciones = ET.SubElement(doc, "retenciones")
        for imp in retencion.impuestos.all():
            nodo = ET.SubElement(retenciones, "retencion")
            ET.SubElement(nodo, "codigo").text = imp.codigo
            ET.SubElement(nodo, "codigoRetencion").text = imp.codigo_retencion
            ET.SubElement(nodo, "baseImponible").text = self._fmt(imp.base_imponible)
            ET.SubElement(nodo, "porcentajeRetener").text = self._fmt(imp.porcentaje_retener, decimales=2).rstrip("0").rstrip(".")
            ET.SubElement(nodo, "valorRetenido").text = self._fmt(imp.valor_retenido)

        self._append_info_adicional(root, retencion)
        return root

    def generar_xml_retencion(self, retencion) -> str:
        self._validar_reglas(retencion)

        if not retencion.clave_acceso:
            retencion.generar_clave_acceso()

        if retencion.version_xml == self.VERSION_BASICA:
            root = self._generar_v100(retencion)
        else:
            root = self._generar_v200(retencion)

        xml_bytes = ET.tostring(root, encoding="utf-8")
        xml_pretty = minidom.parseString(xml_bytes).toprettyxml(indent="    ", encoding="utf-8")
        return xml_pretty.decode("utf-8")
