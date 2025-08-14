from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0071_factura_estado_sri_factura_fecha_autorizacion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='estado',
            field=models.CharField(
                max_length=20,
                default='PENDIENTE',
                choices=[
                    ('PENDIENTE', 'Pendiente'),
                    ('RECIBIDA', 'Recibida'),
                    ('AUTORIZADO', 'Autorizado'),
                    ('RECHAZADO', 'Rechazado'),
                    ('ERROR', 'Error'),
                ],
                help_text='Estado interno del flujo',
            ),
        ),
    ]


