#----------------------------FUNCIONES DE AYUDA Y COMPLEMENTO--------------------------------------------------

from .models import Producto, Opciones
from decimal import Decimal
from .tenant.queryset import get_current_tenant


def obtenerIdProducto(descripcion):
    id_producto = Producto.objects.get(descripcion=descripcion)
    resultado = id_producto.id

    return resultado

def productoTieneIva(idProducto):
    iva = Producto.objects.get(id=idProducto)
    resultado = iva.tiene_iva
    
    return resultado

def sacarIva(elemento, empresa=None):
    empresa = empresa or get_current_tenant()
    iva = Opciones.objects.for_tenant(empresa).first()
    if not iva and empresa:
        iva = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))
    ivaSacado = iva.valor_iva / 100
    resultado = elemento + (elemento * Decimal(ivaSacado))
    return resultado

def ivaActual(modo, empresa=None):
    empresa = empresa or get_current_tenant()
    iva = Opciones.objects.for_tenant(empresa).first()
    if not iva and empresa:
        iva = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))
    if modo == 'valor':
        return iva.valor_iva
    elif modo == 'objeto':
        return iva

def obtenerProducto(idProducto):
    producto = Producto.objects.get(id=idProducto)      
    return producto


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

def manejarArchivo(archivo, ruta):
    with open(ruta, 'wb+') as destino:  # ← aquí debe ser 'destino'
        for chunk in archivo.chunks():
            destino.write(chunk)


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

