#----------------------------FUNCIONES DE AYUDA Y COMPLEMENTO--------------------------------------------------

from pathlib import Path

from django.core.files.temp import NamedTemporaryFile
from django.shortcuts import get_object_or_404

from .models import Producto
from .tenant.services import tenant_unsafe_service


def obtenerIdProducto(descripcion, empresa):
    """Devuelve el ID del producto filtrando por empresa."""

    empresa_id = getattr(empresa, 'id', empresa)
    producto = tenant_unsafe_service(Producto).get(
        empresa_id=empresa_id,
        descripcion=descripcion,
    )
    return producto.id

def obtenerProducto(idProducto, empresa):
    """Obtiene el producto filtrando por la empresa proporcionada."""

    empresa_id = getattr(empresa, 'id', empresa)
    qs = tenant_unsafe_service(Producto).filter(empresa_id=empresa_id)
    return get_object_or_404(qs, id=idProducto)


def complementarContexto(contexto,datos):
    contexto['usuario'] = datos.username
    contexto['id_usuario'] = datos.id
    contexto['nombre'] = datos.first_name
    contexto['apellido'] = datos.last_name
    contexto['correo'] = datos.email

    return contexto

def usuarioExiste(Usuario,buscar,valor):
    if buscar == 'username':
        try:
            Usuario.objects.get(username=valor)
            return True
        except Usuario.DoesNotExist:
            return False

    elif buscar == 'email':
        try:
            Usuario.objects.get(email=valor)
            return True
        except Usuario.DoesNotExist:
            return False

def manejarArchivo(archivo):
    """Guarda ``archivo`` de manera temporal en ``/tmp`` y devuelve la ruta."""

    suffix = Path(getattr(archivo, 'name', '')).suffix
    with NamedTemporaryFile(delete=False, dir='/tmp', suffix=suffix or '', mode='wb') as destino:
        for chunk in archivo.chunks():
            destino.write(chunk)
        destino.flush()
        temp_path = destino.name

    return temp_path


def generar_codigo_servicio():
    from .models import Servicio
    ultimo = Servicio.objects.order_by('-id').first()
    if ultimo and ultimo.codigo and ultimo.codigo.startswith('S'):
        try:
            numero = int(ultimo.codigo[1:])
        except ValueError:
            numero = ultimo.id
    else:
        numero = 0
    siguiente = numero + 1
    return f"S{siguiente:09d}"

def generar_codigo_producto():
    """
    Genera el próximo código de producto en formato P00000001, P00000002, etc.
    """
    from .models import Producto
    
    # Buscar el último producto por ID para obtener el siguiente número
    ultimo = Producto.objects.order_by('-id').first()
    
    if ultimo and ultimo.codigo and ultimo.codigo.startswith('P'):
        try:
            # Extraer el número del código (después de la P)
            numero = int(ultimo.codigo[1:])
        except (ValueError, IndexError):
            # Si el código no tiene el formato esperado, usar el ID
            numero = ultimo.id
    else:
        # Si no hay productos o el código no sigue el formato, empezar desde 0
        numero = 0
    
    # Generar el siguiente código
    siguiente = numero + 1
    return f"P{siguiente:08d}"  # P00000001, P00000002, etc.

#--------------------------------------------------------------------------------------------------------------                 

