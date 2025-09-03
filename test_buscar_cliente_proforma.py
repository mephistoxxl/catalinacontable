#!/usr/bin/env python3
"""
Script para probar la funcionalidad de búsqueda de clientes en proforma
"""
import os
import sys
import django
from django.test.client import Client
from django.contrib.auth import get_user_model
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

# Importar modelos después de configurar Django
from inventario.models import Cliente, Empresa

def test_buscar_cliente_api():
    """Prueba el endpoint de búsqueda de cliente"""
    client = Client()
    
    # Crear un usuario de prueba para autenticación
    User = get_user_model()
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Usuario',
            last_name='Prueba'
        )
    
    # Iniciar sesión
    login_success = client.login(username='testuser', password='testpass123')
    print(f"Login successful: {login_success}")
    
    if not login_success:
        print("❌ No se pudo iniciar sesión")
        return
    
    # Configurar empresa en sesión
    try:
        empresa = Empresa.objects.first()
        if empresa:
            session = client.session
            session['empresa_activa'] = empresa.id
            session.save()
            print(f"✅ Empresa configurada: {empresa.razonSocial}")
        else:
            print("⚠️ No se encontraron empresas")
            return
    except Exception as e:
        print(f"❌ Error configurando empresa: {e}")
        return
    
    # Crear un cliente de prueba si no existe
    try:
        cliente_test = Cliente.objects.filter(
            identificacion='1234567890',
            empresa=empresa
        ).first()
        
        if not cliente_test:
            cliente_test = Cliente.objects.create(
                empresa=empresa,
                identificacion='1234567890',
                razon_social='Cliente de Prueba',
                nombre_comercial='Prueba Comercial',
                correo='cliente@prueba.com',
                telefono='0999999999',
                direccion='Dirección de prueba',
                tipoIdentificacion='05',
                tipo_contribuyente='CONTRIBUYENTE ESPECIAL',
                obligado_llevar_contabilidad='NO'
            )
            print(f"✅ Cliente de prueba creado: {cliente_test.razon_social}")
        else:
            print(f"✅ Cliente de prueba encontrado: {cliente_test.razon_social}")
            
    except Exception as e:
        print(f"❌ Error creando cliente de prueba: {e}")
        return
    
    # Probar la búsqueda de cliente
    try:
        response = client.get('/inventario/buscar_cliente/', {'q': '1234567890'})
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Respuesta del API de búsqueda:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if not data.get('error'):
                print("✅ Cliente encontrado exitosamente")
                print(f"   ID: {data.get('id')}")
                print(f"   Identificación: {data.get('identificacion')}")
                print(f"   Razón Social: {data.get('razon_social')}")
                print(f"   Correo: {data.get('correo', 'N/A')}")
            else:
                print(f"❌ Error en búsqueda: {data.get('message')}")
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            print(f"Response content: {response.content.decode()}")
            
    except Exception as e:
        print(f"❌ Error probando búsqueda: {e}")
        import traceback
        traceback.print_exc()

def test_proforma_form_access():
    """Prueba el acceso al formulario de proforma"""
    client = Client()
    
    # Crear usuario y autenticar
    User = get_user_model()
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Usuario',
            last_name='Prueba'
        )
    
    # Iniciar sesión
    login_success = client.login(username='testuser', password='testpass123')
    if not login_success:
        print("❌ No se pudo iniciar sesión para prueba de formulario")
        return
    
    # Configurar empresa en sesión
    try:
        empresa = Empresa.objects.first()
        if empresa:
            session = client.session
            session['empresa_activa'] = empresa.id
            session.save()
    except Exception as e:
        print(f"❌ Error configurando empresa para formulario: {e}")
        return
    
    # Acceder al formulario de proforma
    try:
        response = client.get('/inventario/proformas/emitir/')
        print(f"Acceso a formulario - Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Formulario de proforma accesible")
            # Verificar que contiene los campos necesarios
            content = response.content.decode()
            if 'id_identificacion_cliente' in content:
                print("✅ Campo identificación_cliente presente")
            if 'buscarCliente()' in content:
                print("✅ Función buscarCliente() presente")
            if 'cliente_id' in content:
                print("✅ Campo cliente_id presente")
        else:
            print(f"❌ Error accediendo a formulario: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error accediendo a formulario: {e}")

if __name__ == '__main__':
    print("=== PRUEBA DE FUNCIONALIDAD DE BÚSQUEDA DE CLIENTES EN PROFORMA ===\n")
    
    print("1. Probando API de búsqueda de cliente...")
    test_buscar_cliente_api()
    
    print("\n2. Probando acceso a formulario de proforma...")
    test_proforma_form_access()
    
    print("\n=== PRUEBAS COMPLETADAS ===")
