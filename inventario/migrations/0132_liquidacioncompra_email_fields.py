from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0131_notadebito_email_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='liquidacioncompra',
            name='email_enviado',
            field=models.BooleanField(default=False, help_text='Indica si ya se envió el correo con XML de la liquidación de compra'),
        ),
        migrations.AddField(
            model_name='liquidacioncompra',
            name='email_enviado_at',
            field=models.DateTimeField(blank=True, help_text='Fecha/hora del primer envío exitoso de la liquidación de compra', null=True),
        ),
        migrations.AddField(
            model_name='liquidacioncompra',
            name='email_envio_intentos',
            field=models.PositiveSmallIntegerField(default=0, help_text='Número de intentos de envío de la liquidación de compra'),
        ),
        migrations.AddField(
            model_name='liquidacioncompra',
            name='email_ultimo_error',
            field=models.TextField(blank=True, help_text='Último error registrado al intentar enviar correo de la liquidación de compra', null=True),
        ),
    ]