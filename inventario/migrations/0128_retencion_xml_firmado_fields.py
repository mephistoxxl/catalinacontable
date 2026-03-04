from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0127_retencion_xml_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='comprobanteretencion',
            name='xml_firmado',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='comprobanteretencion',
            name='xml_firmado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
