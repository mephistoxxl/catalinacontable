from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

from lxml import etree

from .services import (
    calcular_totales_desde_componentes,
    format_decimal_for_xml,
    generar_clave_acceso_retencion,
    inferir_tipo_identificacion,
    obtener_codigo_porcentaje_iva_sustento,
)


@dataclass
class XmlValidationResult:
    valido: bool
    mensaje: str
    errores: str = ""


class RetencionXMLGenerator:
    VERSION = "2.0.0"

    def __init__(self, comprobante):
        self.comprobante = comprobante
        self.empresa = comprobante.empresa
        self.opciones = self.empresa.opciones.first() if hasattr(self.empresa, "opciones") else None

    def generar_clave_acceso(self) -> str:
        if self.comprobante.clave_acceso and len(self.comprobante.clave_acceso) == 49:
            return self.comprobante.clave_acceso

        ambiente = (getattr(self.opciones, "tipo_ambiente", None) or getattr(self.empresa, "tipo_ambiente", None) or "1").strip()
        tipo_emision = (getattr(self.opciones, "tipo_emision", None) or "1").strip()

        clave = generar_clave_acceso_retencion(
            fecha_emision=self.comprobante.fecha_emision_retencion,
            ruc_emisor=(getattr(self.opciones, "identificacion", None) or self.empresa.ruc or "").strip(),
            ambiente=ambiente,
            establecimiento=self.comprobante.establecimiento_retencion,
            punto_emision=self.comprobante.punto_emision_retencion,
            secuencial=self.comprobante.secuencia_retencion,
            tipo_emision=tipo_emision,
        )
        return clave

    def generar_xml(self) -> str:
        comp = self.comprobante
        opts = self.opciones

        clave_acceso = self.generar_clave_acceso()

        root = ET.Element("comprobanteRetencion", {"id": "comprobante", "version": self.VERSION})

        info_trib = ET.SubElement(root, "infoTributaria")
        ambiente = (getattr(opts, "tipo_ambiente", None) or getattr(self.empresa, "tipo_ambiente", None) or "1").strip()
        tipo_emision = (getattr(opts, "tipo_emision", None) or "1").strip()
        razon_social = (getattr(opts, "razon_social", None) or self.empresa.razon_social or "").strip()[:300]
        nombre_comercial = (getattr(opts, "nombre_comercial", None) or "").strip()[:300]
        ruc = (getattr(opts, "identificacion", None) or self.empresa.ruc or "").strip()
        dir_matriz = (getattr(opts, "direccion_establecimiento", None) or "SIN DIRECCION").strip()[:300]

        ET.SubElement(info_trib, "ambiente").text = ambiente
        ET.SubElement(info_trib, "tipoEmision").text = tipo_emision
        ET.SubElement(info_trib, "razonSocial").text = razon_social
        if nombre_comercial:
            ET.SubElement(info_trib, "nombreComercial").text = nombre_comercial
        ET.SubElement(info_trib, "ruc").text = ruc
        ET.SubElement(info_trib, "claveAcceso").text = clave_acceso
        ET.SubElement(info_trib, "codDoc").text = "07"
        ET.SubElement(info_trib, "estab").text = comp.establecimiento_retencion
        ET.SubElement(info_trib, "ptoEmi").text = comp.punto_emision_retencion
        ET.SubElement(info_trib, "secuencial").text = comp.secuencia_retencion
        ET.SubElement(info_trib, "dirMatriz").text = dir_matriz

        agente_retencion = getattr(opts, "agente_retencion_xml", None)
        if agente_retencion:
            numero = "".join(ch for ch in str(agente_retencion) if ch.isdigit())[:8]
            if numero:
                ET.SubElement(info_trib, "agenteRetencion").text = numero

        if getattr(opts, "tipo_regimen", "") == "RIMPE":
            ET.SubElement(info_trib, "contribuyenteRimpe").text = "CONTRIBUYENTE RÉGIMEN RIMPE"

        info_comp = ET.SubElement(root, "infoCompRetencion")
        ET.SubElement(info_comp, "fechaEmision").text = comp.fecha_emision_retencion.strftime("%d/%m/%Y")

        dir_est = (getattr(opts, "direccion_establecimiento", None) or "").strip()
        if dir_est:
            ET.SubElement(info_comp, "dirEstablecimiento").text = dir_est[:300]

        cont_esp = (getattr(opts, "contribuyente_especial_xml", None) or "").strip() if opts else ""
        if cont_esp:
            ET.SubElement(info_comp, "contribuyenteEspecial").text = cont_esp[:13]

        obligado = (getattr(opts, "obligado_contabilidad_xml", None) or "").strip() if opts else ""
        if obligado in {"SI", "NO"}:
            ET.SubElement(info_comp, "obligadoContabilidad").text = obligado

        ET.SubElement(info_comp, "tipoIdentificacionSujetoRetenido").text = inferir_tipo_identificacion(comp.identificacion_sujeto)
        ET.SubElement(info_comp, "parteRel").text = "NO"
        ET.SubElement(info_comp, "razonSocialSujetoRetenido").text = (comp.razon_social_sujeto or "CONSUMIDOR").strip()[:300]
        ET.SubElement(info_comp, "identificacionSujetoRetenido").text = (comp.identificacion_sujeto or "9999999999999").strip()[:20]
        ET.SubElement(info_comp, "periodoFiscal").text = comp.fecha_emision_retencion.strftime("%m/%Y")

        docs_sustento = ET.SubElement(root, "docsSustento")
        doc = ET.SubElement(docs_sustento, "docSustento")

        ET.SubElement(doc, "codSustento").text = (comp.sustento_tributario or "00").zfill(2)[:2]
        ET.SubElement(doc, "codDocSustento").text = (comp.tipo_documento_sustento or "01").zfill(2)[:2]
        ET.SubElement(doc, "numDocSustento").text = f"{comp.establecimiento_doc}{comp.punto_emision_doc}{comp.secuencia_doc}"
        ET.SubElement(doc, "fechaEmisionDocSustento").text = comp.fecha_emision.strftime("%d/%m/%Y")

        if comp.autorizacion_doc_sustento:
            ET.SubElement(doc, "numAutDocSustento").text = comp.autorizacion_doc_sustento[:49]

        ET.SubElement(doc, "pagoLocExt").text = "01"

        total_sin_impuestos, importe_total = calcular_totales_desde_componentes(
            base_iva_0=comp.base_iva_0,
            base_iva_5=comp.base_iva_5,
            base_no_obj_iva=comp.base_no_obj_iva,
            base_exento_iva=comp.base_exento_iva,
            base_iva=comp.base_iva,
            monto_iva=comp.monto_iva,
            monto_ice=comp.monto_ice,
        )

        ET.SubElement(doc, "totalSinImpuestos").text = format_decimal_for_xml(total_sin_impuestos)
        ET.SubElement(doc, "importeTotal").text = format_decimal_for_xml(importe_total)

        impuestos_doc = ET.SubElement(doc, "impuestosDocSustento")
        imp = ET.SubElement(impuestos_doc, "impuestoDocSustento")
        ET.SubElement(imp, "codImpuestoDocSustento").text = "2"
        ET.SubElement(imp, "codigoPorcentaje").text = obtener_codigo_porcentaje_iva_sustento(comp.porcentaje_iva)
        ET.SubElement(imp, "baseImponible").text = format_decimal_for_xml(comp.base_iva)
        ET.SubElement(imp, "tarifa").text = format_decimal_for_xml(comp.porcentaje_iva)
        ET.SubElement(imp, "valorImpuesto").text = format_decimal_for_xml(comp.monto_iva)

        retenciones = ET.SubElement(doc, "retenciones")
        detalles = list(comp.detalles.all().order_by("id"))
        if not detalles:
            detalles = [None]

        for detalle in detalles:
            nodo_ret = ET.SubElement(retenciones, "retencion")
            if detalle is None:
                ET.SubElement(nodo_ret, "codigo").text = "2"
                ET.SubElement(nodo_ret, "codigoRetencion").text = "8"
                ET.SubElement(nodo_ret, "baseImponible").text = "0.00"
                ET.SubElement(nodo_ret, "porcentajeRetener").text = "0.00"
                ET.SubElement(nodo_ret, "valorRetenido").text = "0.00"
            else:
                ET.SubElement(nodo_ret, "codigo").text = "1" if detalle.tipo_impuesto == "RENTA" else "2"
                ET.SubElement(nodo_ret, "codigoRetencion").text = str(detalle.codigo_retencion or "")[:5]
                ET.SubElement(nodo_ret, "baseImponible").text = format_decimal_for_xml(detalle.base_imponible)
                ET.SubElement(nodo_ret, "porcentajeRetener").text = format_decimal_for_xml(detalle.porcentaje_retener)
                ET.SubElement(nodo_ret, "valorRetenido").text = format_decimal_for_xml(detalle.valor_retenido)

        pagos = ET.SubElement(doc, "pagos")
        pago = ET.SubElement(pagos, "pago")
        ET.SubElement(pago, "formaPago").text = (comp.forma_pago_sri or "20").zfill(2)[:2]
        ET.SubElement(pago, "total").text = format_decimal_for_xml(importe_total)

        xml_bytes = ET.tostring(root, encoding="utf-8")
        xml_pretty = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")
        return xml_pretty.decode("utf-8")

    def validar_xml(self, xml_content: str, xsd_path: str | None = None) -> XmlValidationResult:
        try:
            xsd_file = Path(xsd_path) if xsd_path else Path(__file__).resolve().parent / "ComprobanteRetencion_V2.0.0.xsd"
            if not xsd_file.exists():
                return XmlValidationResult(False, "No se encontró XSD de retención v2.0.0", "Archivo no existe")

            parser = etree.XMLParser(resolve_entities=False)
            xml_doc = etree.fromstring(xml_content.encode("utf-8"), parser)
            xsd_doc = etree.parse(str(xsd_file), parser)
            schema = etree.XMLSchema(xsd_doc)

            if schema.validate(xml_doc):
                return XmlValidationResult(True, "XML válido según XSD v2.0.0")

            errores = "\n".join(str(err) for err in schema.error_log)
            return XmlValidationResult(False, "XML inválido para XSD v2.0.0", errores)
        except Exception as exc:
            return XmlValidationResult(False, "Error validando XML", str(exc))
