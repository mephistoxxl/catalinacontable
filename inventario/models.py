from django.db import models
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    MinLengthValidator,
    MaxLengthValidator,
    RegexValidator,
)
import logging
import datetime
from django.utils import timezone
from .crypto_utils import EncryptedCharField
# MODELOS

# --------------------------------USUARIO------------------------------------------------
class Usuario(AbstractUser):
    # id
    username = models.CharField(max_length=80, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    first_name = models.CharField(max_length=40)
    last_name = models.CharField(max_length=60)
    nivel = models.IntegerField(null=True)
    empresas = models.ManyToManyField(
        'Empresa',
        through='UsuarioEmpresa',
        related_name='usuarios',
        blank=True,
    )

    @classmethod
    def numeroRegistrados(cls, empresa_id=None):
        """Devuelve el número de usuarios registrados.

        Si ``empresa_id`` es proporcionado, cuenta únicamente los usuarios
        asociados a esa empresa específica.
        """
        usuarios = cls.objects.all()
        if empresa_id is not None:
            usuarios = usuarios.filter(empresas__id=empresa_id).distinct()
        return int(usuarios.count())

    @classmethod
    def numeroUsuarios(cls, tipo, empresa_id=None):
        """Cuenta usuarios por tipo (administrador/usuario) opcionalmente
        filtrando por empresa."""
        usuarios = cls.objects.all()
        if empresa_id is not None:
            usuarios = usuarios.filter(empresas__id=empresa_id)
        if tipo == 'administrador':
            usuarios = usuarios.filter(is_superuser=True)
        elif tipo == 'usuario':
            usuarios = usuarios.filter(is_superuser=False)
        return int(usuarios.distinct().count())

from django.core.exceptions import ValidationError  # ← Y ESTA TAMBIÉN


class Empresa(models.Model):
    ruc = models.CharField(
        max_length=13,
        unique=True,
        validators=[RegexValidator(r'^\d{13}$', 'El RUC debe tener exactamente 13 dígitos')],
    )
    razon_social = models.CharField(max_length=300)

    def __str__(self):
        return f"{self.razon_social} ({self.ruc})"


class UsuarioEmpresa(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('usuario', 'empresa')


class Opciones(models.Model):
    # INFORMACIÓN BÁSICA EMPRESA
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='opciones',
        null=True,
        blank=True,
    )
    identificacion = models.CharField(
        max_length=13,
        unique=True,
        validators=[RegexValidator(r'^\d{13}$', 'El RUC debe tener exactamente 13 dígitos')],
        default='0000000000000',
        help_text='RUC de 13 dígitos de su empresa'
    )
    AGENTE_RETENCION_CHOICES = [
        ('...', '...'),
        ('NAC-GTRRIOC21-00000001', 'NAC-GTRRIOC21-00000001'),
        ('NAC-GTRRIOC22-00000001', 'NAC-GTRRIOC22-00000001'),
        ('NAC-GTRRIOC22-00000003', 'NAC-GTRRIOC22-00000003'),
        ('NAC-DGERCGC24-00000014', 'NAC-DGERCGC24-00000014'),
        ('NAC-DGERCGC25-00000010', 'NAC-DGERCGC25-00000010'),
    ]
    # === FIRMA ELECTRÓNICA (SUPER SEGURO) ===
    firma_electronica = models.FileField(
        upload_to='firmas/',
        null=True,
        blank=True,
        help_text='Archivo de firma electrónica (.p12 o .pfx). Se almacena cifrado y nunca se expone públicamente.'
    )
    password_firma = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Contraseña de la firma electrónica (almacenada cifrada).'
    )
    fecha_caducidad_firma = models.DateField(
        null=True,
        blank=True,
        help_text='Fecha de caducidad del certificado de firma electrónica'
    )

    # ...existing code...
    def save(self, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        self.full_clean()
        logger.info("Guardando instancia Opciones...")
        is_new_file = False
        if self.pk:
            try:
                old = Opciones.objects.get(pk=self.pk)
                if old.firma_electronica != self.firma_electronica:
                    is_new_file = True
            except Opciones.DoesNotExist:
                is_new_file = True
        else:
            is_new_file = True
        super().save(*args, **kwargs)
        # Solo procesar si hay archivo y contraseña, y si el archivo es nuevo o la fecha no está
        if self.firma_electronica and self.password_firma and (is_new_file or not self.fecha_caducidad_firma):
            try:
                logger.info(f"Procesando archivo de firma: {self.firma_electronica.name}")
                from cryptography.hazmat.primitives.serialization import pkcs12
                from cryptography.hazmat.backends import default_backend
                with self.firma_electronica.open('rb') as f:
                    p12_data = f.read()
                password = self.password_firma.encode()
                try:
                    private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                        p12_data, password, backend=default_backend()
                    )
                except ValueError as ve:
                    logger.error(f"Contraseña incorrecta para la firma electrónica: {ve}")
                    from django.core.exceptions import ValidationError
                    raise ValidationError({'password_firma': 'La contraseña de la firma electrónica es incorrecta.'})
                except Exception as e:
                    logger.error(f"Archivo de firma electrónica inválido o corrupto: {e}")
                    from django.core.exceptions import ValidationError
                    raise ValidationError({'firma_electronica': 'El archivo de firma electrónica es inválido o está corrupto.'})
                if certificate:
                    self.fecha_caducidad_firma = certificate.not_valid_after.date()
                    logger.info(f"Fecha de caducidad extraída: {self.fecha_caducidad_firma}")
                    Opciones.objects.filter(pk=self.pk).update(fecha_caducidad_firma=self.fecha_caducidad_firma)
                else:
                    logger.error("No se encontró certificado en el archivo de firma electrónica.")
                    from django.core.exceptions import ValidationError
                    raise ValidationError({'firma_electronica': 'No se encontró certificado en el archivo de firma electrónica.'})
            except ValidationError as ve:
                raise ve
            except Exception as e:
                logger.error(f"Error inesperado extrayendo fecha de caducidad: {e}")
                from django.core.exceptions import ValidationError
                raise ValidationError({'__all__': 'No se pudo extraer la fecha de caducidad. Verifique el archivo y la contraseña.'})
    # Opcional: método para obtener la ruta segura del archivo
    def get_firma_path(self):
        if self.firma_electronica:
            return self.firma_electronica.path
        return None

    razon_social = models.CharField(
        max_length=300, 
        default='[CONFIGURAR RAZÓN SOCIAL]',
        help_text='Razón social según consta en el RUC'
    )
    
    nombre_comercial = models.CharField(
        max_length=300, 
        default='[CONFIGURAR NOMBRE COMERCIAL]',
        help_text='Nombre comercial de su empresa (opcional)'
    )
    
    direccion_establecimiento = models.TextField(
        max_length=300, 
        default='[CONFIGURAR DIRECCIÓN]',
        help_text='Dirección principal matriz de su empresa'
    )
    
    correo = models.EmailField(
        max_length=100, 
        default='configurar@empresa.com',
        help_text='Email principal de su empresa'
    )
    
    telefono = models.CharField(
        max_length=20, 
        default='0000000000',
        help_text='Teléfono principal de contacto'
    )
    
    # INFORMACIÓN TRIBUTARIA
    obligado = models.CharField(
        max_length=2, 
        choices=[('SI', 'SÍ'), ('NO', 'NO')], 
        default='SI',
        help_text='¿Está obligado a llevar contabilidad?'
    )
    
    tipo_regimen = models.CharField(
        max_length=20, 
        choices=[
            ('GENERAL', 'Régimen General'), 
            ('RIMPE', 'RIMPE - Emprendedores')
        ],
        default='GENERAL',
        help_text='Tipo de régimen tributario'
    )
    
    # CAMPOS CONDICIONALES SRI (solo si aplica)
    es_contribuyente_especial = models.BooleanField(
        default=False,
        help_text='¿Su empresa es contribuyente especial?'
    )
    
    numero_contribuyente_especial = models.CharField(
        max_length=13, 
        blank=True, 
        null=True,
        help_text='Número de resolución de contribuyente especial'
    )
    imagen = models.ImageField(upload_to='logos/', blank=True, null=True)

    es_agente_retencion = models.BooleanField(
        default=False,
        help_text='¿Su empresa es agente de retención?'
    )

    numero_agente_retencion = models.CharField(
        max_length=30,
        choices=AGENTE_RETENCION_CHOICES,
        blank=True,
        null=True,
        help_text='Número de resolución de agente de retención'
    )
    
    # CONFIGURACIÓN FACTURACIÓN
    valor_iva = models.IntegerField(
        default=15,
        unique=True,
        help_text='Porcentaje de IVA vigente en Ecuador'
    )
    
    moneda = models.CharField(
        max_length=20, 
        default='DOLAR',
        help_text='Moneda oficial (DOLAR para Ecuador)'
    )
    
    # PERSONALIZACIÓN
    nombre_negocio = models.CharField(
        max_length=25, 
        null=True, 
        blank=True,
        default='Mi Negocio',
        help_text='Nombre corto para mostrar en reportes'
    )
    
    mensaje_factura = models.TextField(
        null=True, 
        blank=True,
        default='Gracias por su compra',
        help_text='Mensaje que aparece en las facturas'
    )

    # CONFIGURACIÓN TÉCNICA SRI (VALORES FIJOS - NO EDITABLES POR USUARIO)
    AMBIENTE_CHOICES = [
        ('1', 'Pruebas'),
        ('2', 'Producción'),
    ]

    tipo_ambiente = models.CharField(
        max_length=1,
        choices=AMBIENTE_CHOICES,
        default='1',
        help_text='Ambiente: 1=Pruebas, 2=Producción (Solo técnicos)'
    )


    tipo_emision = models.CharField(
        max_length=1,
        default='1',  # SIEMPRE 1 para método offline
        help_text='Tipo emisión: 1=Normal (único permitido en método offline)'
    )

    # MÉTODOS ÚTILES PARA XML:
    @property
    def ambiente_descripcion(self):
        """Descripción del ambiente para mostrar"""
        return 'PRUEBAS' if self.tipo_ambiente == '1' else 'PRODUCCIÓN'

    @property
    def direccion_establecimiento_xml(self):
        """Dirección del establecimiento (usa la misma dirección matriz)"""
        return self.direccion_establecimiento
    
    def clean(self):
        """Validaciones personalizadas"""
        # Validar que no use valores por defecto
        if self.identificacion == '0000000000000':
            raise ValidationError('Debe configurar un RUC válido')
        
        if '[CONFIGURAR' in self.razon_social:
            raise ValidationError('Debe configurar la razón social')
        
        if '[CONFIGURAR' in self.direccion_establecimiento:
            raise ValidationError('Debe configurar la dirección')
        
        if self.correo == 'configurar@empresa.com':
            raise ValidationError('Debe configurar un email válido')
        
        # Validar campos condicionales
        if self.es_contribuyente_especial and not self.numero_contribuyente_especial:
            raise ValidationError('Si es contribuyente especial, debe ingresar el número de resolución')
        
        if self.es_agente_retencion and not self.numero_agente_retencion:
            raise ValidationError('Si es agente de retención, debe ingresar el número de resolución')
        
        # Limpiar campos condicionales si no aplican
        if not self.es_contribuyente_especial:
            self.numero_contribuyente_especial = None
        
        if not self.es_agente_retencion:
            self.numero_agente_retencion = None
    
def save(self, *args, **kwargs):
    import logging
    import os
    logger = logging.getLogger(__name__)
    is_new_file = False
    if self.pk:
        try:
            old = Opciones.objects.get(pk=self.pk)
            if old.firma_electronica != self.firma_electronica:
                is_new_file = True
        except Opciones.DoesNotExist:
            is_new_file = True
    else:
        is_new_file = True

    # Guarda primero para asegurar que el archivo esté en disco
    super().save(*args, **kwargs)

    # Solo procesar si hay archivo y contraseña, y si el archivo es nuevo o la fecha no está
    if self.firma_electronica and self.password_firma and (is_new_file or not self.fecha_caducidad_firma):
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography.hazmat.backends import default_backend
            if os.path.exists(self.firma_electronica.path):
                with self.firma_electronica.open('rb') as f:
                    p12_data = f.read()
                password = self.password_firma.encode()
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    p12_data, password, backend=default_backend()
                )
                if certificate:
                    self.fecha_caducidad_firma = certificate.not_valid_after.date()
                    # Actualiza solo la fecha sin recursión infinita
                    Opciones.objects.filter(pk=self.pk).update(fecha_caducidad_firma=self.fecha_caducidad_firma)
            else:
                logger.error("El archivo de firma electrónica no existe en disco.")
        except Exception as e:
            logger.error(f"Error procesando la firma electrónica: {e}")
            # No actualiza la fecha si hay error
            pass
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def esta_configurado(self):
        """Verifica si la empresa está completamente configurada"""
        return (
            self.identificacion != '0000000000000' and
            '[CONFIGURAR' not in self.razon_social and
            '[CONFIGURAR' not in self.direccion_establecimiento and
            self.correo != 'configurar@empresa.com' and
            self.telefono != '0000000000'
        )
    
    @property
    def ruc(self):
        """Alias para compatibilidad con generador XML"""
        return self.identificacion
    
    @property
    def contribuyente_especial(self):
        """Devuelve el número si es contribuyente especial, sino None"""
        return self.numero_contribuyente_especial if self.es_contribuyente_especial else None
    
    @property
    def agente_retencion(self):
        """Devuelve el número si es agente de retención, sino None"""
        return self.numero_agente_retencion if self.es_agente_retencion else None
    
    @property
    def obligado_contabilidad_xml(self):
        """Mapea obligado contabilidad para XML"""
        return self.obligado

    @property
    def contribuyente_especial_xml(self):
        """Devuelve número si es contribuyente especial, sino None"""
        return self.numero_contribuyente_especial if self.es_contribuyente_especial else None

    @property
    def agente_retencion_xml(self):
        """Devuelve número si es agente de retención, sino None"""
        return self.numero_agente_retencion if self.es_agente_retencion else None

    @property
    def ruc_formatted(self):
        """RUC con 13 dígitos para XML"""
        return f"{self.identificacion:0>13}"

    @property
    def ambiente_descripcion_xml(self):
        """Descripción del ambiente para XML"""
        return 'PRUEBAS' if self.tipo_ambiente == '1' else 'PRODUCCION'
    
    class Meta:
        verbose_name = "Configuración de Empresa"
        verbose_name_plural = "Configuración de Empresa"
    
    def __str__(self):
        return f"{self.razon_social} - {self.identificacion}"
# ---------------------------------------------------------------------------------------


# -------------------------------PRODUCTO------------------------------------------------
from decimal import Decimal
from django.db import models

