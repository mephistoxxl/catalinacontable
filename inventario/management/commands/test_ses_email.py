from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba usando la configuración SMTP activa."

    def add_arguments(self, parser):
        parser.add_argument('--to', dest='to', required=True, help='Correo destino para la prueba')
        parser.add_argument('--subject', dest='subject', default='Prueba de envío', help='Asunto opcional')
        parser.add_argument(
            '--body',
            dest='body',
            default='Correo de prueba enviado correctamente con la configuración SMTP actual.',
            help='Cuerpo opcional',
        )
        parser.add_argument('--cc', dest='cc', help='Correos CC separados por coma')

    def handle(self, *args, **options):
        destinatario = options['to']
        asunto = options['subject']
        cuerpo = options['body']

        backend = settings.EMAIL_BACKEND
        host = getattr(settings, 'EMAIL_HOST', '(no definido)')
        usuario = getattr(settings, 'EMAIL_HOST_USER', '(no definido)')
        remitente = settings.DEFAULT_FROM_EMAIL

        self.stdout.write(self.style.NOTICE(f"Backend: {backend}"))
        self.stdout.write(self.style.NOTICE(f"Servidor SMTP: {host}"))
        self.stdout.write(self.style.NOTICE(f"Usuario SMTP: {usuario}"))
        self.stdout.write(self.style.NOTICE(f"Remitente por defecto: {remitente}"))

        cc_list = []
        if options.get('cc'):
            cc_list = [correo.strip() for correo in options['cc'].split(',') if correo.strip()]

        try:
            mensaje = EmailMessage(asunto, cuerpo, remitente, [destinatario], cc=cc_list)
            mensaje.send(fail_silently=False)
        except Exception as exc:
            raise CommandError(f"No se pudo enviar el correo de prueba: {exc}") from exc

        destino = destinatario + (f" (cc: {', '.join(cc_list)})" if cc_list else '')
        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {destino}"))
