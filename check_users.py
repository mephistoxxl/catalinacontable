import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario

print("=== USUARIOS ===")
for u in Usuario.objects.all()[:5]:
    print(f"  username: {u.username}, is_active: {u.is_active}, is_superuser: {u.is_superuser}")