class Producto(models.Model):
    decisiones = [('1', 'Unidad'), ('2', 'Kilo'), ('3', 'Litro'), ('4', 'Otros')]
    
    # ✅ CORREGIDO: Mapeo exacto según tabla 17 SRI v2.31
    tiposIVA = [
        ('0', '0%'),           # Código SRI: 0
        ('5', '5%'),           # Código SRI: 5  
        ('2', '12%'),          # Código SRI: 2 (más común en Ecuador)
        ('10', '13%'),         # Código SRI: 10 ✅ CORREGIDO (antes era '1')
        ('3', '14%'),          # Código SRI: 3
        ('4', '15%'),          # Código SRI: 4
        ('6', 'No Objeto'),    # Código SRI: 6
        ('7', 'Exento de IVA'), # Código SRI: 7
        ('8', 'IVA Diferenciado') # Código SRI: 8 (solo turismo) ✅ CORREGIDO
    ]

    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='productos',
        null=False,
        blank=False,
    )
    codigo = models.CharField(max_length=20)
    codigo_barras = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=40)
    precio = models.DecimalField(max_digits=9, decimal_places=2)
    precio2 = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    disponible = models.IntegerField(null=True)
    categoria = models.CharField(max_length=20, choices=decisiones)
    iva = models.CharField(max_length=10, choices=tiposIVA)
    costo_actual = models.DecimalField(max_digits=9, decimal_places=2)
    
    # Campos calculados para el precio con IVA
    precio_iva1 = models.DecimalField(max_digits=9, decimal_places=2, editable=False, default=0)
    precio_iva2 = models.DecimalField(max_digits=9, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        # ✅ CORREGIDO: Cálculo correcto del IVA usando mapeo SRI
        # Mapeo para obtener porcentaje real desde código SRI
        MAPEO_IVA_PORCENTAJES = {
            '0': 0.00,    # 0%
            '5': 0.05,    # 5%
            '2': 0.12,    # 12%
            '10': 0.13,   # 13% ✅ CORREGIDO
            '3': 0.14,    # 14%
            '4': 0.15,    # 15%
            '6': 0.00,    # No objeto
            '7': 0.00,    # Exento
            '8': 0.08,    # IVA diferenciado 8%
        }
        
        iva_percent = Decimal(str(MAPEO_IVA_PORCENTAJES.get(self.iva, 0.00)))
        
        # Calculamos los precios con IVA
        self.precio_iva1 = self.precio * (Decimal('1.00') + iva_percent)
        if self.precio2:
            self.precio_iva2 = self.precio2 * (Decimal('1.00') + iva_percent)
        
        super(Producto, self).save(*args, **kwargs)

    # ✅ NUEVOS MÉTODOS ÚTILES PARA SRI
    def get_porcentaje_iva_real(self):
        """Retorna el porcentaje de IVA real para este producto"""
        MAPEO_IVA_PORCENTAJES = {
            '0': 0.00, '5': 5.00, '2': 12.00, '10': 13.00,
            '3': 14.00, '4': 15.00, '6': 0.00, '7': 0.00, '8': 8.00
        }
        return MAPEO_IVA_PORCENTAJES.get(self.iva, 0.00)
    
    def get_codigo_sri_iva(self):
        """Retorna el código SRI correcto para el XML"""
        return self.iva  # Ya está en formato correcto
    
    def get_descripcion_iva(self):
        """Retorna la descripción del IVA"""
        return dict(self.tiposIVA).get(self.iva, '0%')
    
    def calcular_iva_valor(self, base_imponible):
        """Calcula el valor del IVA sobre una base imponible"""
        porcentaje = self.get_porcentaje_iva_real() / 100
        return Decimal(str(base_imponible)) * Decimal(str(porcentaje))

    # ✅ MÉTODOS EXISTENTES (sin cambios)
    @classmethod
    def numeroRegistrados(cls, empresa_id=None):
        """Cuenta productos registrados opcionalmente filtrando por empresa."""
        productos = cls.objects.all()
        if empresa_id is not None:
            productos = productos.filter(empresa_id=empresa_id)
        return int(productos.count())

    @classmethod
    def productosRegistrados(cls):
        objetos = cls.objects.all().order_by('descripcion')
        return objetos

    @classmethod
    def preciosProductos(cls):
        objetos = cls.objects.all().order_by('id')
        arreglo = []
        etiqueta = True
        extra = 1

        for indice, objeto in enumerate(objetos):
            arreglo.append([])
            if etiqueta:
                arreglo[indice].append(0)
                arreglo[indice].append("------")
                etiqueta = False
                arreglo.append([])

            arreglo[indice + extra].append(objeto.id)
            precio_producto = objeto.precio
            arreglo[indice + extra].append("%d" % (precio_producto))

        return arreglo

    @classmethod
    def productosDisponibles(cls):
        objetos = cls.objects.all().order_by('id')
        arreglo = []
        etiqueta = True
        extra = 1

        for indice, objeto in enumerate(objetos):
            arreglo.append([])
            if etiqueta:
                arreglo[indice].append(0)
                arreglo[indice].append("------")
                etiqueta = False
                arreglo.append([])

            arreglo[indice + extra].append(objeto.id)
            productos_disponibles = objeto.disponible
            arreglo[indice + extra].append("%d" % (productos_disponibles))

        return arreglo

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['descripcion']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='unique_codigo_por_empresa')
        ]
    # ---------------------------------------------------------------------------------------


# ------------------------------------------CLIENTE--------------------------------------
class Cliente(models.Model):
    TIPO_IDENTIFICACION_CHOICES = [
        ('04', 'RUC'),
        ('05', 'Cédula'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del Exterior'),
    ]
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='clientes',
        null=False,
        blank=False,
    )
    tipoIdentificacion = models.CharField(max_length=2, choices=TIPO_IDENTIFICACION_CHOICES)
    identificacion = models.CharField(max_length=13)
    razon_social = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200, blank=True, null=True)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    correo = models.CharField(max_length=100)
    observaciones = models.CharField(max_length=300, blank=True, null=True)
    convencional = models.CharField(max_length=100, blank=True, null=True)
    tipoVenta = models.CharField(max_length=2, choices=[
        ('1', 'Local'),
        ('2', 'Exportación'),
    ])
    tipoRegimen = models.CharField(max_length=3, choices=[
        ('1', 'General'),
        ('2', 'Rimpe - Emprendedores'),
        ('3', 'Rimpe - Negocios Populares'),
    ])
    tipoCliente = models.CharField(max_length=2, choices=[
        ('1', 'Persona Natural'),
        ('2', 'Sociedad'),
    ])

    @classmethod
    def numeroRegistrados(cls, empresa_id=None):
        """Cuenta clientes registrados opcionalmente filtrando por empresa."""
        clientes = cls.objects.all()
        if empresa_id is not None:
            clientes = clientes.filter(empresa_id=empresa_id)
        return int(clientes.count())

    @classmethod
    def cedulasRegistradas(self):
        objetos = self.objects.all().order_by('razon_social')
        arreglo = []
        for indice, objeto in enumerate(objetos):
            arreglo.append([])
            arreglo[indice].append(objeto.identificacion)
            nombre_cliente = objeto.razon_social + " " + (objeto.nombre_comercial if objeto.nombre_comercial else '')
            arreglo[indice].append("%s. ID: %s" % (nombre_cliente, self.formatearIdentificacion(objeto.identificacion)))

        return arreglo

    @staticmethod
    def formatearIdentificacion(identificacion):
        return format(int(identificacion), ',d')
    # -----------------------------------------------------------------------------------------

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'identificacion'], name='unique_identificacion_por_empresa')
        ]


# -------------------------------------FACTURA---------------------------------------------
from django.db import models
import datetime

from django.db import models
import datetime


