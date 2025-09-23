from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import json


class Command(BaseCommand):
    help = "Envía un correo de prueba usando la configuración actual (Anymail/SES)."

    def add_arguments(self, parser):
        parser.add_argument('--to', dest='to', required=True, help='Correo destino para la prueba')
        parser.add_argument('--subject', dest='subject', default='Prueba SES', help='Asunto opcional')
        parser.add_argument('--body', dest='body', default='Correo de prueba SES/Anymail OK', help='Cuerpo opcional')
        parser.add_argument('--raw', action='store_true', help='Usar EmailMessage en lugar de send_mail')

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

        try:
            if options['raw']:
                email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
                email.send(fail_silently=False)
            else:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        except Exception as exc:
            raise CommandError(f"Error enviando correo: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {to}"))
