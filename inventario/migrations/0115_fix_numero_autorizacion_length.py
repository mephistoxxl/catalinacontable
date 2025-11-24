# Generated migration to fix numero_autorizacion field length

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0114_remove_mensaje_nombre_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guiaremision',
            name='numero_autorizacion',
            field=models.CharField(max_length=49, null=True, blank=True),
        ),
    ]
