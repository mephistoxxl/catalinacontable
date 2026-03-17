from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
import logging
from typing import Iterable, List, Sequence, Tuple

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from inventario.models import Cliente, Opciones, Proveedor, Transportista
from inventario.guia_remision.ride_guia_generator import GuiaRemisionRIDEGenerator
from inventario.guia_remision.xml_generator_guia import XMLGeneratorGuiaRemision
from inventario.liquidacion_compra.models import LiquidacionCompra
from inventario.liquidacion_compra.ride_generator_liquidacion import RIDELiquidacionCompraGenerator
from inventario.nota_credito.models import NotaCredito
from inventario.nota_credito.ride_generator_nc import RIDEGeneratorNotaCredito
from inventario.nota_credito.xml_generator_nc import XMLGeneratorNotaCredito
from inventario.nota_debito.models import NotaDebito
from inventario.nota_debito.ride_generator_nd import RIDENotaDebitoGenerator
from inventario.nota_debito.xml_generator_nd import XMLGeneratorNotaDebito
from inventario.retenciones.models import ComprobanteRetencion
from inventario.retenciones.ride_generator_retencion import RIDERetencionGenerator


logger = logging.getLogger(__name__)


Attachment = Tuple[str, bytes, str]


@dataclass
class SendResult:
    success: bool
    message: str
    recipients: List[str]


