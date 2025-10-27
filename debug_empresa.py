import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

# Configurar Django sin cargar módulos externos
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(os.path.dirname(__file__), 'db.sqlite3'),
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'inventario',
        ],
        SECRET_KEY='temp-key-for-debug'
    )

django.setup()

from inventario.models import Empresa, Opciones

# Buscar tu empresa
ruc = '1713959011001'
print(f"\n{'='*80}")
print(f"VERIFICANDO EMPRESA: {ruc}")
print(f"{'='*80}\n")

try:
    empresa = Empresa.objects.get(ruc=ruc)
    print(f"✅ Empresa encontrada: {empresa.razon_social}")
    
    opciones = Opciones.objects.filter(empresa=empresa).first()
    
    if not opciones:
        print(f"\n❌ NO TIENE OPCIONES - Por eso redirige a configuración")
        sys.exit(1)
    
    print(f"\n📋 VERIFICANDO CADA CAMPO:\n")
    
    # Verificar cada campo
    campos = {
        '1. RUC (identificacion)': opciones.identificacion,
        '2. Razón Social': opciones.razon_social,
        '3. Nombre Comercial': opciones.nombre_comercial,
        '4. Dirección': opciones.direccion_establecimiento,
        '5. Correo': opciones.correo,
        '6. Teléfono': opciones.telefono,
        '7. Obligado': opciones.obligado,
        '8. Tipo Régimen': opciones.tipo_regimen,
        '9. Mensaje Factura': opciones.mensaje_factura,
        '10. Firma Electrónica': opciones.firma_electronica.name if opciones.firma_electronica else None,
    }
    
    faltantes = []
    
    for nombre, valor in campos.items():
        if valor is None or valor == '' or valor == 'PENDIENTE' or valor == '0000000000000' or valor == 'pendiente@empresa.com' or valor == '0000000000':
            print(f"❌ {nombre}: '{valor}' <- FALTA")
            faltantes.append(nombre)
        else:
            # Mostrar solo primeros 50 caracteres
            valor_str = str(valor)[:50] if len(str(valor)) > 50 else str(valor)
            print(f"✅ {nombre}: '{valor_str}'")
    
    print(f"\n{'='*80}")
    if faltantes:
        print(f"❌ FALTAN {len(faltantes)} CAMPOS:")
        for f in faltantes:
            print(f"   - {f}")
        print(f"\n→ Por eso redirige a CONFIGURACIÓN")
    else:
        print(f"✅ TODOS LOS CAMPOS COMPLETOS")
        print(f"→ Debería ir al PANEL")
    print(f"{'='*80}\n")
    
except Empresa.DoesNotExist:
    print(f"❌ No se encontró empresa con RUC {ruc}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