class Factura(models.Model):
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='facturas',
        null=False,
        blank=False,
    )
    # Relación con el cliente usando su identificación
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)

    # Almacén relacionado con la factura
    almacen = models.ForeignKey('Almacen', on_delete=models.CASCADE, null=True, blank=True)

    # Relación con el facturador que emite (CRÍTICO para control descuentos)
    facturador = models.ForeignKey(
        'Facturador', 
        on_delete=models.PROTECT,
        related_name='facturas',
        verbose_name='Facturador',
        help_text="Facturador que emite la factura"
    )

    # Fechas de emisión y vencimiento
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()

    # Establecimiento, Punto de Emisión y Secuencia
    establecimiento = models.CharField(max_length=3, verbose_name="Código de establecimiento")
    punto_emision = models.CharField(max_length=3, verbose_name="Punto de emisión")
    secuencia = models.CharField(max_length=9, verbose_name="Número secuencial")

    # Concepto y datos del cliente
    concepto = models.CharField(max_length=255, blank=True, null=True)
    identificacion_cliente = models.CharField(max_length=13)  # RUC o cédula
    nombre_cliente = models.CharField(max_length=100)

    # Montos
    sub_monto = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    base_imponible = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    monto_general = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    # ✅ NUEVO: OBLIGATORIO según XSD
    total_descuento = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Total de descuentos aplicados (OBLIGATORIO en XSD)"
    )

    # ✅ NUEVO: Campos opcionales según XSD
    propina = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Propina (opcional según XSD)"
    )

    placa = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Placa del vehículo (opcional, obligatorio para combustibles)"
    )

    guia_remision = models.CharField(
        max_length=17,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\d{3}-\d{3}-\d{9}$', 'Formato: 001-001-000000001')],
        help_text="Guía de remisión (opcional)"
    )

    valor_retencion_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Valor de retención de IVA (opcional)"
    )

    valor_retencion_renta = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Valor de retención en la fuente (opcional)"
    )

    total_subsidio = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Total de subsidios aplicados (opcional)"
    )

    # Clave de acceso para la facturación electrónica
    clave_acceso = models.CharField(max_length=49, unique=True, blank=True, null=True)

    # Estado interno del flujo de la factura
    estado = models.CharField(
        max_length=20,
        default='PENDIENTE',
        choices=[
            ('PENDIENTE', 'Pendiente'),
            ('RECIBIDA', 'Recibida'),
            ('AUTORIZADO', 'Autorizado'),
            ('RECHAZADO', 'Rechazado'),
            ('ERROR', 'Error')
        ],
        help_text="Estado interno del flujo"
    )

    # ✅ CAMPOS SRI PARA TRACKING COMPLETO DE AUTORIZACIÓN
    numero_autorizacion = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Número de autorización del SRI"
    )
    fecha_autorizacion = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Fecha y hora de autorización del SRI"
    )
    estado_sri = models.CharField(
        max_length=20, 
        default='',
        blank=True,
        choices=[
            ('', 'Local - No enviado al SRI'),
            ('PENDIENTE', 'Pendiente'),
            ('RECIBIDA', 'Recibida por SRI'),
            ('AUTORIZADA', 'Autorizada'),
            ('RECHAZADA', 'Rechazada'),
            ('ERROR', 'Error en procesamiento')
        ],
        help_text="Estado de la factura en el SRI"
    )
    mensaje_sri = models.TextField(
        blank=True, 
        null=True,
        help_text="Mensaje principal del SRI"
    )
    mensaje_sri_detalle = models.TextField(
        blank=True, 
        null=True,
        help_text="Detalle completo de mensajes del SRI"
    )
    xml_autorizado = models.TextField(
        blank=True, 
        null=True,
        help_text="XML autorizado devuelto por el SRI"
    )
    ride_autorizado = models.FileField(
        upload_to='rides/',
        blank=True,
        null=True,
        help_text="RIDE (PDF) autorizado"
    )

    # ✅ VALIDACIONES de descuento
    def clean(self):
        """Validaciones de descuento total de factura"""
        from django.core.exceptions import ValidationError
        
        if self.facturador and self.total_descuento > 0:
            # Calcular el porcentaje total de descuento
            if self.sub_monto > 0:
                porcentaje_total = (self.total_descuento / self.sub_monto) * 100
                
                if porcentaje_total > self.facturador.descuento_permitido:
                    raise ValidationError({
                        'total_descuento': f'El descuento total ({porcentaje_total:.2f}%) excede '
                                         f'el máximo permitido ({self.facturador.descuento_permitido}%) '
                                         f'para {self.facturador.nombres}'
                    })

    # ✅ MÉTODO para calcular totales automáticamente
    def calcular_totales(self):
        """Método para calcular automáticamente los totales de la factura"""
        from django.db.models import Sum
        from decimal import Decimal, ROUND_HALF_UP

        # Verificar si la factura tiene un ID antes de acceder a relaciones
        if not self.pk:
            self.total_descuento = Decimal('0.00')
            self.sub_monto = Decimal('0.00')
            self.monto_general = (Decimal('0.00') + (self.propina or Decimal('0.00'))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            return

        # Sumar todos los descuentos de los detalles
        descuentos_detalles = self.detallefactura_set.aggregate(
            total_desc=Sum('descuento')
        )['total_desc'] or Decimal('0.00')

        # Actualizar el total_descuento de la factura con redondeo
        self.total_descuento = descuentos_detalles.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Recalcular subtotales con redondeo
        subtotal_acumulado = sum(detalle.sub_total for detalle in self.detallefactura_set.all())
        self.sub_monto = Decimal(subtotal_acumulado).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Calcular monto general con redondeo consistente
        base_total = self.sub_monto - self.total_descuento + (self.propina or Decimal('0.00'))
        self.monto_general = base_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # ✅ MÉTODO SAVE() ÚNICO Y CONSOLIDADO - REEMPLAZA AMBOS DUPLICADOS
    def save(self, *args, **kwargs):
        """
        ÚNICO método save() consolidado que incluye TODA la funcionalidad necesaria para XML SRI válido
        """
        
        # ========== FASE 1: AUTO-POBLAR DATOS DEL CLIENTE ==========
        if self.cliente:
            self.identificacion_cliente = self.cliente.identificacion
            self.nombre_cliente = self.cliente.razon_social
        
        # ========== FASE 2: GENERAR CLAVE DE ACCESO ÚNICA ==========
        if not self.clave_acceso:
            intentos = 0
            while intentos < 10:  # Limitar intentos para evitar bucle infinito
                clave_generada = self.generar_clave_acceso()
                if not Factura.objects.filter(clave_acceso=clave_generada).exclude(id=self.id).exists():
                    self.clave_acceso = clave_generada
                    break
                intentos += 1
            
            if not self.clave_acceso:
                raise ValueError("No se pudo generar una clave de acceso única después de 10 intentos")
        
        # ========== FASE 3: CÁLCULO DE TOTALES Y VALIDACIONES ANTES DE GUARDAR ==========
        # Calcular totales de impuestos sin guardar en DB aún
        total_impuestos_calculado = self._calcular_y_crear_totales_impuestos(save_to_db=False)
        
        # Actualizar monto_general con el total de impuestos calculado
        # Asegurarse de que sub_monto y propina estén actualizados antes de este cálculo
        self.calcular_totales() # Asegura que sub_monto, total_descuento y propina estén correctos
        self.monto_general = (
            self.sub_monto + total_impuestos_calculado + (self.propina or Decimal('0.00'))
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        try:
            self.full_clean()  # Ejecuta todas las validaciones del modelo
        except ValidationError as e:
            # Re-lanzar con información más clara
            raise ValidationError(f"Error de validación en factura: {e}")
        
        # ========== FASE 4: GUARDAR EN BASE DE DATOS ==========
        super().save(*args, **kwargs)
        
        # ========== FASE 5: CREAR TOTALES DE IMPUESTOS AUTOMÁTICAMENTE (AHORA SÍ EN DB) ==========
        # CRÍTICO: Esto debe ejecutarse DESPUÉS del save() para que exista el ID
        try:
            self.crear_totales_impuestos_automatico() # Esto ahora guarda los TotalImpuesto en DB
        except Exception as e:
            # Si hay error en impuestos, registrar pero no fallar el save principal
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creando totales de impuestos para factura {self.id}: {e}")

        # Asegurarse de que el monto_general en la instancia sea el mismo que se guardó
        # Esto es importante si el save() o el crear_totales_impuestos_automatico() lo modifican
        self.refresh_from_db()

    def generar_clave_acceso(self):
        """
        Genera la clave de acceso de 49 dígitos según estándar SRI Ecuador
        Formato: ddmmaaaa + codDoc + ruc + ambiente + serie + secuencial + códigoNumérico + tipoEmisión + dígitoVerificador
        """
        from datetime import datetime
        from random import randint

        # ✅ CORREGIDO: Solo fecha (8 dígitos) - ddmmaaaa (SRI no incluye hora en clave)
        fecha_emision = self.fecha_emision.strftime('%d%m%Y')
        
        # ✅ Tipo de comprobante (2 dígitos)
        tipo_comprobante = "01"  # 01 = Factura
        
        # ✅ CORREGIDO: Validar RUC desde configuración (13 dígitos)
        try:
            opciones = Opciones.objects.first()
            if not opciones or not opciones.identificacion or opciones.identificacion == '0000000000000':
                raise ValueError("RUC no configurado correctamente en Opciones")
            ruc_emisor = opciones.identificacion.zfill(13)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo RUC emisor: {e}")
            # Usar RUC por defecto para pruebas (NO usar en producción)
            ruc_emisor = "1707181374001"
        
        # ✅ Ambiente desde configuración (1 dígito)
        # 1 = Pruebas, 2 = Producción
        try:
            opciones = Opciones.objects.first()
            if opciones and opciones.tipo_ambiente in ['1', '2']:
                tipo_ambiente = opciones.tipo_ambiente
            else:
                tipo_ambiente = "1"
        except Exception:
            tipo_ambiente = "1"
        
        # ✅ Serie (6 dígitos) - establecimiento + punto emisión
        serie = f"{self.establecimiento.zfill(3)}{self.punto_emision.zfill(3)}"
        
        # ✅ Número secuencial (9 dígitos)
        numero_secuencial = self.secuencia.zfill(9)
        
        # ✅ Código numérico aleatorio (8 dígitos)
        codigo_numerico = str(randint(10000000, 99999999))
        
        # ✅ Tipo de emisión (1 dígito)
        tipo_emision = "1"  # 1 = Emisión normal

        # ✅ Construir clave base (48 dígitos)
        clave_base = (
            f"{fecha_emision}"       # 8 dígitos  (ddmmaaaa)
            f"{tipo_comprobante}"    # 2 dígitos  (01)
            f"{ruc_emisor}"         # 13 dígitos (RUC emisor)
            f"{tipo_ambiente}"      # 1 dígito   (1=pruebas, 2=producción)
            f"{serie}"              # 6 dígitos  (estab+pto emisión)
            f"{numero_secuencial}"  # 9 dígitos  (secuencial)
            f"{codigo_numerico}"    # 8 dígitos  (código aleatorio)
            f"{tipo_emision}"       # 1 dígito   (1=normal)
        )
        # Total: 48 dígitos + 1 verificador = 49 dígitos

        # ✅ CORREGIDO: Cálculo del dígito verificador (Módulo 11) según SRI
        clave_lista = [int(d) for d in clave_base]
        pesos = [2, 3, 4, 5, 6, 7]
        total = 0
        peso_index = 0

        # Recorrer de derecha a izquierda
        for digito in reversed(clave_lista):
            total += digito * pesos[peso_index]
            peso_index = (peso_index + 1) % len(pesos)

        residuo = total % 11
        digito_verificador = 11 - residuo
        
        # Casos especiales según normativa SRI
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1

        # ✅ Clave final (49 dígitos)
        clave_acceso = f"{clave_base}{digito_verificador}"
        
        # ✅ VALIDACIÓN: Verificar que tenga exactamente 49 dígitos
        if len(clave_acceso) != 49:
            logger = logging.getLogger(__name__)
            logger.error(f"Clave de acceso generada con longitud incorrecta: {len(clave_acceso)} dígitos")
            raise ValueError(f"Clave de acceso debe tener 49 dígitos, se generaron {len(clave_acceso)}")
        
        return clave_acceso

    # ✅ PROPERTIES PARA MAPEAR A NOMBRES XML
    @property
    def tipo_identificacion_comprador_xml(self):
        """Mapea tipoIdentificacion del cliente para XML"""
        return self.cliente.tipoIdentificacion if self.cliente else '07'

    @property
    def direccion_comprador_xml(self):
        """Mapea dirección del cliente para XML"""
        return self.cliente.direccion if self.cliente else ''

    @property
    def razon_social_comprador_xml(self):
        """Mapea razón social del cliente para XML"""
        return self.cliente.razon_social if self.cliente else self.nombre_cliente

    @property
    def total_sin_impuestos_xml(self):
        """OBLIGATORIO para XML: Total antes de impuestos"""
        return self.sub_monto

    @property
    def importe_total_xml(self):
        """OBLIGATORIO para XML: Total general de la factura"""
        return self.monto_general

    @property
    def moneda_xml(self):
        """Moneda para XML (siempre DOLAR en Ecuador)"""
        return 'DOLAR'

    @property
    def establecimiento_formatted(self):
        """Establecimiento con formato 001"""
        return f"{int(self.establecimiento):03d}"

    @property
    def punto_emision_formatted(self):
        """Punto emisión con formato 001"""
        return f"{int(self.punto_emision):03d}"

    @property
    def secuencia_formatted(self):
        """Secuencia con formato 000000001"""
        return f"{int(self.secuencia):09d}"
    
    @property
    def numero(self):
        """Número de factura completo formato 001-001-000000001"""
        return f"{self.establecimiento_formatted}-{self.punto_emision_formatted}-{self.secuencia_formatted}"
    
    @property
    def numero_factura(self):
        """Alias para numero - compatibilidad con código existente"""
        return self.numero
    
    @property
    def subtotal_12(self):
        return sum(float(ti.base_imponible) for ti in self.totales_impuestos.all() if ti.codigo == '2' and float(ti.tarifa) == 12)

    @property
    def subtotal_0(self):
        return sum(float(ti.base_imponible) for ti in self.totales_impuestos.all() if ti.codigo == '2' and float(ti.tarifa) == 0 and ti.codigo_porcentaje == '0')

    @property
    def subtotal_no_objeto_iva(self):
        return sum(float(ti.base_imponible) for ti in self.totales_impuestos.all() if ti.codigo == '2' and ti.codigo_porcentaje == '6')

    @property
    def subtotal_exento_iva(self):
        return sum(float(ti.base_imponible) for ti in self.totales_impuestos.all() if ti.codigo == '2' and ti.codigo_porcentaje == '7')

    @property
    def subtotal_sin_impuestos(self):
        return float(self.sub_monto)

    @property
    def descuento(self):
        return float(self.total_descuento)

    @property
    def ice(self):
        return sum(float(ti.valor) for ti in self.totales_impuestos.all() if ti.codigo == '3')

    @property
    def iva_12(self):
        return sum(float(ti.valor) for ti in self.totales_impuestos.all() if ti.codigo == '2' and float(ti.tarifa) == 12)

    @property
    def total(self):
        return float(self.monto_general)

    def sincronizar_formas_pago(self):
        """
        Sincroniza las formas de pago para que su suma total coincida exactamente con monto_general.
        Esto corrige discrepancias de redondeo y asegura coherencia para el XML SRI.
        """
        from decimal import Decimal
        
        # Si no hay formas de pago, crear una por defecto
        if not self.formas_pago.exists():
            FormaPago.objects.create(
                factura=self,
                forma_pago='20',  # Otros con utilización del sistema financiero
                total=self.monto_general
            )
            return f"✅ Forma de pago creada: ${self.monto_general}"
        
        # Calcular diferencia actual
        suma_pagos = sum(fp.total for fp in self.formas_pago.all())
        diferencia = self.monto_general - suma_pagos
        
        if diferencia == 0:
            return f"✅ Formas de pago ya sincronizadas: ${suma_pagos}"
        
        # Ajustar la primera forma de pago
        primera_forma_pago = self.formas_pago.first()
        nuevo_total = primera_forma_pago.total + diferencia
        
        # Asegurar que el nuevo total no sea negativo
        if nuevo_total < 0:
            # Si el nuevo total sería negativo, redistribuir entre todas las formas de pago
            primera_forma_pago.total = self.monto_general
            # Eliminar las demás formas de pago para evitar complicaciones
            self.formas_pago.exclude(id=primera_forma_pago.id).delete()
        else:
            primera_forma_pago.total = nuevo_total
        
        primera_forma_pago.save()
        
        return f"✅ Formas de pago sincronizadas. Diferencia corregida: ${diferencia}"

    def _calcular_y_crear_totales_impuestos(self, save_to_db=True):
        """
        Calcula y opcionalmente crea los TotalImpuesto.
        Retorna el total de impuestos calculado.
        """
        from collections import defaultdict
        from django.db.models import Sum
        from decimal import Decimal

        if save_to_db:
            self.totales_impuestos.all().delete() # Limpiar solo si vamos a guardar

        # Verificar si la factura tiene un ID antes de acceder a relaciones
        if not self.pk:
            return Decimal('0.00')

        if not self.detallefactura_set.exists():
            return Decimal('0.00')

        impuestos_agrupados = defaultdict(lambda: {
            'base_imponible': Decimal('0.00'),
            'valor': Decimal('0.00'),
            'tarifa': Decimal('0.00'),
            'count': 0
        })

        for detalle in self.detallefactura_set.all():
            for impuesto_detalle in detalle.impuestos_detalle.all():
                key = (impuesto_detalle.codigo, impuesto_detalle.codigo_porcentaje)
                impuestos_agrupados[key]['base_imponible'] += impuesto_detalle.base_imponible
                impuestos_agrupados[key]['valor'] += impuesto_detalle.valor
                impuestos_agrupados[key]['tarifa'] = impuesto_detalle.tarifa

        total_impuestos_calculado = Decimal('0.00')
        for (codigo, codigo_porcentaje), datos in impuestos_agrupados.items():
            total_impuestos_calculado += datos['valor']
            if save_to_db:
                TotalImpuesto.objects.create(
                    factura=self,
                    codigo=codigo,
                    codigo_porcentaje=codigo_porcentaje,
                    base_imponible=datos['base_imponible'],
                    valor=datos['valor'],
                    tarifa=datos['tarifa']
                )
        return total_impuestos_calculado

    # ✅ MÉTODO CRÍTICO: Crear automáticamente totales de impuestos
    def crear_totales_impuestos_automatico(self):
        """
        Wrapper para _calcular_y_crear_totales_impuestos que siempre guarda en DB.
        """
        self._calcular_y_crear_totales_impuestos(save_to_db=True)

    # ✅ MÉTODO: Verificar si la factura está lista para XML
    def esta_lista_para_xml(self):
        """Verifica si la factura cumple todos los requisitos para XML válido"""
        errores = []
        
        # Verificar si la factura tiene un ID antes de acceder a relaciones
        if not self.pk:
            errores.append("La factura no ha sido guardada aún")
            return False, errores
        
        # ✅ CRÍTICO: Refrescar desde DB MÚLTIPLES VECES para asegurar consistencia
        for intento in range(3):
            self.refresh_from_db()
            if self.formas_pago.exists():
                break
            if intento < 2:  # Solo hacer sleep en los primeros 2 intentos
                import time
                time.sleep(0.2)  # Esperar 200ms entre intentos
        
        # Verificar datos obligatorios
        if not self.cliente:
            errores.append("Falta asignar cliente")
        
        if not self.detallefactura_set.exists():
            errores.append("Falta agregar productos/servicios")
        
        # ✅ VERIFICACIÓN MEJORADA de formas de pago
        formas_pago_count = self.formas_pago.count()
        if formas_pago_count == 0:
            errores.append("Falta definir forma de pago")
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Formas de pago verificadas: {formas_pago_count}")
        
        if not self.totales_impuestos.exists():
            errores.append("Faltan calcular totales de impuestos")
        
        # Verificar configuración de empresa
        opciones = Opciones.objects.first()
        if (not opciones or
            getattr(opciones, 'identificacion', '0000000000000') == '0000000000000' or
            '[CONFIGURAR' in getattr(opciones, 'razon_social', '') or
            '[CONFIGURAR' in getattr(opciones, 'direccion_establecimiento', '') or
            getattr(opciones, 'correo', 'configurar@empresa.com') == 'configurar@empresa.com' or
            getattr(opciones, 'telefono', '0000000000') == '0000000000'):
            errores.append("Falta configurar datos de la empresa")
        
        return len(errores) == 0, errores

    def __str__(self):
        return f'Factura {self.establecimiento}-{self.punto_emision}-{self.secuencia}'

    @classmethod
    def numeroRegistrados(cls, empresa_id=None):
        facturas = cls.objects.all()
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)
        return facturas.count()

    @classmethod
    def ingresoTotal(cls, empresa_id=None):
        facturas = cls.objects.all()
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)
        return facturas.aggregate(total=models.Sum('monto_general'))['total'] or 0

    @classmethod
    def ventasUltimosMeses(cls, meses=6, empresa_id=None):
        """Obtiene las ventas de los últimos N meses"""
        from datetime import date, timedelta
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth

        fecha_limite = date.today() - timedelta(days=meses*30)

        facturas = cls.objects.filter(fecha_emision__gte=fecha_limite)
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)

        ventas_por_mes = facturas.annotate(
            mes=TruncMonth('fecha_emision')
        ).values('mes').annotate(
            total=Sum('monto_general')
        ).order_by('mes')
        
        return list(ventas_por_mes)

    @classmethod
    def ventasEsteMes(cls, empresa_id=None):
        """Obtiene el total de ventas del mes actual"""
        from datetime import date
        from django.db.models import Sum

        hoy = date.today()
        facturas = cls.objects.filter(
            fecha_emision__year=hoy.year,
            fecha_emision__month=hoy.month
        )
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)
        ventas_mes = facturas.aggregate(total=Sum('monto_general'))['total'] or 0

        return ventas_mes

    @classmethod
    def ventasMesAnterior(cls, empresa_id=None):
        """Obtiene el total de ventas del mes anterior"""
        from datetime import date
        from django.db.models import Sum

        hoy = date.today()
        if hoy.month == 1:
            mes_anterior = 12
            año_anterior = hoy.year - 1
        else:
            mes_anterior = hoy.month - 1
            año_anterior = hoy.year
            
        facturas = cls.objects.filter(
            fecha_emision__year=año_anterior,
            fecha_emision__month=mes_anterior
        )
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)
        ventas_mes_anterior = facturas.aggregate(total=Sum('monto_general'))['total'] or 0

        return ventas_mes_anterior

    @classmethod
    def promedioVentasMensuales(cls, meses=12, empresa_id=None):
        """Calcula el promedio de ventas de los últimos N meses"""
        from datetime import date, timedelta
        from django.db.models import Sum

        fecha_limite = date.today() - timedelta(days=meses*30)
        facturas = cls.objects.filter(fecha_emision__gte=fecha_limite)
        if empresa_id is not None:
            facturas = facturas.filter(empresa_id=empresa_id)
        total_ventas = facturas.aggregate(total=Sum('monto_general'))['total'] or 0

        return total_ventas / meses if meses > 0 else 0


