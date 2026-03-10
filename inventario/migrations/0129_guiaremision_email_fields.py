from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0128_retencion_xml_firmado_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='guiaremision',
            name='email_enviado',
            field=models.BooleanField(default=False, help_text='Indica si ya se envió el correo con XML/RIDE de la guía'),
        ),
        migrations.AddField(
            model_name='guiaremision',
            name='email_enviado_at',
            field=models.DateTimeField(blank=True, help_text='Fecha/hora del primer envío exitoso de la guía', null=True),
        ),
        migrations.AddField(
            model_name='guiaremision',
            name='email_envio_intentos',
            field=models.PositiveSmallIntegerField(default=0, help_text='Número de intentos (exitosos + fallidos) de envío de la guía'),
        ),
        migrations.AddField(
            model_name='guiaremision',
            name='email_ultimo_error',
            field=models.TextField(blank=True, help_text='Último error registrado al intentar enviar correo de la guía', null=True),
        ),
    ]