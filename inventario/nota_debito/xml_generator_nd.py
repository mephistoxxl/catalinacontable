"""Generador de XML para Notas de Débito Electrónicas (SRI codDoc 05).

Implementación pragmática: genera clave de acceso (49 dígitos) y XML básico con
la estructura estándar del SRI para Nota de Débito.

Nota: Si el SRI rechaza por validaciones XSD/campos faltantes, el error vendrá
en la respuesta; pero al menos no quedará bloqueado por NotImplementedError.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from random import randint


logger = logging.getLogger(__name__)


class XMLGeneratorNotaDebito:
    VERSION_XML = '1.0'
    ENCODING = 'UTF-8'
    VERSION_ND = '1.0.0'

    def __init__(self, nota_debito, opciones):
        self.nd = nota_debito
        self.opciones = opciones
        self.empresa = getattr(nota_debito, 'empresa', None)

    # ======================== CLAVE DE ACCESO ========================
    def generar_clave_acceso(self) -> str:
        """Genera la clave de acceso de 49 dígitos según estándar SRI Ecuador.

        Formato: ddmmaaaa + codDoc + ruc + ambiente + serie + secuencial + codigoNumerico + tipoEmision + digitoVerificador
        """

        if not getattr(self.nd, 'fecha_emision', None):
            raise ValueError('La Nota de Débito no tiene fecha_emision')

        fecha_emision = self.nd.fecha_emision.strftime('%d%m%Y')
        cod_doc = '05'  # Nota de Débito

        # RUC emisor
        ruc_emisor = (
            (getattr(self.opciones, 'identificacion', None) or '').strip()
            or (getattr(self.empresa, 'ruc', None) or '').strip()
        )
        if not ruc_emisor:
            raise ValueError('RUC/identificación de empresa no configurado')
        ruc_emisor = ruc_emisor.zfill(13)

        # Ambiente (1=Pruebas, 2=Producción)
        tipo_ambiente = str(getattr(self.opciones, 'tipo_ambiente', '1') or '1').strip()
        if tipo_ambiente not in ('1', '2'):
            tipo_ambiente = '1'

        # Serie (estab+pto)
        establecimiento = (getattr(self.nd, 'establecimiento', '') or '').zfill(3)
        punto_emision = (getattr(self.nd, 'punto_emision', '') or '').zfill(3)
        serie = f"{establecimiento}{punto_emision}"

        # Secuencial (9)
        secuencial = (getattr(self.nd, 'secuencial', '') or '').zfill(9)

        # Código numérico (8)
        codigo_numerico = str(randint(10000000, 99999999))

        # Tipo emisión (1=normal, 2=contingencia)
        tipo_emision = str(getattr(self.opciones, 'tipo_emision', '1') or '1').strip()
        if tipo_emision not in ('1', '2'):
            tipo_emision = '1'

        clave_base = (
            f"{fecha_emision}"  # 8
            f"{cod_doc}"  # 2
            f"{ruc_emisor}"  # 13
            f"{tipo_ambiente}"  # 1
            f"{serie}"  # 6
            f"{secuencial}"  # 9
            f"{codigo_numerico}"  # 8
            f"{tipo_emision}"  # 1
        )

        # Dígito verificador (Módulo 11)
        try:
            clave_lista = [int(d) for d in clave_base]
        except ValueError:
            raise ValueError('Clave base contiene caracteres no numéricos')

        pesos = [2, 3, 4, 5, 6, 7]
        total = 0
        peso_index = 0
        for digito in reversed(clave_lista):
            total += digito * pesos[peso_index]
            peso_index = (peso_index + 1) % len(pesos)

        residuo = total % 11
        digito_verificador = 11 - residuo
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1

        clave_acceso = f"{clave_base}{digito_verificador}"
        if len(clave_acceso) != 49:
            raise ValueError(f"Clave de acceso debe tener 49 dígitos, se generaron {len(clave_acceso)}")

        return clave_acceso

    # ============================= XML =============================
    def generar_xml(self) -> str:
        """Genera el XML completo de la Nota de Débito."""

        if not self.nd.clave_acceso:
            self.nd.clave_acceso = self.generar_clave_acceso()

        root = ET.Element('notaDebito')
        root.set('id', 'comprobante')
        root.set('version', self.VERSION_ND)

        self._agregar_info_tributaria(root)
        self._agregar_info_nota_debito(root)
        self._agregar_motivos(root)
        self._agregar_info_adicional(root)

        xml_string = ET.tostring(root, encoding='unicode')
        xml_declaration = f'<?xml version="{self.VERSION_XML}" encoding="{self.ENCODING}"?>'
        return xml_declaration + xml_string

    def _agregar_info_tributaria(self, root):
        info_trib = ET.SubElement(root, 'infoTributaria')

        ambiente = str(getattr(self.opciones, 'tipo_ambiente', '1') or '1')
        if ambiente not in ('1', '2'):
            ambiente = '1'
        ET.SubElement(info_trib, 'ambiente').text = ambiente

        tipo_emision = str(getattr(self.opciones, 'tipo_emision', '1') or '1')
        if tipo_emision not in ('1', '2'):
            tipo_emision = '1'
        ET.SubElement(info_trib, 'tipoEmision').text = tipo_emision

        razon_social = (
            getattr(self.opciones, 'razon_social', None)
            or getattr(self.empresa, 'razon_social', None)
            or getattr(self.empresa, 'razonSocial', None)
            or 'SIN RAZÓN SOCIAL'
        )
        ET.SubElement(info_trib, 'razonSocial').text = self._limpiar_texto(razon_social)

        nombre_comercial = getattr(self.opciones, 'nombre_comercial', None) or getattr(self.empresa, 'nombre_comercial', None)
        if nombre_comercial:
            ET.SubElement(info_trib, 'nombreComercial').text = self._limpiar_texto(nombre_comercial)

        ruc_emisor = (
            (getattr(self.opciones, 'identificacion', None) or '').strip()
            or (getattr(self.empresa, 'ruc', None) or '').strip()
        )
        ET.SubElement(info_trib, 'ruc').text = ruc_emisor

        ET.SubElement(info_trib, 'claveAcceso').text = str(self.nd.clave_acceso)
        ET.SubElement(info_trib, 'codDoc').text = '05'
        ET.SubElement(info_trib, 'estab').text = str(self.nd.establecimiento).zfill(3)
        ET.SubElement(info_trib, 'ptoEmi').text = str(self.nd.punto_emision).zfill(3)
        ET.SubElement(info_trib, 'secuencial').text = str(self.nd.secuencial).zfill(9)

        dir_matriz = getattr(self.opciones, 'direccion_establecimiento', None) or 'S/N'
        ET.SubElement(info_trib, 'dirMatriz').text = self._limpiar_texto(dir_matriz)

        if getattr(self.opciones, 'agente_retencion', None) and str(self.opciones.agente_retencion) != '...':
            ET.SubElement(info_trib, 'agenteRetencion').text = str(self.opciones.agente_retencion)

        if getattr(self.opciones, 'contribuyente_rimpe', None):
            ET.SubElement(info_trib, 'contribuyenteRimpe').text = 'CONTRIBUYENTE RÉGIMEN RIMPE'

    def _agregar_info_nota_debito(self, root):
        info_nd = ET.SubElement(root, 'infoNotaDebito')

        ET.SubElement(info_nd, 'fechaEmision').text = self.nd.fecha_emision.strftime('%d/%m/%Y')

        dir_estab = getattr(self.opciones, 'direccion_establecimiento', None)
        if dir_estab:
            ET.SubElement(info_nd, 'dirEstablecimiento').text = self._limpiar_texto(dir_estab)

        factura = getattr(self.nd, 'factura_modificada', None)
        cliente = getattr(factura, 'cliente', None) if factura else None

        tipo_id = getattr(cliente, 'tipoIdentificacion', None) if cliente else None
        if not tipo_id:
            ident_raw = (
                (getattr(cliente, 'identificacion', None) if cliente else None)
                or getattr(factura, 'identificacion_cliente', None)
                or ''
            )
            ident_len = len(str(ident_raw).strip())
            tipo_id = '04' if ident_len == 13 else '05' if ident_len == 10 else '08'
        ET.SubElement(info_nd, 'tipoIdentificacionComprador').text = str(tipo_id)

        razon_social_comprador = (
            (getattr(cliente, 'razon_social', None) if cliente else None)
            or (getattr(cliente, 'nombre', None) if cliente else None)
            or getattr(factura, 'nombre_cliente', None)
            or 'CONSUMIDOR FINAL'
        )
        ET.SubElement(info_nd, 'razonSocialComprador').text = self._limpiar_texto(razon_social_comprador)

        identificacion = (
            (getattr(cliente, 'identificacion', None) if cliente else None)
            or (getattr(cliente, 'ruc', None) if cliente else None)
            or (getattr(cliente, 'cedula', None) if cliente else None)
            or getattr(factura, 'identificacion_cliente', None)
            or getattr(factura, 'identificacion', None)
            or ''
        )
        ET.SubElement(info_nd, 'identificacionComprador').text = str(identificacion)

        if getattr(self.opciones, 'numero_contribuyente_especial', None):
            ET.SubElement(info_nd, 'contribuyenteEspecial').text = str(self.opciones.numero_contribuyente_especial)

        obligado = 'SI' if getattr(self.opciones, 'obligado', None) in ('SI', True) else 'NO'
        ET.SubElement(info_nd, 'obligadoContabilidad').text = obligado

        ET.SubElement(info_nd, 'codDocModificado').text = str(self.nd.cod_doc_modificado or '01')
        ET.SubElement(info_nd, 'numDocModificado').text = str(self.nd.num_doc_modificado)
        ET.SubElement(info_nd, 'fechaEmisionDocSustento').text = self.nd.fecha_emision_doc_sustento.strftime('%d/%m/%Y')

        total_sin_imp = Decimal(str(getattr(self.nd, 'subtotal_sin_impuestos', 0) or 0))
        total_sin_imp = total_sin_imp.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        ET.SubElement(info_nd, 'totalSinImpuestos').text = self._formatear_decimal(total_sin_imp)

        # impuestos (resumen)
        impuestos = ET.SubElement(info_nd, 'impuestos')
        totales = list(getattr(self.nd, 'totales_impuestos', []).all()) if hasattr(self.nd, 'totales_impuestos') else []
        if not totales and hasattr(self.nd, 'detalles'):
            totales = self._calcular_totales_impuestos_desde_detalles()
        if not totales:
            # El XSD requiere al menos un <impuesto>
            totales = self._calcular_totales_impuestos_fallback()
        for t in totales:
            imp = ET.SubElement(impuestos, 'impuesto')
            ET.SubElement(imp, 'codigo').text = str(getattr(t, 'codigo', '2') or '2')
            ET.SubElement(imp, 'codigoPorcentaje').text = str(getattr(t, 'codigo_porcentaje', '4') or '4')
            ET.SubElement(imp, 'tarifa').text = self._formatear_decimal(Decimal(str(getattr(t, 'tarifa', 0) or 0)))
            ET.SubElement(imp, 'baseImponible').text = self._formatear_decimal(Decimal(str(getattr(t, 'base_imponible', 0) or 0)))
            ET.SubElement(imp, 'valor').text = self._formatear_decimal(Decimal(str(getattr(t, 'valor', 0) or 0)))

        valor_total = Decimal(str(getattr(self.nd, 'valor_modificacion', 0) or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        ET.SubElement(info_nd, 'valorTotal').text = self._formatear_decimal(valor_total)

        # Pagos (opcional en XSD, pero requerido por el SRI en muchos casos)
        if valor_total >= Decimal('0.00'):
            self._agregar_pagos(info_nd, valor_total)

    def _agregar_pagos(self, info_nd, valor_total: Decimal):
        """Agrega <pagos><pago>...</pago></pagos> según NotaDebito_V1.0.0.xsd."""

        factura = getattr(self.nd, 'factura_modificada', None)
        forma_pago = None
        try:
            if factura and hasattr(factura, 'formas_pago') and factura.formas_pago.exists():
                forma_pago = (factura.formas_pago.first().forma_pago or '').strip()
        except Exception:
            forma_pago = None

        # Fallback válido según patrón del XSD: 01..21
        if not forma_pago:
            forma_pago = '20'

        pagos = ET.SubElement(info_nd, 'pagos')
        pago = ET.SubElement(pagos, 'pago')
        ET.SubElement(pago, 'formaPago').text = str(forma_pago)
        ET.SubElement(pago, 'total').text = self._formatear_decimal(valor_total)

    def _agregar_motivos(self, root):
        """Agrega el bloque obligatorio <motivos> según NotaDebito_V1.0.0.xsd.

        Nota: En el XSD de Nota de Débito no existe <detalles>; se reporta como una
        lista de <motivo> con razón y valor.
        """

        motivos = ET.SubElement(root, 'motivos')

        razon = self._limpiar_texto(getattr(self.nd, 'motivo', None) or 'MODIFICACIÓN')
        # En Nota de Débito el valor de motivo debe cuadrar con totalSinImpuestos.
        valor_motivo = Decimal(str(getattr(self.nd, 'subtotal_sin_impuestos', 0) or 0)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        motivo = ET.SubElement(motivos, 'motivo')
        ET.SubElement(motivo, 'razon').text = razon
        ET.SubElement(motivo, 'valor').text = self._formatear_decimal(valor_motivo)

    def _agregar_detalles(self, root):
        detalles_root = ET.SubElement(root, 'detalles')
        for detalle in self.nd.detalles.all():
            det = ET.SubElement(detalles_root, 'detalle')

            ET.SubElement(det, 'codigoInterno').text = str(detalle.codigo_principal)
            ET.SubElement(det, 'descripcion').text = self._limpiar_texto(detalle.descripcion)

            ET.SubElement(det, 'cantidad').text = self._formatear_decimal(Decimal(str(detalle.cantidad or 0)), 6)
            ET.SubElement(det, 'precioUnitario').text = self._formatear_decimal(Decimal(str(detalle.precio_unitario or 0)), 6)
            ET.SubElement(det, 'descuento').text = self._formatear_decimal(Decimal(str(detalle.descuento or 0)))

            base = Decimal(str(detalle.base_imponible or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ET.SubElement(det, 'precioTotalSinImpuesto').text = self._formatear_decimal(base)

            impuestos = ET.SubElement(det, 'impuestos')
            imp = ET.SubElement(impuestos, 'impuesto')

            codigo_porcentaje = str(getattr(detalle, 'codigo_iva', None) or '')
            tarifa = Decimal(str(getattr(detalle, 'tarifa_iva', 0) or 0))
            if not codigo_porcentaje or codigo_porcentaje == '2':
                codigo_porcentaje = self._codigo_porcentaje_por_tarifa(tarifa)

            valor_iva = Decimal(str(detalle.valor_iva or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ET.SubElement(imp, 'codigo').text = '2'
            ET.SubElement(imp, 'codigoPorcentaje').text = codigo_porcentaje
            ET.SubElement(imp, 'tarifa').text = self._formatear_decimal(tarifa)
            ET.SubElement(imp, 'baseImponible').text = self._formatear_decimal(base)
            ET.SubElement(imp, 'valor').text = self._formatear_decimal(valor_iva)

    def _agregar_info_adicional(self, root):
        """Agrega infoAdicional solo si hay al menos un campo.

        IMPORTANTE: En el XSD, si existe <infoAdicional> debe contener al menos un
        <campoAdicional>. Por eso no se crea el nodo si no hay valores.
        """

        factura = getattr(self.nd, 'factura_modificada', None)
        if not factura:
            return
        cliente = getattr(factura, 'cliente', None)

        def obtener_campo_adicional(posibles_nombres):
            try:
                campos = getattr(factura, 'campos_adicionales', None)
                if not campos:
                    return None
                mapa = {
                    (c.nombre or '').strip().upper(): (c.valor or '').strip()
                    for c in campos.all()
                }
                for nombre in posibles_nombres:
                    valor = mapa.get(str(nombre).strip().upper())
                    if valor:
                        return valor
            except Exception:
                return None
            return None

        email = (
            obtener_campo_adicional(['E-MAIL', 'EMAIL', 'CORREO', 'MAIL'])
            or getattr(factura, 'correo', None)
            or getattr(cliente, 'correo', None)
            or getattr(cliente, 'email', None)
        )
        telefono = (
            obtener_campo_adicional(['TELÉFONO', 'TELEFONO', 'TEL'])
            or getattr(cliente, 'telefono', None)
            or getattr(cliente, 'telefono1', None)
            or getattr(cliente, 'telefono2', None)
        )
        direccion = (
            obtener_campo_adicional(['DIRECCIÓN', 'DIRECCION', 'DIR'])
            or getattr(factura, 'direccion_comprador_xml', None)
            or getattr(cliente, 'direccion', None)
        )

        campos = []
        if email:
            campos.append(('Email', str(email).strip()[:300]))
        if telefono:
            campos.append(('Teléfono', str(telefono).strip()[:300]))
        if direccion:
            campos.append(('Dirección', self._limpiar_texto(direccion)))

        if not campos:
            return

        info_adicional = ET.SubElement(root, 'infoAdicional')
        for nombre, valor in campos[:15]:
            campo = ET.SubElement(info_adicional, 'campoAdicional')
            campo.set('nombre', nombre)
            campo.text = valor

    def _calcular_totales_impuestos_fallback(self):
        """Crea un impuesto mínimo para cumplir el XSD cuando no hay totales."""

        base = Decimal(str(getattr(self.nd, 'subtotal_sin_impuestos', 0) or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        valor = Decimal(str(getattr(self.nd, 'total_iva', 0) or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        tarifa = Decimal('0')
        if base > 0 and valor > 0:
            try:
                tarifa = (valor / base * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                tarifa = Decimal('0')

        codigo_porcentaje = self._codigo_porcentaje_por_tarifa(tarifa)

        class _Tmp:
            pass

        tmp = _Tmp()
        tmp.codigo = '2'
        tmp.codigo_porcentaje = codigo_porcentaje
        tmp.tarifa = tarifa
        tmp.base_imponible = base
        tmp.valor = valor
        return [tmp]

    # ============================= HELPERS =============================
    def _limpiar_texto(self, texto) -> str:
        if not texto:
            return ''
        texto = str(texto).replace('\n', ' ').replace('\r', ' ')
        texto = ''.join(char for char in texto if ord(char) >= 32)
        return texto.strip()[:300]

    def _formatear_decimal(self, valor, decimales: int = 2) -> str:
        try:
            valor_dec = Decimal(str(valor))
        except Exception:
            valor_dec = Decimal('0.00')
        cuantizador = Decimal('1.' + ('0' * decimales))
        return str(valor_dec.quantize(cuantizador, rounding=ROUND_HALF_UP))

    def _codigo_porcentaje_por_tarifa(self, tarifa: Decimal) -> str:
        # Mapeo coherente con CrearNotaDebito._get_codigo_porcentaje
        try:
            tarifa = Decimal(str(tarifa))
        except Exception:
            tarifa = Decimal('0')
        if tarifa == Decimal('0'):
            return '0'
        if tarifa == Decimal('5'):
            return '5'
        if tarifa == Decimal('13'):
            return '10'
        if tarifa == Decimal('14'):
            return '3'
        if tarifa in (Decimal('12'), Decimal('15')):
            return '4'
        return '4'

    def _calcular_totales_impuestos_desde_detalles(self):
        """Fallback: agrupa impuestos desde detalles si no existen totales_impuestos."""
        grupos = {}
        for d in self.nd.detalles.all():
            tarifa = Decimal(str(getattr(d, 'tarifa_iva', 0) or 0))
            codigo_porcentaje = self._codigo_porcentaje_por_tarifa(tarifa)
            key = (codigo_porcentaje, str(tarifa))
            if key not in grupos:
                grupos[key] = {'codigo': '2', 'codigo_porcentaje': codigo_porcentaje, 'tarifa': tarifa, 'base_imponible': Decimal('0.00'), 'valor': Decimal('0.00')}
            grupos[key]['base_imponible'] += Decimal(str(getattr(d, 'base_imponible', 0) or 0))
            grupos[key]['valor'] += Decimal(str(getattr(d, 'valor_iva', 0) or 0))

        class _Tmp:
            pass

        totales = []
        for _k, data in grupos.items():
            tmp = _Tmp()
            tmp.codigo = data['codigo']
            tmp.codigo_porcentaje = data['codigo_porcentaje']
            tmp.tarifa = data['tarifa']
            tmp.base_imponible = data['base_imponible'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tmp.valor = data['valor'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            totales.append(tmp)
        return totales
