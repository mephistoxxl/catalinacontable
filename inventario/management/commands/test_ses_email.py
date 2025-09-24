from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage
from django.conf import settings
import json
import os
import traceback

try:  # pragma: no cover - entorno sin boto3
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    boto3 = None
    ClientError = None


class Command(BaseCommand):
    help = "Envía un correo de prueba usando la configuración actual (Anymail/SES)."

    def add_arguments(self, parser):
        parser.add_argument('--to', dest='to', required=True, help='Correo destino para la prueba (cliente)')
        parser.add_argument('--cc', dest='cc', help='Correo(s) CC separados por coma (sobrescribe empresa)')
        parser.add_argument('--empresa-id', dest='empresa_id', type=int, help='Tomar correo de la empresa como CC si existe')
        parser.add_argument('--subject', dest='subject', default='Prueba SES', help='Asunto opcional')
        parser.add_argument('--body', dest='body', default='Correo de prueba SES/Anymail OK', help='Cuerpo opcional')
        parser.add_argument('--raw', action='store_true', help='Usar EmailMessage en lugar de send_mail')
        parser.add_argument('--attach-dummy', action='store_true', help='Adjunta un archivo de texto de prueba')
        parser.add_argument('--no-diag', action='store_true', help='Omite diagnóstico previo de SES')

    def _friendly_ses_error(self, exc, to_addr):  # pragma: no cover (difícil de forzar en tests locales)
        lines = []
        msg = str(exc)
        backend = settings.EMAIL_BACKEND
        from_addr = settings.DEFAULT_FROM_EMAIL
        lines.append('\n=== Diagnóstico SES (MessageRejected) ===')
        # Causas típicas
        sandbox_hints = [
            '- La cuenta SES probablemente está en SANDBOX (cuota 200/24h y rate 1.0).',
            f"- Debes VERIFICAR el dominio del remitente (recomendado) o al menos la dirección: {from_addr}.",
            f"- Mientras sigas en sandbox, cada destinatario externo debe estar verificado (incluyendo: {to_addr}).",
            '- Alternativa inmediata: Verifica el correo destino en la consola SES (Identities > Verify new email address).',
            '- Solución definitiva: Solicita SALIDA DE SANDBOX (Request production access).',
        ]
        if 'Email address is not verified' in msg:
            lines.append('Motivo: Dirección remitente/destino no verificada para este entorno sandbox.')
        lines.extend(sandbox_hints)
        lines.append('\nPasos recomendados:')
        lines.append('  1. En SES > Verified identities: Add identity > Domain -> alpca.ec')
        lines.append('  2. Añadir registros DNS: TXT de verificación + 3 CNAME DKIM que entrega SES.')
        lines.append('  3. (Opcional) SPF: v=spf1 include:amazonses.com ~all (si no existe otro SPF)')
        lines.append('  4. (Opcional) DMARC: _dmarc.alpca.ec  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@alpca.ec"')
        lines.append('  5. Esperar propagación DNS (5-30 min).')
        lines.append('  6. Solicitar producción: SES > Account dashboard > Request production access.')
        lines.append('     - Use case: Envío transaccional de facturas electrónicas autorizadas (SRI Ecuador).')
        lines.append('     - Volumen esperado y plan de manejo de rebotes/quejas (bounces/complaints).')
        lines.append('  7. Una vez fuera de sandbox solo necesitas verificar el dominio remitente.')
        lines.append('\nMientras tanto puedes:')
        lines.append('  - Verificar el email destino puntual para esta prueba.')
        lines.append('  - Reintentar este comando tras la verificación.')
        lines.append('\nInformación técnica capturada:')
        lines.append(f'  Backend: {backend}')
        lines.append(f'  FROM: {from_addr}')
        return '\n'.join(lines)

    def handle(self, *args, **options):
        to = options['to']
        subject = options['subject']
        body = options['body']
        backend = settings.EMAIL_BACKEND
        self.stdout.write(self.style.NOTICE(f"Backend actual: {backend}"))
        self.stdout.write(self.style.NOTICE(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}"))

        anymail_cfg = getattr(settings, 'ANYMAIL', {})
        if anymail_cfg:
            self.stdout.write(self.style.NOTICE(f"ANYMAIL config: {json.dumps(anymail_cfg, indent=2)}"))
        else:
            self.stdout.write(self.style.WARNING('ANYMAIL no está configurado (backend SMTP o consola).'))

        # Diagnóstico SES básico
        if not options['no_diag'] and boto3:
            try:
                region = (anymail_cfg.get('AMAZON_SES_CLIENT_PARAMS', {}) or {}).get('region_name') or os.environ.get('AWS_SES_REGION_NAME') or 'us-east-1'
                ses_client = boto3.client('ses', region_name=region)
                quota = ses_client.get_send_quota()
                max24 = float(quota.get('Max24HourSend') or 0)
                sent24 = float(quota.get('SentLast24Hours') or 0)
                remaining = max24 - sent24
                rate = quota.get('MaxSendRate')
                self.stdout.write(self.style.NOTICE(f"SES Quota: Max24h={max24} Sent24h={sent24} Remaining={remaining} Rate={rate}"))
                if max24 <= 200 and rate <= 1:
                    self.stdout.write(self.style.WARNING('Indicio: Cuenta aún en sandbox (límite 200/24h y 1 msg/seg).'))
            except Exception as e:  # pragma: no cover
                self.stdout.write(self.style.WARNING(f"No se pudo obtener cuota SES: {e}"))

        # Determinar CC
        cc_list = []
        if options.get('cc'):
            cc_list = [c.strip() for c in options['cc'].split(',') if c.strip()]
        elif options.get('empresa_id'):
            try:
                from inventario.models import Empresa
                emp = Empresa.objects.filter(id=options['empresa_id']).first()
                if emp and emp.correo:
                    if emp.correo != to:
                        cc_list.append(emp.correo)
                        self.stdout.write(self.style.NOTICE(f"CC empresa: {emp.correo}"))
            except Exception as e:  # pragma: no cover
                self.stdout.write(self.style.WARNING(f"No se pudo obtener empresa para CC: {e}"))

        try:
            email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [to], cc=cc_list)
            if options['attach_dummy']:
                email.attach('prueba.txt', b'Archivo de prueba de adjunto SES', 'text/plain')
            email.send(fail_silently=False)
        except Exception as exc:
            # Manejo especial sandbox SES
            if ClientError and isinstance(exc, ClientError):  # pragma: no cover
                code = exc.response.get('Error', {}).get('Code')
                if code == 'MessageRejected':
                    self.stdout.write(self.style.ERROR(self._friendly_ses_error(exc, to)))
            # Siempre elevar CommandError al final
            detail = f"Error enviando correo: {exc}\n"
            detail += ''.join(traceback.format_exception_only(type(exc), exc))
            raise CommandError(detail) from exc

        destino = to + (f" (cc: {', '.join(cc_list)})" if cc_list else '')
        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {destino}"))
