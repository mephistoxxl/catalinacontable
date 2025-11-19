import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario
from django.db.models import ProtectedError

# Buscar usuario con ese username o email
username = "2390054060001"
email = "alpcontadoresyauditores@gmail.com"

usuarios = Usuario.objects.filter(username=username) | Usuario.objects.filter(email=email)

if usuarios.exists():
    for usuario in usuarios:
        print(f"Encontrado usuario: {usuario.username} ({usuario.email})")
        print(f"  - Es superuser: {usuario.is_superuser}")
        print(f"  - Empresas asociadas: {usuario.empresas.count()}")
        
        if not usuario.is_superuser:
            confirmacion = input(f"¿Eliminar usuario {usuario.username} y todos sus datos? (s/n): ")
            if confirmacion.lower() == 's':
                try:
                    # Eliminar datos relacionados del usuario
                    from inventario.models import Caja, Empresa, Opciones
                    
                    # Eliminar cajas creadas por el usuario
                    cajas = Caja.objects.filter(creado_por=usuario)
                    if cajas.exists():
                        print(f"  Eliminando {cajas.count()} cajas...")
                        cajas.delete()
                    
                    # Eliminar empresas asociadas (solo si es el único usuario)
                    for empresa in usuario.empresas.all():
                        if empresa.usuarios.count() == 1:
                            print(f"  Eliminando empresa {empresa.razon_social}...")
                            # Eliminar opciones de la empresa
                            Opciones.objects.filter(empresa=empresa).delete()
                            empresa.delete()
                    
                    # Ahora eliminar el usuario
                    usuario.delete()
                    print(f"✅ Usuario {usuario.username} eliminado exitosamente")
                    
                except ProtectedError as e:
                    print(f"❌ Error: {e}")
                    print(f"   El usuario tiene datos protegidos. Necesitas eliminar manualmente desde Django Admin.")
                except Exception as e:
                    print(f"❌ Error inesperado: {e}")
            else:
                print(f"❌ Usuario {usuario.username} NO eliminado")
        else:
            print(f"⚠️ Usuario {usuario.username} es superusuario - NO se eliminará")
else:
    print(f"❌ No se encontró usuario con username '{username}' o email '{email}'")
