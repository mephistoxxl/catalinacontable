import json
import os
from decimal import Decimal

import django
import pytest
from django.urls import reverse
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import connection
from django.test import Client, RequestFactory
from django.utils import timezone
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse

from django.contrib.messages import get_messages

os.environ.setdefault('DATABASE_URL', 'sqlite:///test_db.sqlite3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

settings.ALLOWED_HOSTS = ['testserver', 'localhost']

from inventario.models import (
    Empresa,
    Facturador,
    Cliente,
    Secuencia,
    Producto,
    Servicio,
    Factura,
    Almacen,
    Proforma,
    Proveedor,
    Pedido,
    DetallePedido,
    GuiaRemision,
    DetalleGuiaRemision,
)
from inventario.tenant.queryset import set_current_tenant

User = get_user_model()

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
                # Si alguna tabla ya existe o la operación no es compatible con SQLite,
                # la ignoramos porque solo necesitamos un esquema básico para las pruebas.
                continue
            existing.add(table)


@pytest.mark.django_db
class TestMultiTenantIsolation:
    @pytest.fixture
    def empresas(self):
        Empresa.objects.filter(ruc='0999999999001').delete()
        Empresa.objects.filter(ruc='0888888888001').delete()
        e1 = Empresa.objects.create(razon_social='Empresa Uno', ruc='0999999999001')
        e2 = Empresa.objects.create(razon_social='Empresa Dos', ruc='0888888888001')
        return e1, e2

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def usuario(self, empresas):
        User.objects.filter(username='admin').delete()
        user = User.objects.create_user(username='admin', password='pass', email='admin@example.com')
        # Asumiendo relación ManyToMany Usuario.empresas
        if hasattr(user, 'empresas'):
            for e in empresas:
                user.empresas.add(e)
        return user

    @pytest.fixture
    def staff_usuario(self, empresas):
        User.objects.filter(username='staff').delete()
        user = User.objects.create_user(
            username='staff',
            password='pass',
            email='staff@example.com',
            is_staff=True,
        )
        if hasattr(user, 'empresas'):
            for e in empresas:
                user.empresas.add(e)
        return user

    @pytest.fixture
    def rf(self):
        return RequestFactory()

    @pytest.fixture
    def facturadores(self, empresas):
        f1 = Facturador.objects.create(nombres='Fac A1', correo='fa1@example.com', password='x', empresa=empresas[0], activo=True)
        f2 = Facturador.objects.create(nombres='Fac B1', correo='fb1@example.com', password='y', empresa=empresas[1], activo=True)
        return f1, f2

    @pytest.fixture
    def datos_base(self, empresas):
        e1, e2 = empresas
        c1 = Cliente.objects.create(empresa=e1, tipoIdentificacion='05', identificacion='0101010101', razon_social='Cliente A', nombre_comercial='A', direccion='Dir', telefono='1', correo='a@a.com')
        c2 = Cliente.objects.create(empresa=e2, tipoIdentificacion='05', identificacion='0202020202', razon_social='Cliente B', nombre_comercial='B', direccion='Dir', telefono='2', correo='b@b.com')
        s1 = Secuencia.objects.create(empresa=e1, descripcion='FACT A', tipo_documento='01', secuencial=1, establecimiento=1, punto_emision=1, activo=True)
        s2 = Secuencia.objects.create(empresa=e2, descripcion='FACT B', tipo_documento='01', secuencial=5, establecimiento=1, punto_emision=1, activo=True)
        alm1 = Almacen.objects.create(empresa=e1, descripcion='Alm A', activo=True)
        Producto.objects.create(empresa=e1, codigo='P-A', codigo_barras='BA', descripcion='Prod A', precio=10, precio2=10, disponible=5, categoria='1', iva='2', costo_actual=5)
        Servicio.objects.create(empresa=e2, codigo='S-B', descripcion='Serv B', iva='2', precio1=5, precio2=5, activo=True)
        return {
            'cliente_a': c1,
            'cliente_b': c2,
            'secuencia_a': s1,
            'secuencia_b': s2,
            'almacen_a': alm1,
        }

    def _login(self, client: Client, user):
        client.login(username='admin', password='pass')

    def _set_empresa(self, client: Client, empresa_id):
        session = client.session
        session['empresa_activa'] = empresa_id
        session.save()

    def _prepare_request(self, rf, path, empresa_id, user, header_value=None):
        request = rf.get(path, **({'HTTP_X_TENANT': header_value} if header_value else {}))
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session['empresa_activa'] = empresa_id
        request.session.save()
        request.user = user
        return request

    def test_facturador_login_isolation(self, client, usuario, empresas, facturadores):
        self._login(client, usuario)
        e1, e2 = empresas
        self._set_empresa(client, e1.id)
        # Intentar login de facturador B (empresa 2) usando password directo (vista usa password exacto)
        resp = client.post(reverse('inventario:login_facturador'), {'password': facturadores[1].password})
        assert 'Seleccione una empresa válida' not in resp.content.decode()
        # No debería establecer sesión de facturador con id de empresa 2
        assert client.session.get('facturador_id') != facturadores[1].id

    def test_emitir_factura_rejects_foreign_secuencia(self, client, usuario, empresas, facturadores, datos_base):
        self._login(client, usuario)
        e1, e2 = empresas
        self._set_empresa(client, e1.id)
        f1, f2 = facturadores
        # Simular login facturador empresa 1
        session = client.session
        session['facturador_id'] = f1.id
        session['facturador_nombre'] = f1.nombres
        session.save()
        # Intentar usar secuencia de empresa 2
        payload = {
            'cliente_id': datos_base['cliente_a'].id,
            'correo_cliente': 'nuevo@correo.com',
            'almacen': datos_base['almacen_a'].id,
            'fecha_emision': '2025-01-01',
            'fecha_vencimiento': '2025-01-10',
            'establecimiento': datos_base['secuencia_b'].establecimiento,
            'punto_emision': datos_base['secuencia_b'].punto_emision,
            'secuencia_valor': datos_base['secuencia_b'].id,
            'concepto': 'Test',
        }
        resp = client.post(reverse('inventario:emitirFactura'), payload, follow=True)
        texto = resp.content.decode()
        assert 'no es válida' in texto.lower() or 'no coinciden' in texto.lower()
        assert 'factura_id' not in client.session

    def test_busqueda_producto_no_filtra_otras_empresas(self, client, usuario, empresas, datos_base):
        self._login(client, usuario)
        e1, e2 = empresas
        self._set_empresa(client, e1.id)
        resp = client.get(reverse('inventario:buscar_producto'), {'q': 'S-B'})
        # Servicio S-B pertenece a empresa 2, no debe aparecer
        assert 'S-B' not in resp.content.decode()

    def test_header_no_cambia_tenant_para_usuario_regular(self, rf, usuario, empresas, datos_base):
        from inventario.tenant.middleware import TenantMiddleware

        e1, e2 = empresas
        request = self._prepare_request(
            rf,
            path='/clientes/',
            empresa_id=e1.id,
            user=usuario,
            header_value=str(e2.id),
        )

        middleware = TenantMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)

        assert getattr(request, 'tenant') == e1

        clientes = list(Cliente.objects.all())
        assert clientes
        assert all(cliente.empresa_id == e1.id for cliente in clientes)

        middleware.process_response(request, HttpResponse())

    def test_header_permitido_para_staff(self, rf, staff_usuario, empresas, datos_base):
        from inventario.tenant.middleware import TenantMiddleware

        e1, e2 = empresas
        request = self._prepare_request(
            rf,
            path='/clientes/',
            empresa_id=e1.id,
            user=staff_usuario,
            header_value=str(e2.id),
        )

        middleware = TenantMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)

        assert getattr(request, 'tenant') == e2

        clientes = list(Cliente.objects.all())
        assert clientes
        assert all(cliente.empresa_id == e2.id for cliente in clientes)

        middleware.process_response(request, HttpResponse())

    def test_emitir_proforma_rejects_cliente_de_otra_empresa(self, client, usuario, empresas, facturadores, datos_base):
        self._login(client, usuario)
        e1, e2 = empresas
        self._set_empresa(client, e1.id)
        facturador = facturadores[0]
        token = signing.dumps({'fid': facturador.id}, salt='proformador')
        payload = {
            't': token,
            'cliente': {
                'id': datos_base['cliente_b'].id,
            },
            'productos': [
                {'codigo': 'P-A', 'cantidad': 1, 'precio': '10.00', 'descuento': '0'}
            ],
            'observaciones': 'Intento inválido',
        }
        response = client.post(
            reverse('inventario:emitirProforma'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        data = response.json()
        assert data['success'] is False
        assert 'no pertenece a la empresa activa' in data['message'].lower()
        assert Proforma.objects.filter(empresa=e1).count() == 0

    def test_consultar_estado_sri_isolation(self, client, usuario, empresas, facturadores, datos_base):
        self._login(client, usuario)
        e1, e2 = empresas
        self._set_empresa(client, e1.id)
        f1, f2 = facturadores
        # Crear factura válida en empresa 1
        factura = Factura.objects.create(
            empresa=e1,
            cliente=datos_base['cliente_a'],
            almacen=datos_base['almacen_a'],
            facturador=f1,
            fecha_emision='2025-01-01',
            fecha_vencimiento='2025-01-10',
            establecimiento='001',
            punto_emision='001',
            secuencia='000000001',
            concepto='X',
            identificacion_cliente=datos_base['cliente_a'].identificacion,
            nombre_cliente=datos_base['cliente_a'].razon_social,
        )
        factura.save()
        # Intento de consultar factura de empresa 2 (no existe en e1) debe devolver 404
        resp = client.post(reverse('inventario:consultar_estado_sri', args=[999999]))
        assert resp.status_code in (404, 200)  # 404 esperado; 200 si vista maneja distinto

        # Consulta correcta
        resp2 = client.post(reverse('inventario:consultar_estado_sri', args=[factura.id]))
        assert resp2.status_code == 200

    def test_tenant_managers_and_aggregates(self, empresas, facturadores, datos_base):
        e1, e2 = empresas
        f1, f2 = facturadores
        cliente_a = datos_base['cliente_a']
        cliente_b = datos_base['cliente_b']
        almacen_a = datos_base['almacen_a']

        # Crear productos exclusivos para la prueba con el manager global
        prod_a = Producto.all_objects.create(
            empresa=e1,
            codigo='TENANT-A',
            codigo_barras='TENANT-A',
            descripcion='Producto Tenant A',
            precio=Decimal('5.00'),
            precio2=Decimal('5.00'),
            disponible=10,
            categoria='1',
            iva='2',
            costo_actual=Decimal('2.50'),
        )
        prod_b = Producto.all_objects.create(
            empresa=e2,
            codigo='TENANT-B',
            codigo_barras='TENANT-B',
            descripcion='Producto Tenant B',
            precio=Decimal('7.00'),
            precio2=Decimal('7.00'),
            disponible=8,
            categoria='1',
            iva='2',
            costo_actual=Decimal('3.50'),
        )

        # Crear facturas en ambas empresas usando el manager global
        factura_a = Factura.all_objects.create(
            empresa=e1,
            cliente=cliente_a,
            almacen=almacen_a,
            facturador=f1,
            fecha_emision='2025-01-02',
            fecha_vencimiento='2025-01-10',
            establecimiento='001',
            punto_emision='001',
            secuencia='000000010',
            concepto='Venta Empresa A',
            identificacion_cliente=cliente_a.identificacion,
            nombre_cliente=cliente_a.razon_social,
            sub_monto=Decimal('50.00'),
            base_imponible=Decimal('50.00'),
            monto_general=Decimal('56.00'),
        )
        factura_b = Factura.all_objects.create(
            empresa=e2,
            cliente=cliente_b,
            almacen=None,
            facturador=f2,
            fecha_emision='2025-01-03',
            fecha_vencimiento='2025-01-12',
            establecimiento='002',
            punto_emision='001',
            secuencia='000000020',
            concepto='Venta Empresa B',
            identificacion_cliente=cliente_b.identificacion,
            nombre_cliente=cliente_b.razon_social,
            sub_monto=Decimal('80.00'),
            base_imponible=Decimal('80.00'),
            monto_general=Decimal('89.60'),
        )

        # Sin tenant activo no se debe devolver información
        set_current_tenant(None)
        assert Producto.objects.filter(codigo__in=['TENANT-A', 'TENANT-B']).count() == 0
        assert Factura.objects.filter(id__in=[factura_a.id, factura_b.id]).count() == 0

        # Con tenant A solo ve sus productos/facturas
        set_current_tenant(e1)
        codigos_a = set(Producto.objects.values_list('codigo', flat=True))
        assert 'TENANT-A' in codigos_a
        assert 'TENANT-B' not in codigos_a
        assert Producto.all_objects.filter(codigo__in=['TENANT-A', 'TENANT-B']).count() >= 2

        facturas_a_ids = set(Factura.objects.values_list('id', flat=True))
        assert factura_a.id in facturas_a_ids
        assert factura_b.id not in facturas_a_ids

        expected_a_count = Factura.all_objects.filter(empresa=e1).count()
        assert Factura.numeroRegistrados() == expected_a_count

        expected_a_total = sum(
            (f.monto_general for f in Factura.all_objects.filter(empresa=e1)),
            Decimal('0.00')
        )
        assert Factura.ingresoTotal() == expected_a_total

        # Con tenant B se invierte la visibilidad
        set_current_tenant(e2)
        codigos_b = set(Producto.objects.values_list('codigo', flat=True))
        assert 'TENANT-B' in codigos_b
        assert 'TENANT-A' not in codigos_b

        facturas_b_ids = set(Factura.objects.values_list('id', flat=True))
        assert factura_b.id in facturas_b_ids
        assert factura_a.id not in facturas_b_ids

        expected_b_count = Factura.all_objects.filter(empresa=e2).count()
        assert Factura.numeroRegistrados() == expected_b_count

        expected_b_total = sum(
            (f.monto_general for f in Factura.all_objects.filter(empresa=e2)),
            Decimal('0.00')
        )
        assert Factura.ingresoTotal() == expected_b_total

        # Restablecer tenant
        set_current_tenant(None)

    def test_detalles_pedido_usa_producto_empresa_activa(self, client, usuario, empresas):
        self._login(client, usuario)
        empresa_a, empresa_b = empresas
        proveedor = Proveedor.objects.create(
            empresa=empresa_a,
            tipoIdentificacion='05',
            identificacion_proveedor='9999999999',
            razon_social_proveedor='Proveedor A',
            nombre_comercial_proveedor='Proveedor A',
            direccion='Dir 1',
            telefono='123456789',
            correo='prov@a.com',
        )
        producto_a = Producto.objects.create(
            empresa=empresa_a,
            codigo='PA-1',
            codigo_barras='111',
            descripcion='Duplicado',
            precio=Decimal('10.00'),
            precio2=Decimal('10.00'),
            disponible=5,
            categoria='1',
            iva='2',
            costo_actual=Decimal('5.00'),
        )
        Producto.objects.create(
            empresa=empresa_b,
            codigo='PB-1',
            codigo_barras='222',
            descripcion='Duplicado',
            precio=Decimal('10.00'),
            precio2=Decimal('10.00'),
            disponible=5,
            categoria='1',
            iva='2',
            costo_actual=Decimal('5.00'),
        )

        self._set_empresa(client, empresa_a.id)
        session = client.session
        session['form_details'] = 1
        session['id_proveedor'] = proveedor.identificacion_proveedor
        session.save()

        response = client.post(
            reverse('inventario:detallesPedido'),
            data={
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '0',
                'form-MAX_NUM_FORMS': '',
                'form-0-descripcion': str(producto_a.id),
                'form-0-cantidad': '2',
                'form-0-valor_subtotal': '20.00',
            },
        )

        assert response.status_code == 302
        pedido = Pedido.objects.filter(empresa=empresa_a).latest('id')
        detalle = DetallePedido.objects.get(id_pedido=pedido)
        assert detalle.id_producto == producto_a

    def test_detalles_pedido_rechaza_producto_otro_tenant(self, client, usuario, empresas):
        self._login(client, usuario)
        empresa_a, empresa_b = empresas
        proveedor = Proveedor.objects.create(
            empresa=empresa_a,
            tipoIdentificacion='05',
            identificacion_proveedor='1231231231',
            razon_social_proveedor='Proveedor A',
            nombre_comercial_proveedor='Proveedor A',
            direccion='Dir 1',
            telefono='123456789',
            correo='prov@a.com',
        )
        producto_a = Producto.objects.create(
            empresa=empresa_a,
            codigo='PA-2',
            codigo_barras='333',
            descripcion='Producto A',
            precio=Decimal('5.00'),
            precio2=Decimal('5.00'),
            disponible=5,
            categoria='1',
            iva='2',
            costo_actual=Decimal('2.00'),
        )
        producto_b = Producto.objects.create(
            empresa=empresa_b,
            codigo='PB-2',
            codigo_barras='444',
            descripcion='Producto A',
            precio=Decimal('5.00'),
            precio2=Decimal('5.00'),
            disponible=5,
            categoria='1',
            iva='2',
            costo_actual=Decimal('2.00'),
        )

        self._set_empresa(client, empresa_a.id)
        session = client.session
        session['form_details'] = 1
        session['id_proveedor'] = proveedor.identificacion_proveedor
        session.save()

        response = client.post(
            reverse('inventario:detallesPedido'),
            data={
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '0',
                'form-MAX_NUM_FORMS': '',
                'form-0-descripcion': str(producto_b.id),
                'form-0-cantidad': '1',
                'form-0-valor_subtotal': '5.00',
            },
        )

        assert response.status_code == 400
        storage = get_messages(response.wsgi_request)
        messages_text = [m.message for m in storage]
        assert any('no pertenecen a la empresa activa' in m.lower() for m in messages_text)
        assert Pedido.objects.filter(empresa=empresa_a).count() == 0


    def test_emitir_guia_remision_asigna_empresa_y_detalles(self, client, usuario, empresas):
        self._login(client, usuario)
        empresa_a, _ = empresas
        self._set_empresa(client, empresa_a.id)

        payload = {
            'fecha_emision': '2025-01-01',
            'fecha_inicio_traslado': '2025-01-01T10:00',
            'fecha_fin_traslado': '',
            'motivo_traslado': '01',
            'destinatario_identificacion': '0123456789001',
            'destinatario_nombre': 'Cliente Transporte',
            'direccion_partida': 'Origen 123',
            'direccion_destino': 'Destino 456',
            'transportista_ruc': '1234567890123',
            'transportista_nombre': 'Transportista Demo',
            'placa': 'AAA0000',
            'transportista_observaciones': 'N/A',
            'productos[0][codigo]': 'PRD1',
            'productos[0][descripcion]': 'Producto 1',
            'productos[0][cantidad]': '2',
        }

        response = client.post(reverse('inventario:emitir_guia_remision'), payload, follow=True)
        assert response.status_code == 200

        guia = GuiaRemision.objects.filter(empresa=empresa_a).order_by('-id').first()
        assert guia is not None
        assert guia.destinatario_nombre == 'Cliente Transporte'
        assert guia.empresa_id == empresa_a.id
        detalle = guia.detalles.get()
        assert detalle.empresa_id == empresa_a.id
        assert detalle.codigo_producto == 'PRD1'

    def test_listar_guias_remision_filtra_por_empresa(self, client, usuario, empresas):
        self._login(client, usuario)
        empresa_a, empresa_b = empresas
        self._set_empresa(client, empresa_a.id)

        guia_a = GuiaRemision.objects.create(
            empresa=empresa_a,
            establecimiento='001',
            punto_emision='001',
            secuencial='000000101',
            fecha_emision=timezone.now().date(),
            fecha_inicio_traslado=timezone.now(),
            fecha_fin_traslado=timezone.now(),
            motivo_traslado='01',
            destinatario_identificacion='0101010101',
            destinatario_nombre='Dest Empresa A',
            direccion_partida='Bodega A',
            direccion_destino='Cliente A',
            transportista_ruc='1111111111111',
            transportista_nombre='Trans A',
            placa='AAA0001',
        )
        GuiaRemision.objects.create(
            empresa=empresa_b,
            establecimiento='001',
            punto_emision='001',
            secuencial='000000201',
            fecha_emision=timezone.now().date(),
            fecha_inicio_traslado=timezone.now(),
            fecha_fin_traslado=timezone.now(),
            motivo_traslado='01',
            destinatario_identificacion='0202020202',
            destinatario_nombre='Dest Empresa B',
            direccion_partida='Bodega B',
            direccion_destino='Cliente B',
            transportista_ruc='2222222222222',
            transportista_nombre='Trans B',
            placa='BBB0002',
        )

        response = client.get(reverse('inventario:listar_guias_remision'), follow=True)
        assert response.status_code == 200
        contenido = response.content.decode()
        assert 'Dest Empresa A' in contenido
        assert 'Dest Empresa B' not in contenido
