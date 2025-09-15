from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0091_alter_opciones_options_remove_opciones_valor_iva_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuarioempresa',
            name='email_empresa',
            field=models.EmailField(blank=True, help_text='Correo específico para esta empresa (override opcional)', max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='usuarioempresa',
            name='nivel_empresa',
            field=models.IntegerField(blank=True, help_text='Rol específico en esta empresa (override de nivel global)', null=True),
        ),
        migrations.AddField(
            model_name='usuarioempresa',
            name='alias',
            field=models.CharField(blank=True, help_text='Nombre/alias a mostrar en esta empresa', max_length=120, null=True),
        ),
    ]