class DetalleFactura(models.Model):
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='detalles_factura',
        null=True,
        blank=True,
    )
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE)
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE,null=True, blank=True)
    cantidad = models.IntegerField()
    sub_total = models.DecimalField(max_digits=20, decimal_places=2)
    servicio = models.ForeignKey('Servicio', on_delete=models.CASCADE, null=True, blank=True)

    total = models.DecimalField(max_digits=20, decimal_places=2)

    # ✅ NUEVO: OBLIGATORIO según XSD
    descuento = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text="Descuento aplicado a este ítem específico (OBLIGATORIO en XSD)"
    )

    # ✅ NUEVO: Para control interno de descuentos
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Porcentaje de descuento aplicado (0-100%)"
    )

    # ✅ NUEVO: OPCIONAL según XSD
    precio_sin_subsidio = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Precio sin subsidio para este ítem (opcional)"
    )

    # ✅ VALIDACIONES de descuento por ítem
    def clean(self):
        """Validaciones de descuento por ítem"""
        from django.core.exceptions import ValidationError
        
        if self.factura and self.factura.facturador:
            # Validar que el porcentaje no exceda el permitido
            descuento_maximo = self.factura.facturador.descuento_permitido
            
            if self.porcentaje_descuento > descuento_maximo:
                raise ValidationError({
                    'porcentaje_descuento': f'El descuento no puede exceder {descuento_maximo}% '
                                          f'(máximo permitido para {self.factura.facturador.nombres})'
                })
        
        # Validar que el descuento monetario coincida con el porcentaje
        if self.producto and self.cantidad:
            subtotal_sin_descuento = self.producto.precio * self.cantidad
            descuento_calculado = subtotal_sin_descuento * (self.porcentaje_descuento / 100)
            
            # Permitir pequeña diferencia por redondeo
            if abs(self.descuento - descuento_calculado) > 0.01:
                raise ValidationError({
                    'descuento': f'El descuento debe coincidir con el porcentaje aplicado. '
                               f'Calculado: ${descuento_calculado:.2f}'
                })

    # ✅ MÉTODO para aplicar descuento por porcentaje CON REDONDEO
    def aplicar_descuento_porcentaje(self, porcentaje):
        """Aplica un descuento por porcentaje validando límites CON REDONDEO"""
        from decimal import Decimal, ROUND_HALF_UP
        
        if not self.factura or not self.factura.facturador:
            raise ValueError("Debe asignar factura y facturador primero")
        
        if porcentaje > self.factura.facturador.descuento_permitido:
            raise ValueError(f"Descuento excede el máximo permitido ({self.factura.facturador.descuento_permitido}%)")
        
        # Redondear el porcentaje también
        self.porcentaje_descuento = Decimal(str(porcentaje)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # El save() calculará automáticamente el descuento monetario

    # ✅ MÉTODO para aplicar descuento por monto CON REDONDEO
    def aplicar_descuento_monto(self, monto):
        """Aplica un descuento por monto validando límites CON REDONDEO"""
        from decimal import Decimal, ROUND_HALF_UP
        
        if not self.producto or not self.cantidad:
            raise ValueError("Debe asignar producto y cantidad primero")
        
        subtotal = self.producto.precio * Decimal(str(self.cantidad))
        if subtotal > 0:
            porcentaje = (Decimal(str(monto)) / subtotal) * 100
            porcentaje_redondeado = porcentaje.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.aplicar_descuento_porcentaje(float(porcentaje_redondeado))
        else:
            raise ValueError("El subtotal debe ser mayor a cero para aplicar descuento")

    # ✅ MÉTODO SAVE() ÚNICO Y CONSOLIDADO CON REDONDEO - SOLUCIONA EL ERROR
    def save(self, *args, **kwargs):
        """
        ÚNICO método save() consolidado para DetalleFactura
        CRÍTICO: Incluye cálculos automáticos + creación de impuestos + REDONDEO
        """
        from decimal import Decimal, ROUND_HALF_UP
        from django.core.exceptions import ValidationError
        
        # ========== FASE 1: VALIDAR DATOS BÁSICOS ==========
        if not (self.producto or self.servicio):
            raise ValueError("Debe asignar producto o servicio al detalle")
        if not self.cantidad or self.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        # ========== FASE 2: CALCULAR DESCUENTOS Y SUBTOTALES CON REDONDEO ==========
        if self.producto:
            precio_unitario = self.producto.precio
        elif self.servicio:
            precio_unitario = self.servicio.precio1
        else:
            precio_unitario = Decimal('0.00')

        if self.porcentaje_descuento is not None and self.porcentaje_descuento >= 0:
            subtotal_sin_descuento = precio_unitario * Decimal(str(self.cantidad))
            descuento_calculado = subtotal_sin_descuento * (Decimal(str(self.porcentaje_descuento)) / 100)
            self.descuento = descuento_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sub_total_calculado = subtotal_sin_descuento - self.descuento
            self.sub_total = sub_total_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            subtotal_calculado = precio_unitario * Decimal(str(self.cantidad))
            self.sub_total = subtotal_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.descuento = Decimal('0.00')

        self.total = self.sub_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # ========== FASE 4: VALIDACIONES ANTES DE GUARDAR ==========
        try:
            self.full_clean()
        except ValidationError as e:
            raise ValidationError(f"Error de validación en detalle: {e}")

        super().save(*args, **kwargs)

        # ========== FASE 6: CREAR IMPUESTOS DEL DETALLE AUTOMÁTICAMENTE ==========
        try:
            self.crear_impuestos_detalle_automatico()
            total_impuestos = self.impuestos_detalle.aggregate(
                total=models.Sum('valor')
            )['total'] or Decimal('0.00')
            total_final = (self.sub_total + total_impuestos).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            DetalleFactura.objects.filter(id=self.id).update(total=total_final)
            self.total = total_final
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error creando impuestos para detalle {self.id}: {e}")
    @classmethod
    def productosVendidos(cls, empresa_id=None):
        vendidos = cls.objects.all()
        if empresa_id is not None:
            vendidos = vendidos.filter(empresa_id=empresa_id)
        totalVendidos = 0
        for producto in vendidos:
            totalVendidos += producto.cantidad
        return totalVendidos
    @classmethod
    def ultimasVentas(cls, empresa_id=None):
        ventas = cls.objects.all()
        if empresa_id is not None:
            ventas = ventas.filter(empresa_id=empresa_id)
        return ventas.order_by('-id')[:10]
    
    @classmethod
    def topProductosVendidos(cls, limite=5, empresa_id=None):
        """Obtiene los productos más vendidos con cantidad total"""
        from django.db.models import Sum

        productos_top = cls.objects.filter(
            producto__isnull=False
        )
        if empresa_id is not None:
            productos_top = productos_top.filter(empresa_id=empresa_id)
        productos_top = productos_top.values(
            'producto__descripcion',
            'producto__id'
        ).annotate(
            total_vendido=Sum('cantidad')
        ).order_by('-total_vendido')[:limite]

        return list(productos_top)
    # ✅ PROPERTIES para XML
    @property
    def precio_unitario_xml(self):
        """Precio unitario del producto/servicio para XML"""
        if self.producto:
            return self.producto.precio
        elif self.servicio:
            return self.servicio.precio1
        else:
            return Decimal('0.00')
    @property
    def precio_unitario(self):
        """Precio unitario real aplicado (incluye descuento si existe)"""
        if self.cantidad:
            return (self.sub_total + self.descuento) / self.cantidad
        return Decimal('0.00')

    @property
    def codigo_principal_xml(self):
        """Código principal del producto/servicio para XML"""
        if self.producto:
            return self.producto.codigo
        elif self.servicio:
            return self.servicio.codigo
        else:
            return ''

    @property
    def codigo_auxiliar_xml(self):
        """Código auxiliar del producto para XML"""
        return self.producto.codigo_barras if self.producto else ''

    @property
    def descripcion_xml(self):
        """Descripción del producto/servicio para XML"""
        if self.producto:
            return self.producto.descripcion
        elif self.servicio:
            return self.servicio.descripcion
        else:
            return ''

    @property
    def precio_total_sin_impuesto_xml(self):
        """Precio total sin impuestos para XML (OBLIGATORIO)"""
        return self.sub_total

    # ✅ MÉTODO CRÍTICO: Crear automáticamente impuestos del detalle CON REDONDEO
    def crear_impuestos_detalle_automatico(self):
        from decimal import Decimal, ROUND_HALF_UP

        # Limpiar impuestos existentes para evitar duplicados
        self.impuestos_detalle.all().delete()

        # === PRODUCTO ===
        if self.producto:
            codigo_iva_sri = self.producto.get_codigo_sri_iva()
            porcentaje_iva = self.producto.get_porcentaje_iva_real()
        # === SERVICIO ===
        elif self.servicio:
            codigo_iva_sri = self.servicio.iva
            MAPEO_IVA_PORCENTAJES = {
                '0': 0.00, '5': 5.00, '2': 12.00, '10': 13.00,
                '3': 14.00, '4': 15.00, '6': 0.00, '7': 0.00, '8': 8.00
            }
            porcentaje_iva = MAPEO_IVA_PORCENTAJES.get(self.servicio.iva, 0.00)
        else:
            return

        # Calcular valor del IVA CON REDONDEO
        if porcentaje_iva > 0:
            valor_iva = self.sub_total * (Decimal(str(porcentaje_iva)) / 100)
            valor_iva_redondeado = valor_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            valor_iva_redondeado = Decimal('0.00')

        # Crear ImpuestoDetalle para IVA CON REDONDEO
        ImpuestoDetalle.objects.create(
            detalle_factura=self,
            codigo='2',  # IVA siempre es código 2 según tabla 16 SRI
            codigo_porcentaje=codigo_iva_sri,
            tarifa=Decimal(str(porcentaje_iva)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            base_imponible=self.sub_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            valor=valor_iva_redondeado
        )

# ---------------------------------------------------------------------------------------


# ------------------------------------------PROVEEDOR-----------------------------------
class Proveedor(models.Model):
    # ✅ ACTUALIZADO: Mismos campos que Cliente para consistencia
    TIPO_IDENTIFICACION_CHOICES = [
        ('04', 'RUC'),
        ('05', 'Cédula'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del Exterior'),
    ]

    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='proveedores',
        null=True,
        blank=True,
    )

    tipoIdentificacion = models.CharField(max_length=2, choices=TIPO_IDENTIFICACION_CHOICES)
    identificacion_proveedor = models.CharField(max_length=13)  # ✅ Ampliado a 13
    razon_social_proveedor = models.CharField(max_length=200)  # ✅ Ampliado a 200
    nombre_comercial_proveedor = models.CharField(max_length=200, blank=True, null=True)  # ✅ Ampliado
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    telefono2 = models.CharField(max_length=20, blank=True, null=True)
    correo = models.CharField(max_length=100)
    correo2 = models.CharField(max_length=100, blank=True, null=True)
    
    # ✅ NUEVOS CAMPOS (copiados desde Cliente)
    observaciones = models.CharField(max_length=300, blank=True, null=True)
    convencional = models.CharField(max_length=100, blank=True, null=True)
    nacimiento = models.DateField(blank=True, null=True)  # ✅ Ahora opcional
    
    # ✅ NUEVOS CAMPOS EMPRESARIALES
    tipoVenta = models.CharField(max_length=2, choices=[
        ('1', 'Local'),
        ('2', 'Exportación'),
    ], default='1')
    
    tipoRegimen = models.CharField(max_length=3, choices=[
        ('1', 'General'),
        ('2', 'Rimpe - Emprendedores'),
        ('3', 'Rimpe - Negocios Populares'),
    ], default='1')
    
    tipoProveedor = models.CharField(max_length=2, choices=[
        ('1', 'Persona Natural'),
        ('2', 'Sociedad'),
    ], default='1')

    @classmethod
    def cedulasRegistradas(self):
        objetos = self.objects.all().order_by('razon_social_proveedor')
        arreglo = []
        for indice, objeto in enumerate(objetos):
            arreglo.append([])
            arreglo[indice].append(objeto.identificacion_proveedor)
            nombre_proveedor = objeto.razon_social_proveedor + " " + objeto.nombre_comercial_proveedor
            arreglo[indice].append("%s. C.I: %s" % (nombre_proveedor, self.formatearCedula(objeto.identificacion_proveedor)))

        return arreglo

    @staticmethod
    def formatearCedula(cedula):
        return format(int(cedula), ',d')
    # ---------------------------------------------------------------------------------------

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'identificacion_proveedor'], name='unique_proveedor_por_empresa')
        ]


# ----------------------------------------PEDIDO-----------------------------------------
class Pedido(models.Model):
    # id
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='pedidos',
        null=True,
        blank=True,
    )
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    fecha = models.DateField()
    sub_monto = models.DecimalField(max_digits=20, decimal_places=2)
    monto_general = models.DecimalField(max_digits=20, decimal_places=2)
    iva = models.ForeignKey(Opciones, to_field='valor_iva', on_delete=models.CASCADE)
    presente = models.BooleanField(null=True)

    @classmethod
    def recibido(self, pedido):
        return self.objects.get(id=pedido).presente


