from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0122_alter_factura_estado_sri_notadebito_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresaplan',
            name='notificacion_limite_enviada',
            field=models.BooleanField(
                default=False,
                help_text='Se envió notificación al alcanzar el 100% del límite',
                verbose_name='Notificación Límite Enviada',
            ),
        ),
    ]
