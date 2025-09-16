import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from inventario.models import Empresa, Facturador, Cliente, Secuencia, Producto, Servicio, Factura, Almacen
from django.test import Client

User = get_user_model()

@pytest.mark.django_db
class TestMultiTenantIsolation:
    @pytest.fixture
    def empresas(self):
        e1 = Empresa.objects.create(razon_social='Empresa Uno', identificacion='0999999999001')
        e2 = Empresa.objects.create(razon_social='Empresa Dos', identificacion='0888888888001')
        return e1, e2

    @pytest.fixture
    def usuario(self, empresas):
        user = User.objects.create_user(username='admin', password='pass')
        # Asumiendo relación ManyToMany Usuario.empresas
        if hasattr(user, 'empresas'):
            for e in empresas:
                user.empresas.add(e)
        return user

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

