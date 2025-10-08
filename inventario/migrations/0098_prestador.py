from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0097_alter_opciones_firma_electronica"),
    ]

    operations = [
        migrations.CreateModel(
            name="Prestador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prestadores", to="inventario.empresa")),
                ("tipo_identificacion", models.CharField(choices=[("04", "RUC"), ("05", "Cédula"), ("06", "Pasaporte"), ("07", "Consumidor final"), ("08", "Identificación del exterior")], max_length=2)),
                ("identificacion", models.CharField(max_length=13)),
                ("nombre", models.CharField(max_length=255)),
                ("nombre_comercial", models.CharField(blank=True, max_length=255)),
                ("direccion", models.CharField(blank=True, max_length=255)),
                ("correo", models.EmailField(blank=True, max_length=200)),
                ("telefono", models.CharField(blank=True, max_length=50)),
                ("obligado_contabilidad", models.CharField(choices=[("SI", "Sí"), ("NO", "No")], default="NO", max_length=2)),
                ("tipo_contribuyente", models.CharField(blank=True, max_length=150)),
                ("actividad_economica", models.CharField(blank=True, max_length=255)),
                ("estado", models.CharField(blank=True, max_length=120)),
                ("tipo_regimen", models.CharField(blank=True, max_length=120)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("liquidacion", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="prestador", to="inventario.liquidacioncompra")),
                ("proveedor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="prestadores", to="inventario.proveedor")),
            ],
            options={
                "verbose_name": "Prestador",
                "verbose_name_plural": "Prestadores",
            },
        ),
        migrations.AddIndex(
            model_name="prestador",
            index=models.Index(fields=["identificacion"], name="inventario_identifi_60b0e6_idx"),
        ),
        migrations.AddIndex(
            model_name="prestador",
            index=models.Index(fields=["tipo_identificacion", "identificacion"], name="inventario_tipo_id_7284f2_idx"),
        ),
        migrations.AddIndex(
            model_name="prestador",
            index=models.Index(fields=["empresa", "identificacion"], name="inventario_empresas_4f6988_idx"),
        ),
    ]