class DocumentEmailService:
    def __init__(self, empresa):
        self.empresa = empresa
        self.opciones = Opciones.objects.for_tenant(empresa).first()

    def send_retencion(self, retencion: ComprobanteRetencion) -> SendResult:
        estado = (retencion.estado_sri or '').strip().upper()
        if estado != 'AUTORIZADA':
            return SendResult(False, f'Retención no autorizada. Estado actual: {retencion.estado_sri}', [])

        destinatarios = self._emails_for_retencion(retencion)
        if not destinatarios:
            return SendResult(False, 'El proveedor/sujeto retenido no tiene correo registrado.', [])

        xml = (retencion.xml_firmado or retencion.xml_generado or '').strip()
        if not xml:
            return SendResult(False, 'No existe XML para adjuntar en la retención.', [])

        pdf_bytes = self._try_generate_retencion_pdf(retencion)
        if not pdf_bytes:
            return SendResult(False, 'No se pudo generar el PDF RIDE de la retención.', [])

        numero = retencion.numero_completo
        asunto = f'Retención electrónica {numero}'
        cuerpo = (
            f'Se adjunta la retención electrónica {numero}.\n\n'
            f'Clave de acceso: {retencion.clave_acceso or "N/A"}\n'
            f'Número de autorización: {retencion.numero_autorizacion or "N/A"}'
        )
        html = self._render_document_html(
            template_name='emails/retencion_autorizada.html',
            document_title='Comprobante de Retención',
            number_label='Retención No',
            document_number=numero,
            customer_name=getattr(retencion, 'razon_social_sujeto', '') or 'Contribuyente',
            access_key=retencion.clave_acceso or 'N/A',
            issue_date=self._format_date(getattr(retencion, 'fecha_emision_retencion', None)),
            total=self._format_decimal(getattr(retencion, 'total_retenido', None)),
            intro_text='Se ha emitido un comprobante de retención autorizado por el SRI a su nombre.',
            attachments=['Retencion.pdf', 'Retencion.xml'],
        )
        attachments: List[Attachment] = [
            (f'retencion_{numero.replace("-", "_")}.pdf', pdf_bytes, 'application/pdf'),
            (f'retencion_{numero.replace("-", "_")}.xml', xml.encode('utf-8'), 'application/xml'),
        ]
        self._send_email(asunto, cuerpo, destinatarios, attachments, html_body=html)
        return SendResult(True, 'Retención enviada por correo.', destinatarios)

    def send_nota_credito(self, nota_credito: NotaCredito) -> SendResult:
        estado = (nota_credito.estado_sri or '').strip().upper()
        if estado != 'AUTORIZADO':
            return SendResult(False, f'Nota de crédito no autorizada. Estado actual: {nota_credito.estado_sri}', [])

        destinatarios = self._emails_from_factura_cliente(nota_credito.factura_modificada)
        if not destinatarios:
            return SendResult(False, 'El cliente original no tiene correo registrado.', [])

        opciones = self._require_opciones()
        xml = XMLGeneratorNotaCredito(nota_credito, opciones).generar_xml()
        if not xml:
            return SendResult(False, 'No se pudo generar el XML de la nota de crédito.', [])

        pdf_bytes = self._try_generate_nc_pdf(nota_credito, opciones)
        if not pdf_bytes:
            return SendResult(False, 'No se pudo generar el PDF RIDE de la nota de crédito.', [])

        numero = nota_credito.numero_completo
        asunto = f'Nota de crédito electrónica {numero}'
        cuerpo = (
            f'Se adjunta la nota de crédito electrónica {numero}.\n\n'
            f'Clave de acceso: {nota_credito.clave_acceso or "N/A"}\n'
            f'Número de autorización: {nota_credito.numero_autorizacion or "N/A"}'
        )
        html = self._render_document_html(
            template_name='emails/nota_credito_autorizada.html',
            document_title='Nota de Crédito Electrónica',
            number_label='Nota de Crédito No',
            document_number=numero,
            customer_name=self._resolve_customer_name(getattr(nota_credito, 'factura_modificada', None)),
            access_key=nota_credito.clave_acceso or 'N/A',
            issue_date=self._format_date(getattr(nota_credito, 'fecha_emision', None)),
            total=self._format_decimal(getattr(nota_credito, 'valor_modificacion', None)),
            intro_text='Se ha emitido una nota de crédito electrónica autorizada por el SRI para la transacción original.',
            attachments=['NotaCredito.pdf', 'NotaCredito.xml'],
        )
        attachments: List[Attachment] = [
            (f'nota_credito_{numero.replace("-", "_")}.xml', xml.encode('utf-8'), 'application/xml'),
            (f'nota_credito_{numero.replace("-", "_")}.pdf', pdf_bytes, 'application/pdf'),
        ]

        self._send_email(asunto, cuerpo, destinatarios, attachments, html_body=html)
        return SendResult(True, 'Nota de crédito enviada por correo.', destinatarios)

    def send_nota_debito(self, nota_debito: NotaDebito) -> SendResult:
        estado = (nota_debito.estado_sri or '').strip().upper()
        if estado != 'AUTORIZADO':
            return SendResult(False, f'Nota de débito no autorizada. Estado actual: {nota_debito.estado_sri}', [])

        destinatarios = self._emails_from_factura_cliente(nota_debito.factura_modificada)
        if not destinatarios:
            return SendResult(False, 'El cliente original no tiene correo registrado.', [])

        opciones = self._require_opciones()
        xml = XMLGeneratorNotaDebito(nota_debito, opciones).generar_xml()
        if not xml:
            return SendResult(False, 'No se pudo generar el XML de la nota de débito.', [])

        pdf_bytes = self._try_generate_nd_pdf(nota_debito, opciones)
        if not pdf_bytes:
            return SendResult(False, 'No se pudo generar el PDF RIDE de la nota de débito.', [])

        numero = nota_debito.numero_completo
        asunto = f'Nota de débito electrónica {numero}'
        cuerpo = (
            f'Se adjunta la nota de débito electrónica {numero}.\n\n'
            f'Clave de acceso: {nota_debito.clave_acceso or "N/A"}\n'
            f'Número de autorización: {nota_debito.numero_autorizacion or "N/A"}'
        )
        html = self._render_document_html(
            template_name='emails/nota_debito_autorizada.html',
            document_title='Nota de Débito Electrónica',
            number_label='Nota de Débito No',
            document_number=numero,
            customer_name=self._resolve_customer_name(getattr(nota_debito, 'factura_modificada', None)),
            access_key=nota_debito.clave_acceso or 'N/A',
            issue_date=self._format_date(getattr(nota_debito, 'fecha_emision', None)),
            total=self._format_decimal(getattr(nota_debito, 'valor_modificacion', None)),
            intro_text='Se ha emitido una nota de débito electrónica autorizada por el SRI para la transacción original.',
            attachments=['NotaDebito.pdf', 'NotaDebito.xml'],
        )
        attachments: List[Attachment] = [
            (f'nota_debito_{numero.replace("-", "_")}.xml', xml.encode('utf-8'), 'application/xml'),
            (f'nota_debito_{numero.replace("-", "_")}.pdf', pdf_bytes, 'application/pdf'),
        ]

        self._send_email(asunto, cuerpo, destinatarios, attachments, html_body=html)
        return SendResult(True, 'Nota de débito enviada por correo.', destinatarios)

    def send_guia(self, guia) -> SendResult:
        estado = (guia.estado or '').strip().lower()
        esta_autorizada = estado == 'autorizada' or bool(getattr(guia, 'numero_autorizacion', None) and getattr(guia, 'fecha_autorizacion', None))
        if not esta_autorizada:
            return SendResult(False, f'Guía no autorizada. Estado actual: {guia.estado}', [])

        if estado != 'autorizada' and getattr(guia, 'numero_autorizacion', None) and getattr(guia, 'fecha_autorizacion', None):
            try:
                guia.estado = 'autorizada'
                guia.save(update_fields=['estado'])
            except Exception:
                pass

        destinatarios = self._emails_for_guia(guia)
        if not destinatarios:
            return SendResult(False, 'No se encontraron correos para destinatario/transportista.', [])

        xml = self._get_guia_xml(guia)
        if not xml:
            return SendResult(False, 'No existe XML para adjuntar en la guía.', [])

        pdf_bytes = self._try_generate_guia_pdf(guia)
        if not pdf_bytes:
            return SendResult(False, 'No se pudo generar el PDF RIDE de la guía.', [])

        numero = guia.numero_completo
        asunto = f'Guía de remisión electrónica {numero}'
        cuerpo = (
            f'Se adjunta la guía de remisión electrónica {numero}.\n\n'
            f'Clave de acceso: {guia.clave_acceso or "N/A"}\n'
            f'Número de autorización: {guia.numero_autorizacion or "N/A"}'
        )
        html = self._render_document_html(
            template_name='emails/guia_remision_autorizada.html',
            document_title='Guía de Remisión Electrónica',
            number_label='Guía No',
            document_number=numero,
            customer_name=self._resolve_guia_customer_name(guia),
            access_key=guia.clave_acceso or 'N/A',
            issue_date=self._resolve_guia_issue_date(guia),
            total='N/A',
            intro_text='Se ha emitido una guía de remisión electrónica autorizada para sustento legal del traslado de mercadería.',
            attachments=['GuiaRemision.pdf', 'GuiaRemision.xml'],
        )
        attachments = [
            (f'guia_remision_{numero.replace("-", "_")}.pdf', pdf_bytes, 'application/pdf'),
            (f'guia_remision_{numero.replace("-", "_")}.xml', xml.encode('utf-8'), 'application/xml')
        ]
        self._send_email(asunto, cuerpo, destinatarios, attachments, html_body=html)
        return SendResult(True, 'Guía enviada por correo.', destinatarios)

    def send_liquidacion(self, liquidacion: LiquidacionCompra) -> SendResult:
        estado = (liquidacion.estado_sri or '').strip().upper()
        if estado not in {'AUTORIZADA', 'AUTORIZADO'}:
            return SendResult(False, f'Liquidación no autorizada. Estado actual: {liquidacion.estado_sri}', [])

        destinatarios = self._emails_for_liquidacion(liquidacion)
        if not destinatarios:
            return SendResult(False, 'El vendedor/prestador no tiene correo registrado.', [])

        xml = (liquidacion.xml_autorizado or liquidacion.xml_firmado or '').strip()
        if not xml:
            return SendResult(False, 'No existe XML para adjuntar en la liquidación.', [])

        pdf_bytes = self._try_generate_liquidacion_pdf(liquidacion)
        if not pdf_bytes:
            return SendResult(False, 'No se pudo generar el PDF RIDE de la liquidación.', [])

        numero = liquidacion.numero_completo
        asunto = f'Liquidación de compra electrónica {numero}'
        cuerpo = (
            f'Se adjunta la liquidación de compra electrónica {numero}.\n\n'
            f'Clave de acceso: {liquidacion.clave_acceso or "N/A"}\n'
            f'Número de autorización: {liquidacion.numero_autorizacion or "N/A"}'
        )
        html = self._render_document_html(
            template_name='emails/liquidacion_compra_autorizada.html',
            document_title='Liquidación de Compra Electrónica',
            number_label='Liquidación No',
            document_number=numero,
            customer_name=self._resolve_liquidacion_customer_name(liquidacion),
            access_key=liquidacion.clave_acceso or 'N/A',
            issue_date=self._format_date(getattr(liquidacion, 'fecha_emision', None)),
            total=self._format_decimal(getattr(liquidacion, 'importe_total', None)),
            intro_text='Se ha emitido una liquidación de compra electrónica autorizada por el SRI a su nombre.',
            attachments=['LiquidacionCompra.pdf', 'LiquidacionCompra.xml'],
        )
        attachments = [
            (f'liquidacion_compra_{numero.replace("-", "_")}.pdf', pdf_bytes, 'application/pdf'),
            (f'liquidacion_compra_{numero.replace("-", "_")}.xml', xml.encode('utf-8'), 'application/xml')
        ]
        self._send_email(asunto, cuerpo, destinatarios, attachments, html_body=html)
        return SendResult(True, 'Liquidación enviada por correo.', destinatarios)

    def _require_opciones(self):
        if not self.opciones:
            raise ValueError('No existe configuración Opciones para la empresa activa.')
        return self.opciones

    def _try_generate_nc_pdf(self, nota_credito: NotaCredito, opciones) -> bytes | None:
        try:
            buffer: BytesIO = RIDEGeneratorNotaCredito(nota_credito, opciones).generar_pdf()
            return buffer.read()
        except Exception:
            return None

    def _try_generate_nd_pdf(self, nota_debito: NotaDebito, opciones) -> bytes | None:
        try:
            buffer: BytesIO = RIDENotaDebitoGenerator(nota_debito, opciones).generar_pdf()
            return buffer.read()
        except Exception:
            return None

    def _try_generate_retencion_pdf(self, retencion: ComprobanteRetencion) -> bytes | None:
        try:
            buffer: BytesIO = RIDERetencionGenerator(retencion, self.opciones).generar_pdf()
            return buffer.read()
        except Exception:
            return None

    def _try_generate_guia_pdf(self, guia) -> bytes | None:
        try:
            buffer: BytesIO = GuiaRemisionRIDEGenerator(self.empresa, self.opciones).generar_ride_guia_remision(guia)
            return buffer.read()
        except Exception as exc:
            logger.exception('Error generando PDF RIDE de guía %s: %s', getattr(guia, 'id', None), exc)
            return None

    def _try_generate_liquidacion_pdf(self, liquidacion: LiquidacionCompra) -> bytes | None:
        try:
            buffer: BytesIO = RIDELiquidacionCompraGenerator(liquidacion, self.opciones).generar_pdf()
            return buffer.read()
        except Exception as exc:
            logger.exception('Error generando PDF RIDE de liquidación %s: %s', getattr(liquidacion, 'id', None), exc)
            return None

    def _get_guia_xml(self, guia) -> str:
        xml = (getattr(guia, 'xml_autorizado', '') or '').strip()
        if xml:
            return xml

        xml = self._read_guia_xml_file(guia)
        if xml:
            return xml

        if not self.opciones:
            return ''

        try:
            xml = XMLGeneratorGuiaRemision(guia, self.empresa, self.opciones).generar_xml()
            return (xml or '').strip()
        except Exception as exc:
            logger.exception('Error generando XML de guía %s para correo: %s', getattr(guia, 'id', None), exc)
            return ''

    def _read_guia_xml_file(self, guia) -> str:
        try:
            base_dir = Path(settings.BASE_DIR) / 'media' / 'guias_xml' / str(self.empresa.id)
            nombre_archivo = f'guia_{guia.numero_completo.replace("-", "_")}.xml'
            ruta_completa = base_dir / nombre_archivo
            if ruta_completa.exists():
                return ruta_completa.read_text(encoding='utf-8').strip()
        except Exception as exc:
            logger.warning('No se pudo leer XML local de guía %s: %s', getattr(guia, 'id', None), exc)
        return ''

    def _send_email(
        self,
        subject: str,
        body: str,
        recipients: Sequence[str],
        attachments: Iterable[Attachment],
        html_body: str | None = None,
    ) -> None:
        clean_recipients = self._dedupe(recipients)
        if not clean_recipients:
            raise ValueError('No hay destinatarios de correo válidos.')

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@catalinasoft-ec.com')
        reply_to = []
        if self.opciones and getattr(self.opciones, 'correo', None):
            reply_to = [self.opciones.correo]

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=clean_recipients,
            reply_to=reply_to,
        )
        if html_body:
            email.attach_alternative(html_body, 'text/html')

        for filename, payload, mimetype in attachments:
            email.attach(filename, payload, mimetype)

        email.send(fail_silently=False)

    def _render_document_html(
        self,
        template_name: str,
        document_title: str,
        number_label: str,
        document_number: str,
        customer_name: str,
        access_key: str,
        issue_date: str,
        total: str,
        intro_text: str,
        attachments: List[str],
    ) -> str:
        nombre_emisor = self._nombre_emisor()
        ruc = getattr(self.opciones, 'identificacion', '') or getattr(self.empresa, 'ruc', '')
        context = {
            'document_title': document_title,
            'number_label': number_label,
            'document_number': document_number,
            'nombre_cliente': customer_name or 'Cliente',
            'intro_text': intro_text,
            'razon_social': nombre_emisor,
            'ruc': ruc,
            'fecha_emision': issue_date,
            'clave_acceso': access_key,
            'total': total,
            'attachments': attachments,
            'year': datetime.now().year,
        }
        return render_to_string(template_name, context)

    def _nombre_emisor(self) -> str:
        nombre_comercial = getattr(self.opciones, 'nombre_comercial', '') if self.opciones else ''
        razon_social = getattr(self.opciones, 'razon_social', '') if self.opciones else ''
        if nombre_comercial and nombre_comercial != '[CONFIGURAR NOMBRE COMERCIAL]':
            return nombre_comercial
        if razon_social:
            return razon_social
        return getattr(self.empresa, 'razon_social', 'Empresa')

    def _resolve_customer_name(self, factura) -> str:
        if not factura:
            return 'Cliente'
        return (
            getattr(factura, 'nombre_cliente', '')
            or getattr(getattr(factura, 'cliente', None), 'razon_social', '')
            or 'Cliente'
        )

    def _resolve_guia_customer_name(self, guia) -> str:
        try:
            destinatario = guia.destinatarios.order_by('id').first()
        except Exception:
            destinatario = None

        return (
            getattr(destinatario, 'razon_social_destinatario', '')
            or getattr(getattr(guia, 'factura', None), 'nombre_cliente', '')
            or 'Destinatario'
        )

    def _resolve_guia_issue_date(self, guia) -> str:
        return self._format_date(
            getattr(guia, 'fecha_inicio_traslado', None)
            or getattr(guia, 'fecha_creacion', None)
        )

    def _format_date(self, value) -> str:
        if not value:
            return 'N/A'
        try:
            return value.strftime('%d/%m/%Y')
        except Exception:
            return str(value)

    def _format_decimal(self, value) -> str:
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}"
        except Exception:
            return str(value)

    def _emails_from_proveedor(self, proveedor) -> List[str]:
        if not proveedor:
            return []
        values = [
            getattr(proveedor, 'correo', ''),
            getattr(proveedor, 'correo2', ''),
        ]
        return self._dedupe(self._expand_emails(values))

    def _emails_for_retencion(self, retencion: ComprobanteRetencion) -> List[str]:
        values = []

        def _qs_for_tenant(model):
            manager = getattr(model, 'objects', None)
            if manager is not None and hasattr(manager, 'for_tenant'):
                return manager.for_tenant(self.empresa)
            return model.objects.filter(empresa=self.empresa)

        proveedor = getattr(retencion, 'proveedor', None)
        if proveedor is not None:
            values.extend([
                getattr(proveedor, 'correo', ''),
                getattr(proveedor, 'correo2', ''),
            ])

        identificacion = (getattr(retencion, 'identificacion_sujeto', '') or '').strip()
        if identificacion:
            prov = _qs_for_tenant(Proveedor).filter(
                identificacion_proveedor=identificacion,
            ).first()
            if prov:
                values.extend([
                    getattr(prov, 'correo', ''),
                    getattr(prov, 'correo2', ''),
                ])

            cliente = _qs_for_tenant(Cliente).filter(
                identificacion=identificacion,
            ).first()
            if cliente:
                if hasattr(cliente, 'get_email_efectivo'):
                    try:
                        values.append(cliente.get_email_efectivo(self.empresa))
                    except Exception:
                        pass
                values.extend([
                    getattr(cliente, 'correo', ''),
                    getattr(cliente, 'email', ''),
                ])

            try:
                from inventario.liquidacion_compra.models import Prestador

                prestador = _qs_for_tenant(Prestador).filter(
                    identificacion=identificacion,
                ).first()
                if prestador:
                    values.append(getattr(prestador, 'correo', ''))
            except Exception:
                pass

        return self._dedupe(self._expand_emails(values))

    def _emails_for_liquidacion(self, liquidacion: LiquidacionCompra) -> List[str]:
        values = []

        try:
            prestador = getattr(liquidacion, 'prestador', None)
        except Exception:
            prestador = None

        if prestador is not None:
            values.extend([
                getattr(prestador, 'correo', ''),
            ])

        proveedor = getattr(liquidacion, 'proveedor', None)
        if proveedor is not None:
            values.extend([
                getattr(proveedor, 'correo', ''),
                getattr(proveedor, 'correo2', ''),
            ])

        return self._dedupe(self._expand_emails(values))

    def _resolve_liquidacion_customer_name(self, liquidacion: LiquidacionCompra) -> str:
        try:
            prestador = getattr(liquidacion, 'prestador', None)
        except Exception:
            prestador = None

        if prestador is not None and getattr(prestador, 'nombre', ''):
            return prestador.nombre

        proveedor = getattr(liquidacion, 'proveedor', None)
        return getattr(proveedor, 'razon_social_proveedor', '') or 'Proveedor'

    def _emails_from_factura_cliente(self, factura) -> List[str]:
        if not factura:
            return []

        cliente = getattr(factura, 'cliente', None)
        values = [
            getattr(factura, 'correo', ''),
            getattr(factura, 'email', ''),
        ]

        if cliente is not None:
            if hasattr(cliente, 'get_email_efectivo'):
                try:
                    values.append(cliente.get_email_efectivo(self.empresa))
                except Exception:
                    pass
            values.extend([
                getattr(cliente, 'correo', ''),
                getattr(cliente, 'email', ''),
            ])

        return self._dedupe(self._expand_emails(values))

    def _emails_for_guia(self, guia) -> List[str]:
        values = [getattr(guia, 'correo_envio', '')]

        factura_asociada = getattr(guia, 'factura', None)
        if factura_asociada is not None:
            values.extend(self._emails_from_factura_cliente(factura_asociada))

        identificacion_principal = (getattr(guia, 'destinatario_identificacion', '') or '').strip()
        if identificacion_principal:
            cliente_principal = Cliente.objects.filter(
                empresa=self.empresa,
                identificacion=identificacion_principal,
            ).first()
            if cliente_principal:
                if hasattr(cliente_principal, 'get_email_efectivo'):
                    try:
                        values.append(cliente_principal.get_email_efectivo(self.empresa))
                    except Exception:
                        pass
                values.append(getattr(cliente_principal, 'correo', ''))
                values.append(getattr(cliente_principal, 'email', ''))

        try:
            transportista = Transportista.objects.filter(
                empresa=self.empresa,
                ruc_cedula=getattr(guia, 'transportista_ruc', ''),
                activo=True,
            ).first()
            if transportista:
                values.append(getattr(transportista, 'email', ''))
        except Exception:
            pass

        try:
            for destinatario in guia.destinatarios.all():
                identificacion = (getattr(destinatario, 'identificacion_destinatario', '') or '').strip()
                if not identificacion:
                    continue
                cliente = Cliente.objects.filter(
                    empresa=self.empresa,
                    identificacion=identificacion,
                ).first()
                if cliente:
                    if hasattr(cliente, 'get_email_efectivo'):
                        try:
                            values.append(cliente.get_email_efectivo(self.empresa))
                        except Exception:
                            pass
                    values.append(getattr(cliente, 'correo', ''))
                    values.append(getattr(cliente, 'email', ''))
        except Exception:
            pass

        return self._dedupe(self._expand_emails(values))

    def _expand_emails(self, values: Iterable[str]) -> List[str]:
        emails: List[str] = []
        for raw in values:
            if not raw:
                continue
            for token in str(raw).replace(';', ',').split(','):
                mail = token.strip()
                if mail and '@' in mail:
                    emails.append(mail)
        return emails

    def _dedupe(self, emails: Iterable[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for email in emails:
            val = (email or '').strip()
            if not val:
                continue
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(val)
        return result