# ---------------------------------------------------------------------------------------


# -------------------------------------DETALLES DE PEDIDO-------------------------------
class DetallePedido(models.Model):
    # id
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='detalles_pedido',
        null=True,
        blank=True,
    )
    id_pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    id_producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    sub_total = models.DecimalField(max_digits=20, decimal_places=2)
    total = models.DecimalField(max_digits=20, decimal_places=2)


# ---------------------------------------------------------------------------------------


# ------------------------------------NOTIFICACIONES------------------------------------
class Notificaciones(models.Model):
    # id
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='notificaciones',
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(Usuario, to_field='username', on_delete=models.CASCADE)
    mensaje = models.TextField()


# ---------------------------------------------------------------------------------------

# ------------------------------------SECUENCIAS------------------------------------
class Secuencia(models.Model):
    id = models.AutoField(
        primary_key=True,
        verbose_name="ID"
    )

    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='secuencias',
        null=True,
        blank=True,
    )
    descripcion = models.CharField(
        max_length=100,
        verbose_name="Descripción"
    )

    tipo_documento = models.CharField(
        max_length=2,
        verbose_name="Tipo de Documento"
    )

    secuencial = models.IntegerField(
        verbose_name="Número Secuencial",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999999999)
        ]
    )

    establecimiento = models.IntegerField(
        verbose_name="Establecimiento",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999)
        ]
    )

    punto_emision = models.IntegerField(
        verbose_name="Punto de Emisión",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999)
        ]
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    iva = models.BooleanField(
        default=True,
        verbose_name="IVA"
    )

    fiscal = models.BooleanField(
        default=True,
        verbose_name="Fiscal"
    )

    documento_electronico = models.BooleanField(
        default=True,
        verbose_name="Documento Electrónico"
    )

    class Meta:
        verbose_name = "Secuencia"
        verbose_name_plural = "Secuencias"
        db_table = 'inventario_secuencias'
        unique_together = ('tipo_documento', 'establecimiento', 'punto_emision')

    def __str__(self):
        return f"{self.descripcion} - {self.tipo_documento} (Establecimiento: {self.establecimiento:03d}, Punto de Emisión: {self.punto_emision:03d})"

    def save(self, *args, **kwargs):
        # ✅ VALIDACIÓN CORREGIDA: Validar que el secuencial no exceda 9 dígitos
        if self.secuencial > 999999999:
            raise ValueError("El número secuencial no puede exceder los 9 dígitos.")
        
        # ✅ VALIDACIÓN CORREGIDA: Validar que establecimiento esté en el rango correcto (1-999)
        if self.establecimiento < 1 or self.establecimiento > 999:
            raise ValueError("El código de establecimiento debe estar entre 001 y 999.")

        # ✅ VALIDACIÓN CORREGIDA: Validar que punto_emision esté en el rango correcto (1-999)
        if self.punto_emision < 1 or self.punto_emision > 999:
            raise ValueError("El código de punto de emisión debe estar entre 001 y 999.")

        super(Secuencia, self).save(*args, **kwargs)
    
    def get_establecimiento_formatted(self):
        """Retorna el establecimiento formateado con 3 dígitos (001, 002, etc.)"""
        return f"{self.establecimiento:03d}"
    
    def get_punto_emision_formatted(self):
        """Retorna el punto de emisión formateado con 3 dígitos (001, 002, etc.)"""
        return f"{self.punto_emision:03d}"
    
    def get_secuencial_formatted(self):
        """Retorna el secuencial formateado con 9 dígitos (000000001, etc.)"""
        return f"{self.secuencial:09d}"

class FacturadorManager(BaseUserManager):
    def create_facturador(self, nombres, telefono, correo, password=None, **extra_fields):
        """Crea y guarda un nuevo facturador"""
        if not correo:
            raise ValueError('El correo es obligatorio')
        
        if not nombres:
            raise ValueError('Los nombres son obligatorios')
            
        correo = self.normalize_email(correo)
        facturador = self.model(
            nombres=nombres, 
            telefono=telefono, 
            correo=correo, 
            **extra_fields
        )
        
        # IMPORTANTE: Usar set_password para encriptar la contraseña
        if password:
            facturador.set_password(password)
        else:
            facturador.set_unusable_password()
            
        facturador.save(using=self._db)
        return facturador

    def create_superuser(self, correo, nombres, password, **extra_fields):
        """Crea un superusuario facturador"""
        extra_fields.setdefault('activo', True)
        
        return self.create_facturador(
            nombres=nombres,
            correo=correo,
            password=password,
            **extra_fields
        )


class Facturador(AbstractBaseUser):
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='facturadores',
        null=True,
        blank=True,
    )
    nombres = models.CharField(max_length=255, verbose_name='Nombres')
    telefono = models.CharField(max_length=15, blank=True, null=True, verbose_name='Teléfono')
    correo = models.EmailField(unique=True, verbose_name='Correo')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    descuento_permitido = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, verbose_name='Descuento Permitido'
    )
    
    # Fechas de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = FacturadorManager()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombres']

    class Meta:
        verbose_name = 'Facturador'
        verbose_name_plural = 'Facturadores'
        db_table = 'inventario_facturador'

    def __str__(self):
        return f'{self.nombres} - {self.correo}'
    
    def has_perm(self, perm, obj=None):
        """¿Tiene el usuario un permiso específico?"""
        return self.activo
    
    def has_module_perms(self, app_label):
        """¿Tiene el usuario permisos para ver la app `app_label`?"""
        return self.activo
    
    @property
    def is_staff(self):
        """¿Es el usuario un miembro del staff?"""
        return self.activo

    # ✅ NUEVO: Verifica si puede aplicar un descuento específico
    def puede_aplicar_descuento(self, porcentaje):
        """Verifica si puede aplicar un descuento específico"""
        return porcentaje <= self.descuento_permitido

    # ✅ NUEVO: Calcula cuánto descuento le queda disponible en una factura
    def descuento_disponible(self, factura):
        """Calcula cuánto descuento le queda disponible en una factura"""
        if factura.sub_monto <= 0:
            return 0
        
        porcentaje_usado = (factura.total_descuento / factura.sub_monto) * 100
        return max(0, self.descuento_permitido - porcentaje_usado)

    # ✅ NUEVO: Property para verificar si el facturador puede emitir facturas
    @property
    def puede_facturar(self):
        """Verifica si el facturador puede emitir facturas"""
        return self.activo

class Almacen(models.Model):
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='almacenes',
        null=True,
        blank=True,
    )
    descripcion = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)  # Campo activo añadido

    def __str__(self):
        return self.descripcion


# ===============================  MODELO CAJA  ===============================
class Caja(models.Model):
    """
    Modelo para manejar las cajas del sistema
    """
    
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='cajas',
        null=True,
        blank=True,
    )
    # ✅ Campo principal: Descripción de la caja
    descripcion = models.CharField(
        max_length=100,
        verbose_name="Descripción",
        help_text="Nombre o descripción de la caja (ej: Caja Ventas, Caja Principal)"
    )
    
    # ✅ Campo estado: Activo/Inactivo
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="¿La caja está activa?"
    )
    
    # ✅ Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Creado por"
    )
    
    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ['descripcion']
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # Validar que la descripción no esté vacía
        if not self.descripcion or not self.descripcion.strip():
            raise ValidationError({
                'descripcion': 'La descripción es obligatoria.'
            })
        
        # Limpiar espacios extra
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.descripcion
    
    # ✅ Métodos útiles
    @classmethod
    def get_activas(cls):
        """Obtiene todas las cajas activas"""
        return cls.objects.filter(activo=True).order_by('descripcion')
    
    @classmethod
    def get_choices(cls):
        """Retorna choices para usar en formularios"""
        return [(caja.id, caja.descripcion) for caja in cls.get_activas()]
    
    @classmethod
    def total_cajas_activas(cls):
        """Cuenta total de cajas activas"""
        return cls.objects.filter(activo=True).count()


# ✅ MODELO NUEVO: FormaPago (MUY CRÍTICO para XML válido)
class FormaPago(models.Model):
    """
    Formas de pago de la factura según tabla 24 del SRI
    """
    
    # ✅ Opciones según tabla 24 del SRI (las más usadas)
    FORMAS_PAGO_CHOICES = [
    ('01', 'Sin utilización del sistema financiero'),
    ('15', 'Compensación de deudas'),
    ('16', 'Tarjeta de débito'),
    ('17', 'Dinero electrónico'),
    ('18', 'Tarjeta prepago'),
    ('19', 'Tarjeta de crédito'),
    ('20', 'Otros con utilización del sistema financiero'),
    ('21', 'Endoso de títulos'),
    ]
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='formas_pago',
        null=True,
        blank=True,
    )
    
    # ✅ Relación con factura
    factura = models.ForeignKey(
        Factura, 
        on_delete=models.CASCADE, 
        related_name='formas_pago',
        verbose_name="Factura"
    )
    
    # ✅ OBLIGATORIO: Forma de pago según tabla SRI - SIN DEFAULT
    forma_pago = models.CharField(
        max_length=2, 
        choices=FORMAS_PAGO_CHOICES, 
        verbose_name="Forma de Pago",
        help_text="Selección obligatoria según tabla 24 SRI"
    )
    
    # ✅ CORREGIDO: Campo Caja como ForeignKey
    caja = models.ForeignKey(
        'Caja',
        on_delete=models.PROTECT,
        related_name='formas_pago',
        verbose_name="Caja",
        blank=True,
        null=True,
    )
    
    # ✅ OBLIGATORIO: Total pagado con esta forma
    total = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Total"
    )
    
    # ✅ OPCIONAL: Plazo (para pagos a crédito)
    plazo = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name="Plazo"
    )
    
    # ✅ OPCIONAL: Unidad de tiempo del plazo
    unidad_tiempo = models.CharField(
        max_length=10, 
        blank=True, 
        null=True,
        choices=[
            ('dias', 'Días'),
            ('semanas', 'Semanas'),
            ('meses', 'Meses'),
            ('años', 'Años'),
        ],
        verbose_name="Unidad de Tiempo"
    )
    
    class Meta:
        verbose_name = "Forma de Pago"
        verbose_name_plural = "Formas de Pago"
        # ✅ Asegurar que no se dupliquen formas de pago en la misma factura
        unique_together = ('factura', 'forma_pago')
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # ✅ Validar que si hay plazo, debe haber unidad de tiempo
        if self.plazo and not self.unidad_tiempo:
            raise ValidationError({
                'unidad_tiempo': 'Debe especificar la unidad de tiempo cuando hay plazo'
            })
        
        # ✅ Validar que el total no exceda el total de la factura
        if self.factura and self.total:
            total_otras_formas = self.factura.formas_pago.exclude(id=self.id).aggregate(
                total=models.Sum('total')
            )['total'] or 0
            
            total_con_esta = total_otras_formas + self.total
            
            if total_con_esta > self.factura.monto_general:
                raise ValidationError({
                    'total': f'El total de formas de pago (${total_con_esta}) '
                           f'excede el total de la factura (${self.factura.monto_general})'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Factura {self.factura.id} - {self.get_forma_pago_display()} (${self.total})"
    
    # ✅ Métodos útiles
    @property
    def es_contado(self):
        """Verifica si es pago de contado"""
        return self.forma_pago == '01'
    
    @property
    def es_credito(self):
        """Verifica si es pago a crédito (tiene plazo)"""
        return self.plazo is not None and self.plazo > 0
    
    @property
    def descripcion_completa(self):
        """Descripción completa del pago"""
        desc = self.get_forma_pago_display()
        if self.es_credito:
            desc += f" - {self.plazo} {self.unidad_tiempo}"
        return desc


# ✅ MODELO NUEVO: CampoAdicional (MUY RECOMENDADO)
class CampoAdicional(models.Model):
    """
    Información adicional de la factura según XSD del SRI
    Máximo 15 campos adicionales por factura
    """
    
    # ✅ Relación con factura
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='campos_adicionales',
        null=True,
        blank=True,
    )
    factura = models.ForeignKey(
        Factura, 
        on_delete=models.CASCADE, 
        related_name='campos_adicionales',
        verbose_name="Factura"
    )
    
    # ✅ OBLIGATORIO: Nombre del campo (max 300 caracteres según XSD)
    nombre = models.CharField(
        max_length=300,
        verbose_name="Nombre del Campo",
        help_text="Ej: E-MAIL, TELÉFONO, OBSERVACIONES, etc."
    )
    
    # ✅ OBLIGATORIO: Valor del campo (max 300 caracteres según XSD)
    valor = models.CharField(
        max_length=300,
        verbose_name="Valor del Campo",
        help_text="Contenido del campo adicional"
    )
    
    # ✅ Orden para mostrar los campos
    orden = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(15)],
        verbose_name="Orden",
        help_text="Orden de aparición en la factura (1-15)"
    )
    
    class Meta:
        verbose_name = "Campo Adicional"
        verbose_name_plural = "Campos Adicionales"
        # ✅ No duplicar nombres en la misma factura
        unique_together = ('factura', 'nombre')
        ordering = ['factura', 'orden', 'nombre']
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # ✅ Validar máximo 15 campos por factura según XSD
        if self.factura:
            campos_existentes = self.factura.campos_adicionales.exclude(id=self.id).count()
            if campos_existentes >= 15:
                raise ValidationError(
                    'Una factura no puede tener más de 15 campos adicionales según SRI'
                )
        
        # ✅ Limpiar espacios en nombre y valor
        if self.nombre:
            self.nombre = self.nombre.strip()
        if self.valor:
            self.valor = self.valor.strip()
        
        # ✅ Validar que no estén vacíos después de limpiar
        if not self.nombre or not self.valor:
            raise ValidationError('Nombre y valor no pueden estar vacíos')
    
    def save(self, *args, **kwargs):
        # ✅ Asignar orden automáticamente si no se especifica
        if not self.orden and self.factura:
            ultimo_orden = self.factura.campos_adicionales.aggregate(
                max_orden=models.Max('orden')
            )['max_orden'] or 0
            self.orden = ultimo_orden + 1
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Factura {self.factura.id} - {self.nombre}: {self.valor[:50]}..."
    
    # ✅ Métodos útiles para tipos comunes
    @classmethod
    def crear_email(cls, factura, email):
        """Crear campo adicional para email"""
        return cls.objects.create(
            factura=factura,
            nombre='E-MAIL',
            valor=email
        )
    
    @classmethod
    def crear_telefono(cls, factura, telefono):
        """Crear campo adicional para teléfono"""
        return cls.objects.create(
            factura=factura,
            nombre='TELÉFONO',
            valor=telefono
        )
    
    @classmethod
    def crear_direccion(cls, factura, direccion):
        """Crear campo adicional para dirección"""
        return cls.objects.create(
            factura=factura,
            nombre='DIRECCIÓN',
            valor=direccion
        )
    
    @classmethod
    def crear_observaciones(cls, factura, observaciones):
        """Crear campo adicional para observaciones"""
        return cls.objects.create(
            factura=factura,
            nombre='OBSERVACIONES',
            valor=observaciones
        )
    
    @classmethod
    def crear_vendedor(cls, factura, vendedor):
        """Crear campo adicional para vendedor"""
        return cls.objects.create(
            factura=factura,
            nombre='VENDEDOR',
            valor=vendedor
        )
    
    # ✅ Campos adicionales más comunes según SRI
    CAMPOS_COMUNES = [
        'E-MAIL',
        'TELÉFONO',
        'DIRECCIÓN',
        'OBSERVACIONES',
        'VENDEDOR',
        'SUCURSAL',
        'PROYECTO',
        'ORDEN DE COMPRA',
        'REFERENCIA',
        'CONTACTO',
        'NOTAS',
        'CIUDAD',
        'PROVINCIA',
        'CÓDIGO POSTAL',
        'SITIO WEB'
    ]
    
    @classmethod
    def get_campos_disponibles(cls, factura):
        """Obtiene campos comunes que aún no se han usado en la factura"""
        campos_usados = factura.campos_adicionales.values_list('nombre', flat=True)
        return [campo for campo in cls.CAMPOS_COMUNES if campo not in campos_usados]


