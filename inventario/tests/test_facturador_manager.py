import os

import django
import pytest
from django.apps import apps
from django.db import connection
from django.test import Client
from django.urls import reverse

os.environ.setdefault('DATABASE_URL', 'sqlite:///test_db.sqlite3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Facturador, Usuario, UsuarioEmpresa


@pytest.fixture(scope='session', autouse=True)
def _ensure_schema():
    with connection.schema_editor() as schema_editor:
        existing = set(connection.introspection.table_names())
        for model in apps.get_models():
            if not model._meta.managed:
                continue
            table = model._meta.db_table
            if table in existing:
                continue
            try:
                schema_editor.create_model(model)
            except Exception:
                continue
            existing.add(table)


def test_facturador_manager_create_facturador():
    empresa = Empresa.objects.create(
        razon_social='Empresa Test',
        ruc='0777777777001',
    )

    facturador = Facturador.objects.create_facturador(
        nombres='Facturador Uno',
        telefono='0999999999',
        correo='facturador1@example.com',
        password='Secreta123',
        empresa=empresa,
    )

    assert facturador.pk is not None
    assert facturador.empresa == empresa
    assert facturador.check_password('Secreta123')
    assert facturador.password != 'Secreta123'


def test_crear_facturador_view_uses_manager():
    empresa = Empresa.objects.create(
        razon_social='Empresa Vista',
        ruc='0666666666001',
    )
    usuario = Usuario.objects.create_user(
        username='admin',
        password='supersegura',
        email='admin@example.com',
    )
    UsuarioEmpresa._unsafe_objects.create(usuario=usuario, empresa=empresa)

    client = Client()
    client.defaults['HTTP_HOST'] = 'localhost'
    client.force_login(usuario)
    session = client.session
    session['empresa_activa'] = empresa.id
    session.save()

    response = client.post(
        reverse('inventario:crear_facturador'),
        data={
            'nombres': 'Nuevo Facturador',
            'telefono': '0976543210',
            'correo': 'nuevofacturador@example.com',
            'password': 'ClaveFuerte1',
            'verificar_password': 'ClaveFuerte1',
            'descuento_permitido': '5.00',
            'activo': 'on',
        },
        follow=True,
    )

    assert response.status_code == 200
    facturador = Facturador.objects.get(correo='nuevofacturador@example.com')
    assert facturador.empresa == empresa
    assert facturador.check_password('ClaveFuerte1')
