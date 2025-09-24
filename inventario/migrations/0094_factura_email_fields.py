from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0093_alter_secuencia_unique_together_alter_usuario_nivel_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='email_enviado',
            field=models.BooleanField(default=False, help_text='Indica si ya se envió el correo con XML/RIDE al cliente'),
        ),
        migrations.AddField(
            model_name='factura',
            name='email_enviado_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Fecha/hora del primer envío exitoso'),
        ),
        migrations.AddField(
            model_name='factura',
            name='email_envio_intentos',
            field=models.PositiveSmallIntegerField(default=0, help_text='Número de intentos (exitosos + fallidos) de envío'),
        ),
        migrations.AddField(
            model_name='factura',
            name='email_ultimo_error',
            field=models.TextField(blank=True, null=True, help_text='Último error registrado al intentar enviar correo'),
        ),
    ]