# ✅ MODELO NUEVO: MaquinaFiscal (OPCIONAL)
class MaquinaFiscal(models.Model):
    """
    Información de máquina fiscal según XSD del SRI
    Solo se usa cuando la factura se emite desde una máquina fiscal
    """
    
    # ✅ Relación uno a uno con factura
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='maquinas_fiscales',
        null=True,
        blank=True,
    )
    factura = models.OneToOneField(
        Factura, 
        on_delete=models.CASCADE, 
        related_name='maquina_fiscal',
        verbose_name="Factura"
    )
    
    # ✅ OBLIGATORIO: Marca de la máquina (max 30 caracteres según XSD)
    marca = models.CharField(
        max_length=30,
        verbose_name="Marca",
        help_text="Marca de la máquina fiscal (ej: EPSON, BIXOLON, etc.)"
    )
    
    # ✅ OBLIGATORIO: Modelo de la máquina (max 30 caracteres según XSD)
    modelo = models.CharField(
        max_length=30,
        verbose_name="Modelo",
        help_text="Modelo específico de la máquina fiscal"
    )
    
    # ✅ OBLIGATORIO: Serie de la máquina (max 30 caracteres según XSD)
    serie = models.CharField(
        max_length=30,
        verbose_name="Número de Serie",
        help_text="Número de serie único de la máquina fiscal"
    )
    
    # ✅ Campos adicionales para control interno
    fecha_instalacion = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Instalación",
        help_text="Fecha en que se instaló la máquina fiscal"
    )
    
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="¿La máquina fiscal está activa?"
    )
    
    ubicacion = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Ubicación",
        help_text="Ubicación física de la máquina (ej: Caja 1, Mostrador, etc.)"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones",
        help_text="Notas adicionales sobre la máquina fiscal"
    )
    
    class Meta:
        verbose_name = "Máquina Fiscal"
        verbose_name_plural = "Máquinas Fiscales"
        # ✅ Asegurar que serie sea única
        constraints = [
            models.UniqueConstraint(
                fields=['serie'], 
                name='unique_serie_maquina_fiscal'
            )
        ]
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # ✅ Limpiar espacios en los campos
        if self.marca:
            self.marca = self.marca.strip()
        if self.modelo:
            self.modelo = self.modelo.strip()
        if self.serie:
            self.serie = self.serie.strip()
        
        # ✅ Validar que no estén vacíos después de limpiar
        if not self.marca or not self.modelo or not self.serie:
            raise ValidationError('Marca, modelo y serie son obligatorios')
        
        # ✅ Validar formato de serie (solo alfanumérico)
        import re
        if not re.match(r'^[A-Za-z0-9\-_]+$', self.serie):
            raise ValidationError({
                'serie': 'La serie solo puede contener letras, números, guiones y guiones bajos'
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.marca} {self.modelo} - Serie: {self.serie}"
    
    # ✅ Métodos útiles
    @property
    def descripcion_completa(self):
        """Descripción completa de la máquina"""
        return f"{self.marca} {self.modelo} (S/N: {self.serie})"
    
    @property
    def identificador_unico(self):
        """Identificador único para el XML"""
        return f"{self.marca}-{self.modelo}-{self.serie}".upper()
    
    @classmethod
    def crear_para_factura(cls, factura, marca, modelo, serie, **kwargs):
        """Método helper para crear máquina fiscal asociada a factura"""
        return cls.objects.create(
            factura=factura,
            marca=marca,
            modelo=modelo,
            serie=serie,
            **kwargs
        )
    
    @classmethod
    def get_maquinas_activas(cls):
        """Obtiene todas las máquinas fiscales activas"""
        return cls.objects.filter(activa=True).select_related('factura')
    
    @classmethod
    def get_por_serie(cls, serie):
        """Busca máquina fiscal por número de serie"""
        try:
            return cls.objects.get(serie=serie)
        except cls.DoesNotExist:
            return None
    
    # ✅ Marcas y modelos comunes de máquinas fiscales en Ecuador
    MARCAS_COMUNES = [
        'EPSON',
        'BIXOLON', 
        'CITIZEN',
        'STAR',
        'ZEBRA',
        'DATAMAX',
        'GODEX',
        'TSC',
        'ARGOX',
        'HONEYWELL'
    ]
    
    @classmethod
    def get_marcas_disponibles(cls):
        """Obtiene lista de marcas comunes"""
        return cls.MARCAS_COMUNES


# ✅ MODELO NUEVO: TipoNegociable (OPCIONAL - Solo facturas comerciales negociables)
class TipoNegociable(models.Model):
    """
    Información para facturas electrónicas comerciales negociables según SRI
    Solo para contribuyentes que se dedican a la negociación de facturas electrónicas
    """
    
    # ✅ Relación uno a uno con factura
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='tipos_negociables',
        null=True,
        blank=True,
    )
    factura = models.OneToOneField(
        Factura, 
        on_delete=models.CASCADE, 
        related_name='tipo_negociable',
        verbose_name="Factura"
    )
    
    # ✅ OBLIGATORIO: Correo electrónico del receptor (max 100 caracteres según XSD)
    correo = models.EmailField(
        max_length=100,
        verbose_name="Correo del Receptor",
        help_text="Email del receptor para notificación masiva de facturas negociables"
    )
    
    # ✅ Campos adicionales para control del proceso de negociación
    estado_negociacion = models.CharField(
        max_length=20,
        choices=[
            ('pendiente', 'Pendiente de Negociación'),
            ('en_proceso', 'En Proceso de Negociación'),
            ('negociada', 'Negociada'),
            ('rechazada', 'Rechazada'),
            ('vencida', 'Vencida'),
        ],
        default='pendiente',
        verbose_name="Estado de Negociación"
    )
    
    fecha_notificacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Notificación",
        help_text="Fecha en que se notificó al receptor"
    )
    
    fecha_aceptacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Aceptación",
        help_text="Fecha en que el receptor aceptó la factura"
    )
    
    fecha_vencimiento_negociacion = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha Vencimiento Negociación",
        help_text="Fecha límite para negociar la factura"
    )
    
    entidad_negociadora = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Entidad Negociadora",
        help_text="Nombre de la entidad que negocia la factura"
    )
    
    valor_negociado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Valor Negociado",
        help_text="Valor por el cual se negoció la factura"
    )
    
    tasa_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name="Tasa de Descuento",
        help_text="Tasa de descuento aplicada en la negociación (0.0000 - 1.0000)"
    )
    
    observaciones_negociacion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones de Negociación",
        help_text="Notas sobre el proceso de negociación"
    )
    
    class Meta:
        verbose_name = "Tipo Negociable"
        verbose_name_plural = "Tipos Negociables"
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        # ✅ La factura debe tener dirección del comprador (requisito SRI)
        if self.factura and not self.factura.cliente.direccion:
            raise ValidationError(
                'Las facturas comerciales negociables requieren dirección del comprador'
            )
        
        # ✅ La factura debe tener forma de pago definida (requisito SRI)
        if self.factura and not self.factura.formas_pago.exists():
            raise ValidationError(
                'Las facturas comerciales negociables requieren forma de pago definida'
            )
        
        # ✅ Si está negociada, debe tener valor negociado
        if self.estado_negociacion == 'negociada' and not self.valor_negociado:
            raise ValidationError({
                'valor_negociado': 'Debe especificar el valor negociado'
            })
        
        # ✅ Si hay valor negociado, debe tener tasa de descuento
        if self.valor_negociado and not self.tasa_descuento:
            # Calcular tasa automáticamente
            if self.factura and self.factura.monto_general > 0:
                descuento = self.factura.monto_general - self.valor_negociado
                self.tasa_descuento = descuento / self.factura.monto_general
    
    def save(self, *args, **kwargs):
        # ✅ Asignar fecha de notificación automáticamente
        if not self.fecha_notificacion and self.estado_negociacion != 'pendiente':
            from django.utils import timezone
            self.fecha_notificacion = timezone.now()
        
        # ✅ Asignar fecha de aceptación automáticamente
        if not self.fecha_aceptacion and self.estado_negociacion in ['negociada', 'en_proceso']:
            from django.utils import timezone
            self.fecha_aceptacion = timezone.now()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Factura Negociable {self.factura.id} - {self.correo} ({self.estado_negociacion})"
    
    # ✅ Métodos útiles
    @property
    def puede_negociar(self):
        """Verifica si la factura puede ser negociada"""
        from django.utils import timezone
        
        if self.estado_negociacion not in ['pendiente', 'en_proceso']:
            return False
        
        if self.fecha_vencimiento_negociacion and self.fecha_vencimiento_negociacion < timezone.now().date():
            return False
        
        return True
    
    @property
    def dias_para_vencimiento(self):
        """Calcula días restantes para vencimiento de negociación"""
        if not self.fecha_vencimiento_negociacion:
            return None
        
        from django.utils import timezone
        hoy = timezone.now().date()
        
        if self.fecha_vencimiento_negociacion <= hoy:
            return 0
        
        return (self.fecha_vencimiento_negociacion - hoy).days
    
    @property
    def porcentaje_descuento(self):
        """Retorna el porcentaje de descuento aplicado"""
        if self.tasa_descuento:
            return self.tasa_descuento * 100
        return 0
    
    def calcular_valor_negociado(self, tasa_descuento):
        """Calcula el valor negociado basado en una tasa de descuento"""
        if not self.factura:
            return 0
        
        descuento = self.factura.monto_general * tasa_descuento
        return self.factura.monto_general - descuento
    
    def marcar_como_negociada(self, valor_negociado, entidad_negociadora=None):
        """Marca la factura como negociada"""
        from django.utils import timezone
        
        self.estado_negociacion = 'negociada'
        self.valor_negociado = valor_negociado
        self.fecha_aceptacion = timezone.now()
        
        if entidad_negociadora:
            self.entidad_negociadora = entidad_negociadora
        
        # Calcular tasa de descuento
        if self.factura and self.factura.monto_general > 0:
            descuento = self.factura.monto_general - valor_negociado
            self.tasa_descuento = descuento / self.factura.monto_general
        
        self.save()
    
    def marcar_como_rechazada(self, observaciones=None):
        """Marca la factura como rechazada"""
        self.estado_negociacion = 'rechazada'
        if observaciones:
            self.observaciones_negociacion = observaciones
        self.save()
    
    @classmethod
    def get_pendientes_vencimiento(cls, dias=7):
        """Obtiene facturas que vencen en X días"""
        from django.utils import timezone
        fecha_limite = timezone.now().date() + timezone.timedelta(days=dias)
        
        return cls.objects.filter(
            estado_negociacion__in=['pendiente', 'en_proceso'],
            fecha_vencimiento_negociacion__lte=fecha_limite
        ).select_related('factura')
    
    @classmethod
    def get_por_estado(cls, estado):
        """Obtiene facturas por estado de negociación"""
        return cls.objects.filter(estado_negociacion=estado).select_related('factura')
    

class TotalImpuesto(models.Model):
    """
    Sección <totalConImpuestos><totalImpuesto> del XML
    CRÍTICO: Sin esto el XML será INVÁLIDO
    """
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='totales_impuestos',
        null=True,
        blank=True,
    )
    factura = models.ForeignKey(
        Factura, 
        on_delete=models.CASCADE, 
        related_name='totales_impuestos'
    )
    
    # ✅ OBLIGATORIO: Código según tabla 16 SRI
    codigo = models.CharField(
        max_length=1,
        choices=[
            ('2', 'IVA'),
            ('3', 'ICE'), 
            ('5', 'IRBPNR'),
            ('6', 'ISD')
        ],
        help_text="Código del impuesto según tabla 16 SRI"
    )
    
    # ✅ OBLIGATORIO: Código porcentaje según tablas 17/18 SRI
    codigo_porcentaje = models.CharField(
        max_length=4,
        help_text="Código específico del porcentaje (ej: 2, 0, 6, 7)"
    )
    
    # ✅ OBLIGATORIO: Base imponible
    base_imponible = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        help_text="Base sobre la cual se calcula el impuesto"
    )
    
    # ✅ OBLIGATORIO: Tarifa del impuesto
    tarifa = models.DecimalField(
        max_digits=4, 
        decimal_places=2,
        help_text="Porcentaje del impuesto (ej: 15.00 para 15%)"
    )
    
    # ✅ OBLIGATORIO: Valor calculado del impuesto
    valor = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        help_text="Valor del impuesto = base_imponible * (tarifa/100)"
    )
    
    # ✅ OPCIONAL: Descuento adicional (solo para IVA código 2)
    descuento_adicional = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        default=0.00,
        help_text="Descuento adicional aplicable solo a IVA"
    )
    
    class Meta:
        verbose_name = "Total Impuesto"
        verbose_name_plural = "Totales Impuestos"
        unique_together = ('factura', 'codigo', 'codigo_porcentaje')
    
    def save(self, *args, **kwargs):
        # Auto-calcular valor si no está definido
        if not self.valor:
            self.valor = self.base_imponible * (self.tarifa / 100)
        super().save(*args, **kwargs)

class ImpuestoDetalle(models.Model):
    """
    Sección <detalles><detalle><impuestos><impuesto> del XML
    CRÍTICO: Cada ítem debe tener sus impuestos calculados
    """
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='impuestos_detalle',
        null=True,
        blank=True,
    )
    detalle_factura = models.ForeignKey(
        DetalleFactura, 
        on_delete=models.CASCADE,
        related_name='impuestos_detalle'
    )
    
    # ✅ OBLIGATORIO: Código del impuesto
    codigo = models.CharField(max_length=1, choices=[
        ('2', 'IVA'), ('3', 'ICE'), ('5', 'IRBPNR')
    ])
    
    # ✅ OBLIGATORIO: Código porcentaje específico
    codigo_porcentaje = models.CharField(max_length=4)
    
    # ✅ OBLIGATORIO: Tarifa
    tarifa = models.DecimalField(max_digits=4, decimal_places=2)
    
    # ✅ OBLIGATORIO: Base imponible del ítem
    base_imponible = models.DecimalField(max_digits=14, decimal_places=2)
    
    # ✅ OBLIGATORIO: Valor del impuesto
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    
    def save(self, *args, **kwargs):
        # Auto-calcular valor
        if not self.valor:
            self.valor = self.base_imponible * (self.tarifa / 100)
        super().save(*args, **kwargs)


class DetalleAdicional(models.Model):
    """
    Sección <detalles><detalle><detallesAdicionales> del XML
    Máximo 3 detalles adicionales por ítem según XSD
    """
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='detalles_adicionales',
        null=True,
        blank=True,
    )
    detalle_factura = models.ForeignKey(
        DetalleFactura, 
        on_delete=models.CASCADE,
        related_name='detalles_adicionales'
    )
    
    # ✅ OBLIGATORIO: Nombre del detalle adicional
    nombre = models.CharField(
        max_length=300,
        help_text="Nombre del detalle adicional (ej: Marca, Modelo, Serie)"
    )
    
    # ✅ OBLIGATORIO: Valor del detalle adicional  
    valor = models.CharField(
        max_length=300,
        help_text="Valor del detalle adicional"
    )
    
    # ✅ Orden para XML
    orden = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    
    class Meta:
        verbose_name = "Detalle Adicional"
        verbose_name_plural = "Detalles Adicionales"
        unique_together = ('detalle_factura', 'nombre')
        ordering = ['detalle_factura', 'orden', 'nombre']
    
    def clean(self):
        # Máximo 3 detalles adicionales por ítem
        if self.detalle_factura:
            count = self.detalle_factura.detalles_adicionales.exclude(id=self.id).count()
            if count >= 3:
                raise ValidationError(
                    'Máximo 3 detalles adicionales por ítem según XSD SRI'
                )

# ===============================  MODELO BANCO  ===============================

class Banco(models.Model):
    """
    Modelo para manejar las cuentas bancarias del sistema
    """
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='bancos',
        null=True,
        blank=True,
    )
    
    # ✅ Campos según tu imagen del formulario
    banco = models.CharField(
        max_length=100,
        verbose_name="Banco",
        help_text="Nombre del banco (ej: Banco Pichincha, Banco de Guayaquil)"
    )
    
    titular = models.CharField(
        max_length=200,
        verbose_name="Titular",
        help_text="Nombre completo del titular de la cuenta"
    )
    
    numero_cuenta = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Cuenta",
        help_text="Número de la cuenta bancaria"
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="¿La cuenta bancaria está activa?"
    )
    
    saldo_inicial = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name="Saldo Inicial",
        help_text="Saldo inicial de la cuenta"
    )
    
    # ✅ Opciones de tipo de cuenta según bancos ecuatorianos
    TIPO_CUENTA_CHOICES = [
        ('CORRIENTE', 'Corriente'),
        ('AHORROS', 'Ahorros'),
        ('VISTA', 'Vista'),
        ('PLAZO_FIJO', 'Plazo Fijo'),
    ]
    
    tipo_cuenta = models.CharField(
        max_length=20,
        choices=TIPO_CUENTA_CHOICES,
        default='CORRIENTE',
        verbose_name="Tipo de Cuenta"
    )
    
    fecha_apertura = models.DateField(
        verbose_name="Fecha Apertura",
        help_text="Fecha en que se abrió la cuenta"
    )
    
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Teléfono",
        help_text="Teléfono de contacto del banco o sucursal"
    )
    
    secuencial_cheque = models.IntegerField(
        default=1,
        verbose_name="Secuencial Cheque",
        help_text="Próximo número de cheque a utilizar",
        validators=[MinValueValidator(1)]
    )
    
    # ✅ Campos adicionales útiles
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones",
        help_text="Notas adicionales sobre la cuenta bancaria"
    )
    
    # ✅ Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Creado por",
        help_text="Usuario que creó esta cuenta bancaria"
    )
    
    class Meta:
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ['banco', 'titular']
        unique_together = [('banco', 'numero_cuenta')]  # Evitar duplicados
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        import re
        
        # Validar que el número de cuenta solo contenga números y guiones
        if self.numero_cuenta:
            if not re.match(r'^[0-9\-]+$', self.numero_cuenta):
                raise ValidationError({
                    'numero_cuenta': 'El número de cuenta solo puede contener números y guiones.'
                })
        
        # Validar formato de teléfono si se proporciona
        if self.telefono:
            if not re.match(r'^[0-9\s\-\(\)]+$', self.telefono):
                raise ValidationError({
                    'telefono': 'El teléfono solo puede contener números, espacios, guiones y paréntesis.'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.banco} - {self.titular} ({self.numero_cuenta})"
    
    # ✅ Métodos útiles para el sistema
    @classmethod
    def get_activos(cls):
        """Obtiene todas las cuentas bancarias activas"""
        return cls.objects.filter(activo=True).order_by('banco', 'titular')
    
    @classmethod
    def get_choices(cls):
        """Retorna choices para usar en formularios"""
        return [(banco.id, f"{banco.banco} - {banco.numero_cuenta}") for banco in cls.get_activos()]
    
    @classmethod
    def get_por_banco(cls, nombre_banco):
        """Obtiene cuentas de un banco específico"""
        return cls.objects.filter(
            banco__icontains=nombre_banco,
            activo=True
        ).order_by('titular')
    
    @property
    def nombre_completo(self):
        """Nombre completo para mostrar en reportes"""
        return f"{self.banco} - {self.titular}"
    
    @property
    def descripcion_cuenta(self):
        """Descripción completa de la cuenta"""
        return f"{self.banco} ({self.get_tipo_cuenta_display()}) - {self.numero_cuenta}"
    
    def siguiente_cheque(self):
        """Obtiene el siguiente número de cheque"""
        return self.secuencial_cheque
    
    def incrementar_cheque(self):
        """Incrementa el secuencial de cheque y lo guarda"""
        self.secuencial_cheque += 1
        self.save(update_fields=['secuencial_cheque', 'fecha_actualizacion'])
        return self.secuencial_cheque - 1  # Retorna el número que se usó
    
    def resetear_cheque(self, nuevo_numero=1):
        """Resetea el secuencial de cheque"""
        self.secuencial_cheque = nuevo_numero
        self.save(update_fields=['secuencial_cheque', 'fecha_actualizacion'])
    
    # ✅ Métodos para estadísticas
    @classmethod
    def total_cuentas_activas(cls):
        """Cuenta total de cuentas activas"""
        return cls.objects.filter(activo=True).count()
    
    @classmethod
    def por_tipo_cuenta(cls):
        """Agrupa cuentas por tipo"""
        from django.db.models import Count
        return cls.objects.filter(activo=True).values('tipo_cuenta').annotate(
            total=Count('id')
        ).order_by('tipo_cuenta')
    
    @classmethod
    def bancos_disponibles(cls):
        """Lista de bancos únicos en el sistema"""
        return cls.objects.filter(activo=True).values_list(
            'banco', flat=True
        ).distinct().order_by('banco')
    
class Servicio(models.Model):
    """
    Modelo para registrar servicios facturables en el sistema.
    Ejemplo: MANTENIMIENTO DE EQUIPOS DE CERRAJERÍA
    """
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='servicios',
        null=True,
        blank=True,
    )
    tiposIVA = [
        ('0', '0%'),
        ('5', '5%'),
        ('2', '12%'),
        ('10', '13%'),
        ('3', '14%'),
        ('4', '15%'),
        ('6', 'No Objeto'),
        ('7', 'Exento de IVA'),
        ('8', 'IVA Diferenciado')
    ]

    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.TextField(blank=True)
    iva = models.CharField(max_length=10, choices=tiposIVA, default='2')
    precio1 = models.DecimalField(max_digits=10, decimal_places=2)
    precio2 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.descripcion

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"


# -----------------------------------PROFORMA-----------------------------------------
class Proforma(models.Model):
    """Modelo para manejar proformas/cotizaciones en el sistema"""
    empresa = models.ForeignKey(
        'Empresa',
        on_delete=models.CASCADE,
        related_name='proformas',
        null=False,
        blank=False,
    )
    
    # Datos de la proforma
    numero = models.CharField(max_length=20, help_text="Número de proforma (ej: PF-000001)")
    fecha_emision = models.DateField(help_text="Fecha de emisión de la proforma")
    fecha_vencimiento = models.DateField(help_text="Fecha de vencimiento de la cotización")
    
    # Cliente relacionado
    cliente = models.ForeignKey(
        'Cliente', 
        on_delete=models.CASCADE, 
        help_text="Cliente al que se dirige la proforma"
    )
    
    # Vendedor/facturador que crea la proforma
    facturador = models.ForeignKey(
        'Facturador',
        on_delete=models.PROTECT,
        related_name='proformas',
        help_text="Facturador que emite la proforma"
    )
    
    # Almacén opcional
    almacen = models.ForeignKey(
        'Almacen',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Almacén desde donde se cotiza"
    )
    
    # Observaciones generales
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Observaciones o condiciones de la proforma"
    )
    
    # Montos calculados
    subtotal = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Subtotal sin impuestos"
    )
    
    total_descuento = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total de descuentos aplicados"
    )
    
    total_impuestos = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total de impuestos (IVA)"
    )
    
    total = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total final de la proforma"
    )
    
    # Estado de la proforma
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('ENVIADA', 'Enviada'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('CONVERTIDA', 'Convertida a Factura'),
        ('VENCIDA', 'Vencida'),
    ]
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
        help_text="Estado actual de la proforma"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        help_text="Usuario que creó la proforma"
    )
    
    # Factura generada (si se convierte)
    factura = models.OneToOneField(
        'Factura',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Factura generada a partir de esta proforma"
    )
    
    @classmethod
    def siguiente_numero(cls, empresa):
        """Calcula el siguiente código secuencial por empresa.
        Formato: PR000001 (prefijo PR + 6 dígitos). Ignora formatos viejos (p.ej. PF-000001).
        """
        from django.db.models import F

        max_n = 0
        # Recorremos solo los números existentes de esa empresa
        for cod in cls.objects.filter(empresa=empresa).values_list('numero', flat=True):
            if not cod:
                continue
            # Extraer parte numérica
            digits = ''.join(ch for ch in str(cod) if ch.isdigit())
            try:
                n = int(digits)
            except (TypeError, ValueError):
                continue
            if n > max_n:
                max_n = n
        return f"PR{max_n + 1:06d}"

    def save(self, *args, **kwargs):
        """Guarda la proforma y calcula automáticamente los totales"""
        # Generar número automáticamente si no existe (por empresa)
        if not self.numero and self.empresa_id:
            # Intentar pocas veces en caso de colisión por concurrencia
            intentos = 0
            while intentos < 5:
                candidato = Proforma.siguiente_numero(self.empresa)
                if not Proforma.objects.filter(empresa=self.empresa, numero=candidato).exists():
                    self.numero = candidato
                    break
                intentos += 1
            if not self.numero:
                # Último recurso: asignar usando timestamp para evitar choque (muy raro)
                import time
                self.numero = f"PR{int(time.time()) % 1000000:06d}"

        # Calcular totales antes de guardar
        if self.pk:
            self.calcular_totales()
        
        super().save(*args, **kwargs)
        
        # Recalcular totales después de guardar (para asegurar que los detalles estén disponibles)
        if self.pk:
            self.calcular_totales()
    
    def calcular_totales(self):
        """Calcula automáticamente todos los totales de la proforma"""
        from django.db.models import Sum
        from decimal import Decimal, ROUND_HALF_UP
        
        # Verificar si la proforma tiene detalles
        if not hasattr(self, 'detalles') or not self.detalles.exists():
            self.subtotal = Decimal('0.00')
            self.total_descuento = Decimal('0.00')
            self.total_impuestos = Decimal('0.00')
            self.total = Decimal('0.00')
            return
        
        # Calcular subtotal y descuentos
        subtotal = Decimal('0.00')
        total_descuento = Decimal('0.00')
        
        for detalle in self.detalles.all():
            subtotal += detalle.subtotal
            total_descuento += detalle.descuento
        
        # Calcular impuestos
        total_impuestos = Decimal('0.00')
        for detalle in self.detalles.all():
            # Obtener el IVA del producto o servicio
            if detalle.producto:
                porcentaje_iva = detalle.producto.get_porcentaje_iva_real()
            elif detalle.servicio:
                MAPEO_IVA = {
                    '0': 0.00, '5': 5.00, '2': 12.00, '10': 13.00,
                    '3': 14.00, '4': 15.00, '6': 0.00, '7': 0.00, '8': 8.00
                }
                porcentaje_iva = MAPEO_IVA.get(detalle.servicio.iva, 0.00)
            else:
                porcentaje_iva = 0.00
            
            # Calcular IVA sobre el subtotal menos descuento del detalle
            base_imponible = detalle.subtotal - detalle.descuento
            iva_detalle = base_imponible * (Decimal(str(porcentaje_iva)) / 100)
            total_impuestos += iva_detalle
        
        # Asignar valores con redondeo
        self.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total_descuento = total_descuento.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total_impuestos = total_impuestos.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = (self.subtotal - self.total_descuento + self.total_impuestos).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Guardar solo los campos calculados para evitar recursión
        Proforma.objects.filter(pk=self.pk).update(
            subtotal=self.subtotal,
            total_descuento=self.total_descuento,
            total_impuestos=self.total_impuestos,
            total=self.total,
            fecha_actualizacion=timezone.now()
        )
    
    def convertir_a_factura(self, establecimiento, punto_emision, secuencial):
        """Convierte la proforma a una factura oficial"""
        if self.estado == 'CONVERTIDA':
            raise ValueError("Esta proforma ya fue convertida a factura")
        
        # Crear la factura
        factura = Factura.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            almacen=self.almacen,
            facturador=self.facturador,
            fecha_emision=datetime.date.today(),
            fecha_vencimiento=self.fecha_vencimiento,
            establecimiento=establecimiento,
            punto_emision=punto_emision,
            secuencia=secuencial,
            concepto=f"Factura generada desde proforma {self.numero}",
        )
        
        # Copiar detalles de proforma a factura
        for detalle_proforma in self.detalles.all():
            DetalleFactura.objects.create(
                factura=factura,
                empresa=self.empresa,
                producto=detalle_proforma.producto,
                servicio=detalle_proforma.servicio,
                cantidad=detalle_proforma.cantidad,
                sub_total=detalle_proforma.subtotal,
                total=detalle_proforma.total,
                descuento=detalle_proforma.descuento,
                porcentaje_descuento=detalle_proforma.porcentaje_descuento,
            )
        
        # Actualizar estado de la proforma
        self.estado = 'CONVERTIDA'
        self.factura = factura
        self.save()
        
        # Recalcular totales de la factura
        factura.calcular_totales()
        
        return factura
    
    @property
    def esta_vencida(self):
        """Verifica si la proforma está vencida"""
        from datetime import date
        return self.fecha_vencimiento < date.today()
    
    @property
    def puede_convertirse(self):
        """Verifica si la proforma puede convertirse a factura"""
        return self.estado in ['ENVIADA', 'APROBADA'] and not self.esta_vencida
    
    def __str__(self):
        return f"{self.numero} - {self.cliente.razon_social}"
    
    class Meta:
        verbose_name = "Proforma"
        verbose_name_plural = "Proformas"
        ordering = ['-fecha_creacion']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'numero'], name='unique_numero_proforma_por_empresa')
        ]


class ProformaDetalle(models.Model):
    """Detalles/líneas de una proforma"""
    proforma = models.ForeignKey(
        Proforma,
        on_delete=models.CASCADE,
        related_name='detalles',
        help_text="Proforma a la que pertenece este detalle"
    )
    
    # Producto o servicio
    producto = models.ForeignKey(
        'Producto',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Producto cotizado"
    )
    
    servicio = models.ForeignKey(
        'Servicio',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Servicio cotizado"
    )
    
    # Cantidad y precios
    cantidad = models.IntegerField(
        help_text="Cantidad de productos/servicios",
        validators=[MinValueValidator(1)]
    )
    
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio unitario del producto/servicio"
    )
    
    subtotal = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Subtotal (cantidad x precio unitario)"
    )
    
    # Descuentos
    descuento = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Descuento monetario aplicado"
    )
    
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Porcentaje de descuento aplicado"
    )
    
    # Total del detalle
    total = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total del detalle (subtotal - descuento + impuestos)"
    )
    
    def save(self, *args, **kwargs):
        """Calcula automáticamente los valores del detalle"""
        from decimal import Decimal, ROUND_HALF_UP
        
        # Validar que se asigne producto o servicio
        if not self.producto and not self.servicio:
            raise ValueError("Debe asignar un producto o servicio")
        
        # Obtener precio unitario automáticamente
        if self.producto and not self.precio_unitario:
            self.precio_unitario = self.producto.precio
        elif self.servicio and not self.precio_unitario:
            self.precio_unitario = self.servicio.precio1
        
        # Calcular subtotal
        subtotal_calculado = Decimal(str(self.precio_unitario)) * Decimal(str(self.cantidad))
        self.subtotal = subtotal_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Aplicar descuento si hay porcentaje
        if self.porcentaje_descuento > 0:
            descuento_calculado = self.subtotal * (Decimal(str(self.porcentaje_descuento)) / 100)
            self.descuento = descuento_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calcular total (por ahora sin impuestos, se calculan a nivel de proforma)
        self.total = (self.subtotal - self.descuento).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        super().save(*args, **kwargs)
        
        # Recalcular totales de la proforma padre
        if self.proforma_id:
            self.proforma.calcular_totales()
    
    def delete(self, *args, **kwargs):
        """Al eliminar un detalle, recalcula los totales de la proforma"""
        proforma = self.proforma
        super().delete(*args, **kwargs)
        proforma.calcular_totales()
    
    @property
    def descripcion(self):
        """Descripción del producto o servicio"""
        if self.producto:
            return self.producto.descripcion
        elif self.servicio:
            return self.servicio.descripcion
        return "Sin descripción"
    
    @property
    def codigo(self):
        """Código del producto o servicio"""
        if self.producto:
            return self.producto.codigo
        elif self.servicio:
            return self.servicio.codigo
        return ""
    
    def clean(self):
        """Validaciones del modelo"""
        from django.core.exceptions import ValidationError
        
        if not self.producto and not self.servicio:
            raise ValidationError("Debe asignar un producto o un servicio")
        
        if self.producto and self.servicio:
            raise ValidationError("No puede asignar producto y servicio al mismo tiempo")
    
    def __str__(self):
        return f"{self.descripcion} (Cant: {self.cantidad})"
    
    class Meta:
        verbose_name = "Detalle de Proforma"
        verbose_name_plural = "Detalles de Proforma"
        ordering = ['id']

# Función para crear detalles de factura a partir de códigos y cantidades
def crear_detalles_factura(factura, codigos, cantidades, descuentos, porcentajes_descuento, errores):
    from decimal import Decimal

    MAPEO_IVA_PORCENTAJES = {
        '0': 0.00, '5': 0.05, '2': 0.12, '10': 0.13,
        '3': 0.14, '4': 0.15, '6': 0.00, '7': 0.00, '8': 0.08
    }

    # Asegurar que la factura tenga un ID antes de crear detalles
    if not factura.pk:
        factura.save()

    for codigo, cantidad_str, descuento_str, porcentaje_str in zip(codigos, cantidades, descuentos, porcentajes_descuento):
        producto = Producto.objects.filter(empresa_id=factura.empresa_id, codigo=codigo).first()
        servicio = Servicio.objects.filter(empresa_id=factura.empresa_id, codigo=codigo).first()
        if not producto and not servicio:
            errores.append(f"Producto o servicio con código '{codigo}' no encontrado.")
            continue

        cantidad = int(cantidad_str)
        try:
            descuento = Decimal(descuento_str)
        except:
            descuento = Decimal('0.00')
        try:
            porcentaje_descuento = Decimal(porcentaje_str)
        except:
            porcentaje_descuento = Decimal('0.00')

        DetalleFactura.objects.create(
            factura=factura,
            producto=producto if producto else None,
            servicio=servicio if servicio else None,
            cantidad=cantidad,
            descuento=descuento,
            porcentaje_descuento=porcentaje_descuento,
        )

    factura.save()


# ===============================
# MODELOS DE GUÍAS DE REMISIÓN
# ===============================

class GuiaRemision(models.Model):
    """
    Modelo para las Guías de Remisión según normativa SRI Ecuador
    """
    
    # Opciones para motivo de traslado según SRI
    MOTIVOS_TRASLADO = [
        ('01', 'Venta'),
        ('02', 'Transformación'),
        ('03', 'Consignación'),
        ('04', 'Devolución'),
        ('05', 'Otros'),
    ]
    
    # Estados de la guía
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('autorizada', 'Autorizada'),
        ('anulada', 'Anulada'),
        ('devuelta', 'Devuelta'),
    ]
    
    # Campos de numeración SRI
    establecimiento = models.CharField(
        max_length=3, 
        default='001',
        help_text="Código del establecimiento (3 dígitos)"
    )
    punto_emision = models.CharField(
        max_length=3, 
        default='001',
        help_text="Código del punto de emisión (3 dígitos)"
    )
    secuencial = models.CharField(
        max_length=9,
        help_text="Número secuencial (9 dígitos)"
    )
    
    # Datos generales
    fecha_emision = models.DateField(
        default=timezone.now,
        help_text="Fecha de emisión de la guía"
    )
    fecha_inicio_traslado = models.DateTimeField(
        help_text="Fecha y hora de inicio del traslado"
    )
    fecha_fin_traslado = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha y hora de fin del traslado"
    )
    motivo_traslado = models.CharField(
        max_length=2, 
        choices=MOTIVOS_TRASLADO,
        help_text="Motivo del traslado según catálogo SRI"
    )
    
    # Datos del destinatario
    destinatario_identificacion = models.CharField(
        max_length=13,
        help_text="RUC, cédula o pasaporte del destinatario"
    )
    destinatario_nombre = models.CharField(
        max_length=300,
        help_text="Razón social o nombre del destinatario"
    )
    direccion_partida = models.TextField(
        help_text="Dirección desde donde se envía la mercadería"
    )
    direccion_destino = models.TextField(
        help_text="Dirección donde se entrega la mercadería"
    )
    
    # Datos del transportista
    transportista_ruc = models.CharField(
        max_length=13,
        help_text="RUC del transportista"
    )
    transportista_nombre = models.CharField(
        max_length=300,
        help_text="Razón social del transportista"
    )
    placa = models.CharField(
        max_length=10,
        help_text="Placa del vehículo"
    )
    transportista_observaciones = models.TextField(
        blank=True,
        help_text="Observaciones adicionales del transportista"
    )
    
    # Campos SRI para autorización electrónica
    clave_acceso = models.CharField(
        max_length=49, 
        null=True, 
        blank=True,
        unique=True,
        help_text="Clave de acceso SRI (49 dígitos)"
    )
    numero_autorizacion = models.CharField(
        max_length=37, 
        null=True, 
        blank=True,
        help_text="Número de autorización del SRI"
    )
    fecha_autorizacion = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha y hora de autorización del SRI"
    )
    xml_autorizado = models.TextField(
        null=True, 
        blank=True,
        help_text="XML autorizado por el SRI"
    )
    
    # Estado y control
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='borrador'
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones generales de la guía"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    usuario_creacion = models.ForeignKey(
        'Usuario', 
        on_delete=models.PROTECT, 
        related_name='guias_creadas',
        null=True, 
        blank=True
    )
    usuario_modificacion = models.ForeignKey(
        'Usuario', 
        on_delete=models.PROTECT, 
        related_name='guias_modificadas',
        null=True, 
        blank=True
    )
    
    class Meta:
        db_table = 'guia_remision'
        verbose_name = 'Guía de Remisión'
        verbose_name_plural = 'Guías de Remisión'
        ordering = ['-fecha_emision', '-secuencial']
        unique_together = [['establecimiento', 'punto_emision', 'secuencial']]
        indexes = [
            models.Index(fields=['fecha_emision']),
            models.Index(fields=['estado']),
            models.Index(fields=['destinatario_identificacion']),
            models.Index(fields=['clave_acceso']),
        ]
    
    def __str__(self):
        return f"Guía {self.numero_completo} - {self.destinatario_nombre}"
    
    @property
    def numero_completo(self):
        """Devuelve el número completo de la guía: 001-001-000000001"""
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial.zfill(9)}"
    
    def save(self, *args, **kwargs):
        """Override save para generar secuencial automáticamente"""
        if not self.secuencial:
            # Obtener el último secuencial para este establecimiento y punto de emisión
            ultima_guia = GuiaRemision.objects.filter(
                establecimiento=self.establecimiento,
                punto_emision=self.punto_emision
            ).order_by('-secuencial').first()
            
            if ultima_guia and ultima_guia.secuencial.isdigit():
                nuevo_secuencial = int(ultima_guia.secuencial) + 1
            else:
                nuevo_secuencial = 1
            
            self.secuencial = str(nuevo_secuencial).zfill(9)
        
        super().save(*args, **kwargs)
    
    def puede_editarse(self):
        """Determina si la guía puede editarse"""
        return self.estado == 'borrador'
    
    def puede_anularse(self):
        """Determina si la guía puede anularse"""
        return self.estado in ['borrador', 'autorizada']


class DetalleGuiaRemision(models.Model):
    """
    Modelo para los detalles de productos en la Guía de Remisión
    """
    
    guia = models.ForeignKey(
        GuiaRemision, 
        on_delete=models.CASCADE, 
        related_name='detalles',
        help_text="Guía de remisión a la que pertenece este detalle"
    )
    orden = models.PositiveIntegerField(
        default=1,
        help_text="Orden del producto en la guía"
    )
    
    # Datos del producto
    codigo_producto = models.CharField(
        max_length=50,
        help_text="Código del producto o servicio"
    )
    descripcion_producto = models.CharField(
        max_length=500,
        help_text="Descripción del producto o servicio"
    )
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text="Cantidad del producto"
    )
    
    # Campos adicionales opcionales
    unidad_medida = models.CharField(
        max_length=20,
        blank=True,
        help_text="Unidad de medida (kg, unidades, etc.)"
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones específicas del producto"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'detalle_guia_remision'
        verbose_name = 'Detalle de Guía de Remisión'
        verbose_name_plural = 'Detalles de Guías de Remisión'
        ordering = ['orden', 'id']
        indexes = [
            models.Index(fields=['guia', 'orden']),
            models.Index(fields=['codigo_producto']),
        ]
    
    def __str__(self):
        return f"{self.codigo_producto} - {self.descripcion_producto[:50]}"


class ConfiguracionGuiaRemision(models.Model):
    """
    Modelo para la configuración del módulo de Guías de Remisión
    """
    
    # Configuración de numeración
    establecimiento_defecto = models.CharField(
        max_length=3,
        default='001',
        help_text="Establecimiento por defecto para nuevas guías"
    )
    punto_emision_defecto = models.CharField(
        max_length=3,
        default='001',
        help_text="Punto de emisión por defecto para nuevas guías"
    )
    
    # Configuración de empresa
    nombre_comercial = models.CharField(
        max_length=300,
        blank=True,
        help_text="Nombre comercial para los documentos"
    )
    direccion_matriz = models.TextField(
        blank=True,
        help_text="Dirección de la matriz para las guías"
    )
    
    # Configuración SRI
    ambiente_sri = models.CharField(
        max_length=1,
        choices=[('1', 'Pruebas'), ('2', 'Producción')],
        default='1',
        help_text="Ambiente del SRI"
    )
    tipo_emision = models.CharField(
        max_length=1,
        choices=[('1', 'Emisión Normal'), ('2', 'Emisión por Indisponibilidad')],
        default='1',
        help_text="Tipo de emisión"
    )
    
    # Configuración de plantilla PDF
    mostrar_logo = models.BooleanField(
        default=True,
        help_text="Mostrar logo en el PDF"
    )
    ruta_logo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ruta del archivo de logo"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    usuario_modificacion = models.ForeignKey(
        'Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'configuracion_guia_remision'
        verbose_name = 'Configuración de Guías de Remisión'
        verbose_name_plural = 'Configuraciones de Guías de Remisión'
    
    def __str__(self):
        return f"Configuración Guías de Remisión - {self.establecimiento_defecto}-{self.punto_emision_defecto}"
    
    @classmethod
    def get_configuracion(cls):
        """Obtiene la configuración activa, crea una por defecto si no existe"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'establecimiento_defecto': '001',
                'punto_emision_defecto': '001',
                'ambiente_sri': '1',
                'tipo_emision': '1',
                'mostrar_logo': True,
            }
        )
        return config