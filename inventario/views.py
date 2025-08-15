#renderiza las vistas al usuario
from django.contrib.auth.hashers import check_password
from django.shortcuts import render, get_object_or_404, redirect

# para redirigir a otras paginas
from django.http import HttpResponseRedirect, HttpResponse, FileResponse, JsonResponse
from urllib3 import request
#el formulario de login
from .forms import *
# clase para crear vistas basadas en sub-clases
from django.views import View
#autentificacion de usuario e inicio de sesion
from django.contrib.auth import authenticate, login, logout
#verifica si el usuario esta logeado
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import SecuenciaFormulario  # Asumiendo que existe un formulario llamado SecuenciaFormulario
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Secuencia
from .forms import SecuenciaFormulario
#modelos
from .models import *
#formularios dinamicos
from django.forms import formset_factory
#funciones personalizadas
from .funciones import *
#Mensajes de formulario
from django.contrib import messages
#Ejecuta un comando en la terminal externa
from django.core.management import call_command
#procesa archivos en .json
from django.core import serializers
#permite acceder de manera mas facil a los ficheros
from django.core.files.storage import FileSystemStorage
import re
from datetime import date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import logging
from django.contrib import admin
from services import consultar_ruc as servicio_consultar_ruc
from .sri.ride_generator import RIDEGenerator
import os
from pathlib import Path
from django.conf import settings
# ===== AGREGAR ESTOS IMPORTS AL INICIO DE views.py =====

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import random
from .forms import FirmaElectronicaForm  # Asegúrate de tener este formulario
from django.urls import reverse

logger = logging.getLogger(__name__)


#Vistas endogenas.


#Interfaz de inicio de sesion----------------------------------------------------#
#Interfaz de inicio de sesion----------------------------------------------------#
class Login(View):
    #Si el usuario ya envio el formulario por metodo post
    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos:
        form = LoginFormulario(request.POST)
        # Revisa si es valido:
        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            usuario = form.cleaned_data['username']
            clave = form.cleaned_data['password']
            # Se verifica que el usuario y su clave existan
            logeado = authenticate(request, username=usuario, password=clave)
            if logeado is not None:
                login(request, logeado)
                #Si el login es correcto lo redirige al panel del sistema:
                return HttpResponseRedirect('/inventario/panel')
            else:
                #De lo contrario lanzara el mismo formulario
                return render(request, 'inventario/login.html', {'form': form})

    # Si se llega por GET crearemos un formulario en blanco
    def get(self, request):
        if request.user.is_authenticated == True:
            return HttpResponseRedirect('/inventario/panel')

        form = LoginFormulario()
        #Envia al usuario el formulario para que lo llene
        return render(request, 'inventario/login.html', {'form': form})


#Fin de vista---------------------------------------------------------------------#


#Panel de inicio y vista principal------------------------------------------------#
class Panel(LoginRequiredMixin, View):
    #De no estar logeado, el usuario sera redirigido a la pagina de Login
    #Las dos variables son la pagina a redirigir y el campo adicional, respectivamente
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from datetime import date
        #Recupera los datos del usuario despues del login
        contexto = {'usuario': request.user.username,
                    'id_usuario': request.user.id,
                    'nombre': request.user.first_name,
                    'apellido': request.user.last_name,
                    'correo': request.user.email,
                    'fecha': date.today(),
                    'productosRegistrados': Producto.numeroRegistrados(),
                    'productosVendidos': DetalleFactura.productosVendidos(),
                    'clientesRegistrados': Cliente.numeroRegistrados(),
                    'usuariosRegistrados': Usuario.numeroRegistrados(),
                    'facturasEmitidas': Factura.numeroRegistrados(),
                    'ingresoTotal': Factura.ingresoTotal(),
                    'ultimasVentas': DetalleFactura.ultimasVentas(),
                    'administradores': Usuario.numeroUsuarios('administrador'),
                    'usuarios': Usuario.numeroUsuarios('usuario'),
                    # Nuevos datos para el panel de ventas
                    'ventasEsteMes': Factura.ventasEsteMes(),
                    'ventasMesAnterior': Factura.ventasMesAnterior(),
                    'promedioVentasMensuales': Factura.promedioVentasMensuales(),
                    'ventasUltimosMeses': Factura.ventasUltimosMeses(6),
                    # Datos para top productos vendidos
                    'topProductosVendidos': DetalleFactura.topProductosVendidos(5),
                    }

        return render(request, 'inventario/panel.html', contexto)


#Fin de vista----------------------------------------------------------------------#


#Maneja la salida del usuario------------------------------------------------------#
class Salir(LoginRequiredMixin, View):
    #Sale de la sesion actual
    login_url = 'inventario/login'
    redirect_field_name = None

    def get(self, request):
        logout(request)
        return HttpResponseRedirect('/inventario/login')


#Fin de vista----------------------------------------------------------------------#


#Muestra el perfil del usuario logeado actualmente---------------------------------#
class Perfil(LoginRequiredMixin, View):
    login_url = 'inventario/login'
    redirect_field_name = None

    #se accede al modo adecuado y se valida al usuario actual para ver si puede modificar al otro usuario-
    #-el cual es obtenido por la variable 'p'
    def get(self, request, modo, p):
        if modo == 'editar':
            perf = Usuario.objects.get(id=p)
            editandoSuperAdmin = False

            if p == 1:
                if request.user.nivel != 2:
                    messages.error(request,
                                   'No puede editar el perfil del administrador por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)
                editandoSuperAdmin = True
            else:
                if request.user.is_superuser != True:
                    messages.error(request, 'No puede cambiar el perfil por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

                else:
                    if perf.is_superuser == True:
                        if request.user.nivel == 2:
                            pass

                        elif perf.id != request.user.id:
                            messages.error(request, 'No puedes cambiar el perfil de un usuario de tu mismo nivel')

                            return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

            if editandoSuperAdmin:
                form = UsuarioFormulario()
                form.fields['level'].disabled = True
            else:
                form = UsuarioFormulario()

            #Me pregunto si habia una manera mas facil de hacer esto, solo necesitaba hacer que el formulario-
            #-apareciera lleno de una vez, pero arrojaba User already exists y no pasaba de form.is_valid()
            form['username'].field.widget.attrs['value'] = perf.username
            form['first_name'].field.widget.attrs['value'] = perf.first_name
            form['last_name'].field.widget.attrs['value'] = perf.last_name
            form['email'].field.widget.attrs['value'] = perf.email
            form['level'].field.widget.attrs['value'] = perf.nivel

            #Envia al usuario el formulario para que lo llene
            contexto = {'form': form, 'modo': request.session.get('perfilProcesado'), 'editar': 'perfil',
                        'nombreUsuario': perf.username}

            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/perfil/perfil.html', contexto)


        elif modo == 'clave':
            perf = Usuario.objects.get(id=p)
            if p == 1:
                if request.user.nivel != 2:
                    messages.error(request,
                                   'No puede cambiar la clave del administrador por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)
            else:
                if request.user.is_superuser != True:
                    messages.error(request,
                                   'No puede cambiar la clave de este perfil por no tener los permisos suficientes')
                    return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

                else:
                    if perf.is_superuser == True:
                        if request.user.nivel == 2:
                            pass

                        elif perf.id != request.user.id:
                            messages.error(request, 'No puedes cambiar la clave de un usuario de tu mismo nivel')
                            return HttpResponseRedirect('/inventario/perfil/ver/%s' % p)

            form = ClaveFormulario(request.POST)
            contexto = {'form': form, 'modo': request.session.get('perfilProcesado'),
                        'editar': 'clave', 'nombreUsuario': perf.username}

            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/perfil/perfil.html', contexto)

        elif modo == 'ver':
            perf = Usuario.objects.get(id=p)
            contexto = {'perfil': perf}
            contexto = complementarContexto(contexto, request.user)

            return render(request, 'inventario/perfil/verPerfil.html', contexto)

    def post(self, request, modo, p):
        if modo == 'editar':
            # Crea una instancia del formulario y la llena con los datos:
            form = UsuarioFormulario(request.POST)
            # Revisa si es valido:

            if form.is_valid():
                perf = Usuario.objects.get(id=p)
                # Procesa y asigna los datos con form.cleaned_data como se requiere
                if p != 1:
                    level = form.cleaned_data['level']
                    perf.nivel = level
                    perf.is_superuser = level

                username = form.cleaned_data['username']
                first_name = form.cleaned_data['first_name']
                last_name = form.cleaned_data['last_name']
                email = form.cleaned_data['email']

                perf.username = username
                perf.first_name = first_name
                perf.last_name = last_name
                perf.email = email

                perf.save()

                form = UsuarioFormulario()
                messages.success(request, 'Actualizado exitosamente el perfil de ID %s.' % p)
                request.session['perfilProcesado'] = True
                return HttpResponseRedirect("/inventario/perfil/ver/%s" % perf.id)
            else:
                #De lo contrario lanzara el mismo formulario
                return render(request, 'inventario/perfil/perfil.html', {'form': form})

        elif modo == 'clave':
            form = ClaveFormulario(request.POST)

            if form.is_valid():
                error = 0
                clave_nueva = form.cleaned_data['clave_nueva']
                repetir_clave = form.cleaned_data['repetir_clave']
                #clave = form.cleaned_data['clave']

                #Comentare estas lineas de abajo para deshacerme de la necesidad
                #   de obligar a que el usuario coloque la clave nuevamente
                #correcto = authenticate(username=request.user.username , password=clave)

                #if correcto is not None:
                #if clave_nueva != clave:
                #pass
                #else:
                #error = 1
                #messages.error(request,"La clave nueva no puede ser identica a la actual")

                usuario = Usuario.objects.get(id=p)

                if clave_nueva == repetir_clave:
                    pass
                else:
                    error = 1
                    messages.error(request, "La clave nueva y su repeticion tienen que coincidir")

                #else:
                #error = 1
                #messages.error(request,"La clave de acceso actual que ha insertado es incorrecta")

                if (error == 0):
                    messages.success(request, 'La clave se ha cambiado correctamente!')
                    usuario.set_password(clave_nueva)
                    usuario.save()
                    return HttpResponseRedirect("/inventario/login")

                else:
                    return HttpResponseRedirect("/inventario/perfil/clave/%s" % p)


#----------------------------------------------------------------------------------#   


#Elimina usuarios, productos, clientes o proveedores----------------------------
class Eliminar(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, modo, p):

        if modo == 'producto':
            prod = Producto.objects.get(id=p)
            prod.delete()
            messages.success(request, 'Producto de ID %s borrado exitosamente.' % p)
            return HttpResponseRedirect("/inventario/listarProductos")

        elif modo == 'cliente':
            cliente = Cliente.objects.get(id=p)
            cliente.delete()
            messages.success(request, 'Cliente de ID %s borrado exitosamente.' % p)
            return HttpResponseRedirect("/inventario/listarClientes")


        elif modo == 'proveedor':
            proveedor = Proveedor.objects.get(id=p)
            proveedor.delete()
            messages.success(request, 'Proveedor de ID %s borrado exitosamente.' % p)
            return HttpResponseRedirect("/inventario/listarProveedores")

        elif modo == 'usuario':
            if request.user.is_superuser == False:
                messages.error(request, 'No tienes permisos suficientes para borrar usuarios')
                return HttpResponseRedirect('/inventario/listarUsuarios')

            elif p == 1:
                messages.error(request, 'No puedes eliminar al super-administrador.')
                return HttpResponseRedirect('/inventario/listarUsuarios')

            elif request.user.id == p:
                messages.error(request, 'No puedes eliminar tu propio usuario.')
                return HttpResponseRedirect('/inventario/listarUsuarios')

            else:
                usuario = Usuario.objects.get(id=p)
                usuario.delete()
                messages.success(request, 'Usuario de ID %s borrado exitosamente.' % p)
                return HttpResponseRedirect("/inventario/listarUsuarios")

            #Fin de vista-------------------------------------------------------------------


#Muestra una lista de 10 productos por pagina----------------------------------------#
class ListarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models

        #Lista de productos de la BDD
        productos = Producto.objects.all()

        contexto = {'tabla': productos}

        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/producto/listarProductos.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Maneja y visualiza un formulario--------------------------------------------------#
class AgregarProducto(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ProductoFormulario(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data['codigo']
            codigo_barras = form.cleaned_data['codigo_barras']
            descripcion = form.cleaned_data['descripcion']
            precio = form.cleaned_data['precio']
            precio2 = form.cleaned_data.get('precio2', None)
            categoria = form.cleaned_data['categoria']
            disponible = form.cleaned_data['disponible']
            iva = form.cleaned_data['iva']
            costo_actual = form.cleaned_data['costo_actual']

            iva_percent = Decimal(dict(Producto.tiposIVA).get(iva).replace('%', '')) / 100

            precio_iva1 = precio * (Decimal('1.00') + iva_percent)
            precio_iva2 = precio2 * (Decimal('1.00') + iva_percent) if precio2 else None

            prod = Producto(
                codigo=codigo,
                codigo_barras=codigo_barras,
                descripcion=descripcion,
                precio=precio,
                precio2=precio2,
                categoria=categoria,
                disponible=disponible,
                iva=iva,
                costo_actual=costo_actual,
                precio_iva1=precio_iva1,
                precio_iva2=precio_iva2
            )
            prod.save()

            form = ProductoFormulario()
            messages.success(request, 'Ingresado exitosamente bajo la ID %s.' % prod.id)
            request.session['productoProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarProducto")
        else:
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})

    def get(self, request):
        from .funciones import generar_codigo_producto
        
        # ✅ GENERAR CÓDIGO AUTOMÁTICO DE PRODUCTO
        nuevo_codigo = generar_codigo_producto()
        
        form = ProductoFormulario(initial={'codigo': nuevo_codigo})
        
        # Obtener mensajes de sesión
        mensaje = None
        if 'productoProcesado' in request.session:
            if request.session['productoProcesado'] == 'agregado':
                mensaje = "Producto agregado exitosamente"
            del request.session['productoProcesado']
        
        contexto = {
            'form': form,
            'mensaje': mensaje,
            'nuevo_codigo': nuevo_codigo
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/agregarProducto.html', contexto)

        #FIN DEL CONTEXTO-----------------------------#


#Formulario simple que procesa un script para importar los productos-----------------#
class ImportarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarProductosFormulario(request.POST)
        if form.is_valid():
            request.session['productosImportados'] = True
            return HttpResponseRedirect("/inventario/importarProductos")

    def get(self, request):
        form = ImportarProductosFormulario()

        if request.session.get('productosImportados') == True:
            importado = request.session.get('productoImportados')
            contexto = {'form': form, 'productosImportados': importado}
            request.session['productosImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/importarProductos.html', contexto)

    #Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los productos-----------------------#
class ExportarProductos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ExportarProductosFormulario(request.POST)
        if form.is_valid():
            request.session['productosExportados'] = True

            #Se obtienen las entradas de producto en formato JSON
            data = serializers.serialize("json", Producto.objects.all())
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("productos.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("productos.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="productos.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarProductosFormulario()

        if request.session.get('productosExportados') == True:
            exportado = request.session.get('productoExportados')
            contexto = {'form': form, 'productosExportados': exportado}
            request.session['productosExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/exportarProductos.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Muestra el formulario de un producto especifico para editarlo----------------------------------#
class EditarProducto(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        # Crea una instancia del formulario y la llena con los datos:
        form = ProductoFormulario(request.POST)
        # Revisa si es valido:
        if form.is_valid():
            # ✅ CORREGIDO: Procesar TODOS los campos del formulario
            codigo = form.cleaned_data['codigo']
            codigo_barras = form.cleaned_data['codigo_barras']
            descripcion = form.cleaned_data['descripcion']
            precio = form.cleaned_data['precio']
            precio2 = form.cleaned_data.get('precio2', None)
            categoria = form.cleaned_data['categoria']
            disponible = form.cleaned_data['disponible']
            iva = form.cleaned_data['iva']  # ✅ ESTO FALTABA!
            costo_actual = form.cleaned_data['costo_actual']

            # Obtener el producto a editar
            prod = Producto.objects.get(id=p)
            
            # ✅ ACTUALIZAR TODOS LOS CAMPOS
            prod.codigo = codigo
            prod.codigo_barras = codigo_barras
            prod.descripcion = descripcion
            prod.precio = precio
            prod.precio2 = precio2
            prod.categoria = categoria
            prod.disponible = disponible
            prod.iva = iva  # ✅ ESTO ES LO QUE FALTABA!
            prod.costo_actual = costo_actual
            
            # ✅ RECALCULAR PRECIOS CON IVA USANDO EL MÉTODO save() DEL MODELO
            # El modelo ya tiene la lógica para calcular precio_iva1 y precio_iva2
            prod.save()  # Esto ejecutará automáticamente el cálculo de IVA

            form = ProductoFormulario(instance=prod)
            messages.success(request, 'Actualizado exitosamente el producto de ID %s.' % p)
            request.session['productoProcesado'] = 'editado'
            return HttpResponseRedirect("/inventario/editarProducto/%s" % prod.id)
        else:
            # De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/producto/agregarProducto.html', {'form': form})

    def get(self, request, p):
        prod = Producto.objects.get(id=p)
        form = ProductoFormulario(instance=prod)
        # Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('productoProcesado'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/producto/agregarProducto.html', contexto)


#Fin de vista------------------------------------------------------------------------------------#

# Búsqueda de Clientes
def buscar_cliente(request):
    query = request.GET.get('q', '')
    clientes = Cliente.objects.filter(identificacion__icontains=query)[:5] # Usar 'identificacion'
    resultados = [{'id': cliente.id, 'nombre': f"{cliente.identificacion} - {cliente.razon_social} {cliente.nombre_comercial if cliente.nombre_comercial else ''}"} for cliente in clientes] # Usar 'identificacion', 'razon_social', 'nombre_comercial'
    return JsonResponse(resultados, safe=False)

# Búsqueda de Productos
from .models import Producto, Servicio

from django.http import JsonResponse
from .models import Producto, Servicio


#Crea una lista de los clientes, 10 por pagina----------------------------------------#
class ListarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        #Saca una lista de todos los clientes de la BDD
        clientes = Cliente.objects.all()
        contexto = {'tabla': clientes}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/cliente/listarClientes.html', contexto)
    #Fin de vista--------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar a un cliente---------------------------------#
class AgregarCliente(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos:
        form = ClienteFormulario(request.POST)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            identificacion = form.cleaned_data['identificacion'] # Renombrado
            razon_social = form.cleaned_data['razon_social'] # Renombrado
            nombre_comercial = form.cleaned_data['nombre_comercial'] # Renombrado
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            observaciones = form.cleaned_data['observaciones']
            convencional = form.cleaned_data['convencional']
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoCliente = form.cleaned_data['tipoCliente']
            # CORRECCIÓN: cambiar tipoCedula por tipoIdentificacion
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']

            cliente = Cliente(identificacion=identificacion, razon_social=razon_social, nombre_comercial=nombre_comercial,
                              direccion=direccion, telefono=telefono,
                              correo=correo, observaciones=observaciones, convencional=convencional,
                              tipoVenta=tipoVenta,
                              tipoRegimen=tipoRegimen, tipoCliente=tipoCliente, 
                              # CORRECCIÓN: usar tipoIdentificacion
                              tipoIdentificacion=tipoIdentificacion)

            cliente.save()
            form = ClienteFormulario()
            messages.success(request, 'Ingresado exitosamente bajo la ID %s.' % cliente.id)
            request.session['clienteProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarCliente")
        else:
            #De lo contrario lanzara el mismo formulario
            messages.error(request, 'Error al agregar el cliente, ya existe o se encuentra en la base de datos')
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})

    def get(self, request):
        form = ClienteFormulario()
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('clienteProcesado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/agregarCliente.html', contexto)


# NUEVA VISTA: Consulta RUC mediante API
@csrf_exempt
@require_http_methods(["GET"])
def consultar_ruc(request):
    """Vista para consultar información de RUC."""
    logger = logging.getLogger(__name__)
    
    try:
        # Obtener el RUC del request
        ruc = request.GET.get('ruc', '')
        logger.info(f"Recibida solicitud de consulta para RUC: {ruc}")
        
        if not ruc:
            return JsonResponse({
                'error': True,
                'message': 'El RUC es requerido',
                'status_code': 400
            }, status=400)
        
        # Importar el servicio
        from services import consultar_ruc as servicio_consultar_ruc
        
        # Llamar al servicio
        resultado = servicio_consultar_ruc(ruc)
        logger.info(f"Resultado del servicio: {resultado}")
        
        # Obtener el status code del resultado o usar 200 por defecto
        status_code = resultado.get('status_code', 200)
        
        # Devolver la respuesta
        return JsonResponse(resultado, status=status_code)
        
    except Exception as e:
        logger.error(f"Error en la vista consultar_ruc: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'error': True,
            'message': f'Error interno del servidor: {str(e)}',
            'status_code': 500
        }, status=500)


def validar_ruc_ecuatoriano(ruc):
    """
    Validar que el RUC tenga formato ecuatoriano válido
    """
    if len(ruc) != 13:
        return False
    
    try:
        # Los primeros 2 dígitos deben ser provincia válida (01-24)
        provincia = int(ruc[:2])
        if provincia < 1 or provincia > 24:
            return False
        
        # El tercer dígito determina el tipo de RUC
        tercer_digito = int(ruc[2])
        
        # Para RUC de empresas, el tercer dígito debe ser 9
        # Para personas naturales con actividad económica, puede ser 0-5
        # Para entidades públicas, debe ser 6
        if tercer_digito not in [0, 1, 2, 3, 4, 5, 6, 9]:
            return False
        
        return True
        
    except ValueError:
        return False


def determinar_tipo_cliente(data_api):
    """
    Función auxiliar para determinar el tipo de cliente basado en los datos del API
    """
    # Ajustar la lógica según los datos que devuelva tu API
    tipo_contribuyente = data_api.get('tipoContribuyente', '').lower()
    
    if 'natural' in tipo_contribuyente or 'persona natural' in tipo_contribuyente:
        return 'Persona Natural'
    elif 'sociedad' in tipo_contribuyente or 'juridica' in tipo_contribuyente:
        return 'Sociedad'
    else:
        # Valor por defecto
        return 'Persona Natural'




#Fin de vista-----------------------------------------------------------------------------#


#Formulario simple que procesa un script para importar los clientes-----------------#
class ImportarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesImportados'] = True
            return HttpResponseRedirect("/inventario/importarClientes")

    def get(self, request):
        form = ImportarClientesFormulario()

        if request.session.get('clientesImportados') == True:
            importado = request.session.get('clientesImportados')
            contexto = {'form': form, 'clientesImportados': importado}
            request.session['clientesImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/importarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los clientes-----------------------#
class ExportarClientes(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ExportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesExportados'] = True

            #Se obtienen las entradas de producto en formato JSON
            data = serializers.serialize("json", Cliente.objects.all())
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("clientes.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("clientes.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="clientes.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarClientesFormulario()

        if request.session.get('clientesExportados') == True:
            exportado = request.session.get('clientesExportados')
            contexto = {'form': form, 'clientesExportados': exportado}
            request.session['clientesExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/exportarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Muestra el mismo formulario del cliente pero con los datos a editar----------------------#
class EditarCliente(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        # Crea una instancia del formulario y la llena con los datos:
        cliente = Cliente.objects.get(id=p)
        form = ClienteFormulario(request.POST, instance=cliente)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            identificacion = form.cleaned_data['identificacion']
            razon_social = form.cleaned_data['razon_social']
            nombre_comercial = form.cleaned_data['nombre_comercial']
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            observaciones = form.cleaned_data['observaciones']
            convencional = form.cleaned_data['convencional']
            tipoVenta = form.cleaned_data['tipoVenta']
            tipoRegimen = form.cleaned_data['tipoRegimen']
            tipoCliente = form.cleaned_data['tipoCliente']
            tipoIdentificacion = form.cleaned_data['tipoIdentificacion']

            cliente.identificacion = identificacion
            cliente.razon_social = razon_social
            cliente.nombre_comercial = nombre_comercial
            cliente.direccion = direccion
            cliente.telefono = telefono
            cliente.correo = correo
            cliente.observaciones = observaciones
            cliente.convencional = convencional
            cliente.tipoVenta = tipoVenta
            cliente.tipoRegimen = tipoRegimen
            cliente.tipoCliente = tipoCliente
            cliente.tipoIdentificacion = tipoIdentificacion
            cliente.save()
            form = ClienteFormulario(instance=cliente)

            messages.success(request, 'Actualizado exitosamente el cliente de ID %s.' % p)
            request.session['clienteProcesado'] = 'editado'
            return HttpResponseRedirect("/inventario/editarCliente/%s" % cliente.id)
        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/cliente/agregarCliente.html', {'form': form})

    def get(self, request, p):
        cliente = Cliente.objects.get(id=p)
        form = ClienteFormulario(instance=cliente)
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('clienteProcesado'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/agregarCliente.html', contexto)
    #Fin de vista--------------------------------------------------------------------------------#


#Emite la primera parte de la factura------------------------------#
# ===== VISTA EMITIR FACTURA CORREGIDA =====
# ===== AGREGAR ESTAS FUNCIONES AL FINAL DE views.py =====

def obtener_datos_secuencia(request, secuencia_id):
    """
    Busca la secuencia seleccionada por su ID y devuelve los datos formateados
    """
    try:
        secuencia = Secuencia.objects.get(id=secuencia_id)
        return JsonResponse({
            'success': True,
            'data': {
                'id': secuencia.id,
                'descripcion': secuencia.descripcion,
                'establecimiento': secuencia.get_establecimiento_formatted(),  # Formato: "001"
                'punto_emision': secuencia.get_punto_emision_formatted(),      # Formato: "001"  
                'secuencial': secuencia.get_secuencial_formatted(),             # Formato: "000000001"
                'tipo_documento': secuencia.tipo_documento,
                'activo': secuencia.activo
            }
        })
    except Secuencia.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Secuencia no encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)


# ===== ASEGURAR QUE ESTAS FUNCIONES TAMBIÉN ESTÉN PRESENTES =====




def buscar_cliente(request):
    """
    Función para buscar clientes por identificación
    """
    try:
        query = request.GET.get('q', '')
        clientes = Cliente.objects.filter(identificacion__icontains=query)[:5]
        resultados = []
        
        for cliente in clientes:
            nombre_completo = cliente.razon_social
            if cliente.nombre_comercial:
                nombre_completo += f" {cliente.nombre_comercial}"
            
            resultados.append({
                'id': cliente.id,
                'nombre': f"{cliente.identificacion} - {nombre_completo}"
            })
        
        return JsonResponse(resultados, safe=False)
        
    except Exception as e:
        print(f"❌ Error en buscar_cliente: {e}")
        return JsonResponse([], safe=False)
# ===== VISTA EMITIR FACTURA CORREGIDA =====
class EmitirFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        """Muestra el formulario para emitir factura"""
        try:
            # ✅ VERIFICAR QUE HAY UN FACTURADOR EN SESIÓN
            facturador_id = request.session.get('facturador_id')
            if not facturador_id:
                messages.warning(request, 'Debe iniciar sesión como facturador antes de emitir facturas.')
                return redirect('inventario:login_facturador')
            
            # Verificar que el facturador existe y está activo
            try:
                facturador = Facturador.objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                # Limpiar sesión de facturador inválido
                if 'facturador_id' in request.session:
                    del request.session['facturador_id']
                if 'facturador_nombre' in request.session:
                    del request.session['facturador_nombre']
                return redirect('inventario:login_facturador')

            # Obtener las opciones de clientes y secuencias
            cedulas = Cliente.cedulasRegistradas()
            secuencias = Secuencia.objects.filter(tipo_documento='01', activo=True)  # Solo facturas activas
            almacenes = Almacen.objects.filter(activo=True)  # Solo almacenes activos

            # Preparar opciones para el formulario
            form = EmitirFacturaFormulario(cedulas=cedulas, secuencias=secuencias)
            
            # Actualizar el campo de almacenes dinámicamente
            form.fields['almacen'].choices = [(a.id, a.descripcion) for a in almacenes]

            # Preparar el contexto
            contexto = {
                'form': form,
                'cedulas': cedulas,
                'secuencias': secuencias,
                'almacenes': almacenes,
                'facturador': facturador  # ✅ AGREGAR INFO DEL FACTURADOR
            }
            contexto = complementarContexto(contexto, request.user)

            return render(request, 'inventario/factura/emitirFactura.html', contexto)

        except Exception as e:
            print(f"Error al cargar la página de emitir factura: {e}")
            messages.error(request, f"Error al cargar la página: {e}")
            return redirect('inventario:panel')

    def post(self, request):
        """Procesa el formulario para crear la factura"""
        try:
            # Imprimir datos recibidos para depuración
            print("Datos recibidos del formulario (request.POST):", request.POST)

            # ✅ RECUPERAR Y VALIDAR FACTURADOR DESDE SESIÓN
            facturador_id = request.session.get('facturador_id')
            if not facturador_id:
                messages.error(request, 'Debe iniciar sesión como facturador antes de emitir facturas.')
                return redirect('inventario:login_facturador')
            
            try:
                facturador = Facturador.objects.get(id=facturador_id, activo=True)
            except Facturador.DoesNotExist:
                messages.error(request, 'El facturador no existe o no está activo.')
                # Limpiar sesión de facturador inválido
                if 'facturador_id' in request.session:
                    del request.session['facturador_id']
                if 'facturador_nombre' in request.session:
                    del request.session['facturador_nombre']
                return redirect('inventario:login_facturador')

            # Recuperar datos del cliente
            cliente_id = request.POST.get('cliente_id')
            if not cliente_id:
                raise ValueError("No se seleccionó un cliente válido.")
                
            cliente = get_object_or_404(Cliente, pk=cliente_id)

            # Recuperar datos del almacén
            almacen_id = request.POST.get('almacen')
            if almacen_id:
                almacen = get_object_or_404(Almacen, pk=almacen_id)
            else:
                almacen = None

            # Convertir fechas de cadena a objetos datetime.date
            from datetime import datetime
            fecha_emision_str = request.POST.get('fecha_emision')
            if not fecha_emision_str:
                raise ValueError("La fecha de emisión es obligatoria.")
            fecha_emision = datetime.strptime(fecha_emision_str, '%Y-%m-%d').date()

            fecha_vencimiento_str = request.POST.get('fecha_vencimiento')
            if not fecha_vencimiento_str:
                raise ValueError("La fecha de vencimiento es obligatoria.")
            fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()

            # Recuperar datos de secuencia
            establecimiento = request.POST.get('establecimiento')
            punto_emision = request.POST.get('punto_emision')
            secuencia = request.POST.get('secuencia_valor')
            concepto = request.POST.get('concepto', 'Sin concepto')

            if not establecimiento or not punto_emision or not secuencia:
                raise ValueError("Establecimiento, Punto de Emisión y Secuencia son obligatorios.")

            # Validar que la secuencia sea numérica
            try:
                secuencia_num = int(secuencia)
            except ValueError:
                raise ValueError("La secuencia debe ser un número válido.")

            # ✅ CREAR FACTURA CON FACTURADOR ASIGNADO
            factura = Factura(
                cliente=cliente,
                almacen=almacen,
                facturador=facturador,  # ✅ AGREGAR EL FACTURADOR
                fecha_emision=fecha_emision,
                fecha_vencimiento=fecha_vencimiento,
                establecimiento=establecimiento,
                punto_emision=punto_emision,
                secuencia=secuencia,
                concepto=concepto,
                identificacion_cliente=cliente.identificacion,
                nombre_cliente=f"{cliente.razon_social} {cliente.nombre_comercial if cliente.nombre_comercial else ''}".strip(),
            )
            factura.save()

            # Guardar el ID de la factura en la sesión
            request.session['factura_id'] = factura.id

            print(f"✅ Factura creada exitosamente con ID: {factura.id}")
            print(f"   - Facturador: {facturador.nombres}")
            print(f"   - Cliente: {cliente.razon_social}")
            print(f"   - Número: {establecimiento}-{punto_emision}-{secuencia}")

            messages.success(request, f'Factura generada exitosamente por {facturador.nombres}. Agregue los productos en el detalle de factura.')
            return redirect('inventario:detallesDeFactura')

        except ValueError as e:
            print(f"Error de validación: {e}")
            messages.error(request, f"Error: {e}")
            return self.get(request)  # Volver a mostrar el formulario

        except Exception as e:
            print(f"Error inesperado: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            messages.error(request, f"Error inesperado: {e}")
            return self.get(request)  # Volver a mostrar el formulario

# ===== CLASE DETALLES FACTURA CORREGIDA =====
# Importaciones necesarias para facturación electrónica SRI
from decimal import Decimal, ROUND_HALF_UP
import random
import decimal

class DetallesFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        try:
            print("=== INICIO DE PROCESAMIENTO DE DETALLES ===")
            print("POST data received:", dict(request.POST))
            print("POST KEYS:", list(request.POST.keys()))
            # Log de emergencia para depuración de arrays
            print("\n=== DIAGNÓSTICO DE CAMPOS DE PRODUCTOS ===")
            for key in request.POST.keys():
                print(f"Campo recibido: {key} => {request.POST.getlist(key)}")
            print("=== FIN DIAGNÓSTICO ===\n")

            # Verificar que existe una factura en sesión
            factura_id = request.session.get('factura_id')
            if not factura_id:
                messages.error(request, 'No se encontró la factura a la cual agregar productos.')
                return redirect('inventario:emitirFactura')

            # Obtener la factura
            factura = Factura.objects.filter(pk=factura_id).first()
            if not factura:
                messages.error(request, 'No se pudo encontrar la factura.')
                return redirect('inventario:emitirFactura')

            print(f"Procesando factura ID: {factura_id}")

            # Obtener listas de códigos y cantidades
            codigos = request.POST.getlist('productos_codigos[]')
            cantidades = request.POST.getlist('productos_cantidades[]')
            # Si no llegan, intentar variantes comunes de nombre
            if not codigos:
                codigos = request.POST.getlist('productos_codigos')
            if not cantidades:
                cantidades = request.POST.getlist('productos_cantidades')

            print(f"Códigos recibidos: {codigos}")
            print(f"Cantidades recibidas: {cantidades}")

            # Validaciones iniciales
            if not codigos or not cantidades:
                # Mensaje de ayuda para el frontend
                msg = (
                    "No se enviaron productos para la factura.\n"
                    "\nDiagnóstico:\n"
                    f"Campos recibidos: {list(request.POST.keys())}\n"
                    "El backend espera los campos 'productos_codigos[]' y 'productos_cantidades[]' como arrays.\n"
                    "Asegúrate de que el formulario los envía exactamente con esos nombres y como múltiples campos (input hidden con name='productos_codigos[]').\n"
                    "Ejemplo correcto en HTML:\n"
                    "<input type='hidden' name='productos_codigos[]' value='COD1'>\n"
                    "<input type='hidden' name='productos_codigos[]' value='COD2'>\n"
                    "<input type='hidden' name='productos_cantidades[]' value='1'>\n"
                    "<input type='hidden' name='productos_cantidades[]' value='2'>\n"
                    "\nRevisa el JavaScript que genera estos campos antes de enviar el formulario.\n"
                )
                print(msg)
                messages.error(request, msg)
                return self.get(request)

            if len(codigos) != len(cantidades):
                messages.error(request, "Error en los datos de productos enviados.")
                return self.get(request)

            # Asegurar que la factura tenga un ID antes de acceder a relaciones
            if not factura.pk:
                factura.save()
                print(f"Factura guardada con ID: {factura.id}")
            
            # Limpiar detalles anteriores de esta factura
            DetalleFactura.objects.filter(factura=factura).delete()
            print("Detalles anteriores eliminados")

            # Variables para totales (SRI requiere exactitud en cálculos)
            sub_monto = Decimal('0.00')
            base_imponible = Decimal('0.00')
            monto_general = Decimal('0.00')
            total_iva = Decimal('0.00')
            productos_procesados = 0

            # Procesar cada producto
            errores = []  # Inicializar la lista de errores
            for codigo, cantidad_str in zip(codigos, cantidades):
                producto = Producto.objects.filter(codigo=codigo).first()
                servicio = Servicio.objects.filter(codigo=codigo).first()
                if not producto and not servicio:
                    errores.append(f"Producto o servicio con código '{codigo}' no encontrado.")
                    continue

                cantidad = int(cantidad_str)
                descuento = Decimal('0.00')
                porcentaje_descuento = Decimal('0.00')
                precio_sin_subsidio = None

                if producto:
                    precio_unitario = producto.precio
                    # Si producto.iva es un ForeignKey a un modelo IVA:
                    iva_percent = Decimal(str(producto.iva.valor_iva)) / 100 if hasattr(producto.iva, 'valor_iva') else Decimal(str(producto.iva)) / 100
                elif servicio:
                    precio_unitario = servicio.precio1
                    iva_percent = Decimal(str(servicio.iva.valor_iva)) / 100 if hasattr(servicio.iva, 'valor_iva') else Decimal(str(servicio.iva)) / 100
                else:
                    continue

                subtotal = precio_unitario * cantidad
                valor_iva = subtotal * iva_percent
                total = subtotal + valor_iva

                # Redondear a 2 decimales
                subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                valor_iva = valor_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                detalle = DetalleFactura.objects.create(
                    factura=factura,
                    producto=producto if producto else None,
                    servicio=servicio if servicio else None,
                    cantidad=cantidad,
                    sub_total=subtotal,
                    total=total,
                    descuento=descuento,
                    porcentaje_descuento=porcentaje_descuento,
                    precio_sin_subsidio=precio_sin_subsidio
                )

                # Acumular totales
                sub_monto += subtotal
                if iva_percent > 0:
                    base_imponible += subtotal
                    total_iva += valor_iva
                    monto_general += total

                print(f"✅ Producto procesado: {codigo} - Cantidad: {cantidad} - Precio unitario: {precio_unitario} - Subtotal: {subtotal} - IVA: {valor_iva} - Total: {total}")
                productos_procesados += 1
            if hasattr(factura, 'crear_totales_impuestos_automatico'):
                factura.crear_totales_impuestos_automatico()
            factura.save()

        except Exception as e:
            print(f"❌ Error general en procesamiento: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            # ✅ AGREGAR: En caso de error, también enviar cajas
            try:
                cajas_activas = Caja.objects.filter(activo=True).order_by('descripcion')
                contexto = {
                    'cajas': cajas_activas,
                }
                contexto = complementarContexto(contexto, request.user)
                messages.error(request, f"Error en procesamiento de factura: {str(e)}")
                return render(request, 'inventario/factura/detallesFactura.html', contexto)
            except:
                # Si falla cargar cajas, usar el método get normal
                messages.error(request, f"Error en procesamiento de factura: {str(e)}")
                return self.get(request)

        # Verificar que se procesó al menos un producto
        if productos_procesados == 0:
            # ✅ AGREGAR: En caso de error, también enviar cajas
            try:
                cajas_activas = Caja.objects.filter(activo=True).order_by('descripcion')
                contexto = {
                    'cajas': cajas_activas,
                }
                contexto = complementarContexto(contexto, request.user)
                messages.error(request, "No se pudo procesar ningún producto. Verifique los datos.")
                return render(request, 'inventario/factura/detallesFactura.html', contexto)
            except:
                # Si falla cargar cajas, usar el método get normal
                messages.error(request, "No se pudo procesar ningún producto. Verifique los datos.")
                return self.get(request)

        # Redondear totales finales para cumplir SRI
        sub_monto = sub_monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        base_imponible = base_imponible.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        monto_general = monto_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_iva = total_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Actualizar totales de la factura según estructura SRI
        factura.sub_monto = sub_monto  # totalSinImpuestos en XML SRI
        factura.base_imponible = base_imponible  # baseImponible en XML SRI
        factura.monto_general = monto_general  # importeTotal en XML SRI
        factura.total_descuento = Decimal('0.00')  # Sin descuentos por ahora
        
        # Asegurar que la factura tenga un ID antes de procesar formas de pago
        if not factura.pk:
            factura.save()
            print(f"Factura guardada con ID: {factura.id}")
        
        # 🔧 FIX CRÍTICO: Asegurar que la clave de acceso se genere INMEDIATAMENTE
        # Esto garantiza que la misma clave se use para PDF y autorización SRI
        if not hasattr(factura, 'clave_acceso') or not factura.clave_acceso:
            print("⚠️  Factura sin clave de acceso, forzando generación...")
            factura.save()  # Esto disparará la generación automática en el modelo
            factura.refresh_from_db()  # Recargar para obtener la clave generada
            
            if factura.clave_acceso:
                print(f"✅ Clave de acceso generada: {factura.clave_acceso}")
            else:
                raise ValueError(f"ERROR CRÍTICO: No se pudo generar clave de acceso para factura {factura.id}")
        else:
            print(f"✅ Clave de acceso ya existe: {factura.clave_acceso}")

        # ✅ CORREGIDO: PROCESAR FORMAS DE PAGO DESPUÉS DE ASEGURAR ID
        try:
            print("=== PROCESANDO FORMAS DE PAGO ===")
            print(f"📋 POST data keys: {list(request.POST.keys())}")
            print(f"📋 POST data completo: {dict(request.POST)}")
            
            # Obtener datos de pagos del JavaScript (enviados como JSON string)
            pagos_data = request.POST.get('pagos_efectivo', '[]')
            print(f"📦 Datos de pagos recibidos (raw): '{pagos_data}'")
            print(f"📦 Tipo: {type(pagos_data)}, Longitud: {len(pagos_data)}")
            
            if pagos_data and pagos_data != '[]' and pagos_data.strip():
                import json
                try:
                    pagos_list = json.loads(pagos_data)
                    print(f"✅ Pagos parseados exitosamente: {len(pagos_list)} pagos")
                    for i, pago in enumerate(pagos_list):
                        print(f"  Pago {i+1}: {pago}")
                    
                    # ✅ LIMPIAR FORMAS DE PAGO ANTERIORES - Verificar el nombre correcto del related_name
                    # Asegurar que la factura tenga un ID antes de acceder a relaciones
                    if not factura.pk:
                        factura.save()
                        print(f"Factura guardada con ID: {factura.id}")
            
                    try:
                        # Intentar diferentes formas de acceso al related manager
                        if hasattr(factura, 'formapago_set'):
                            factura.formapago_set.all().delete()
                            print("✅ Formas de pago anteriores eliminadas usando formapago_set")
                        elif hasattr(factura, 'formas_pago'):
                            factura.formas_pago.all().delete()
                            print("✅ Formas de pago anteriores eliminadas usando formas_pago")
                        else:
                            # Buscar directamente por factura
                            from django.apps import apps
                            FormaPago = apps.get_model('inventario', 'FormaPago')
                            FormaPago.objects.filter(factura=factura).delete()
                            print("✅ Formas de pago anteriores eliminadas usando filter directo")
                    except Exception as delete_error:
                        print(f"⚠️ Error eliminando formas de pago anteriores: {delete_error}")
                    
                    # Procesar cada pago
                    for i, pago in enumerate(pagos_list):
                        try:
                            # Extraer datos del pago con valores por defecto seguros
                            sri_pago = pago.get('sri_pago', '01')  # Default: Sin utilización sistema financiero
                            caja_valor = pago.get('caja', 'CAJA VENTAS')  # Default string seguro
                            monto = Decimal(str(pago.get('monto', 0)))
                            
                            print(f"Procesando pago {i+1}: SRI={sri_pago}, Caja={caja_valor}, Monto={monto}")
                            
                            if monto > 0:
                                # ✅ BUSCAR O CREAR LA CAJA CORRECTAMENTE
                                caja_obj = None
                                if caja_valor and caja_valor != 'CAJA VENTAS':
                                    try:
                                        # Intentar buscar por ID primero
                                        if caja_valor.isdigit():
                                            caja_obj = Caja.objects.filter(id=int(caja_valor), activo=True).first()
                                        else:
                                            # Buscar por descripción
                                            caja_obj = Caja.objects.filter(descripcion=caja_valor, activo=True).first()
                                    except Exception as caja_error:
                                        print(f"⚠️ Error buscando caja '{caja_valor}': {caja_error}")
                                
                                # Si no se encuentra la caja, usar la primera caja activa disponible
                                if not caja_obj:
                                    caja_obj = Caja.objects.filter(activo=True).first()
                                    if caja_obj:
                                        print(f"⚠️ Usando caja por defecto: {caja_obj.descripcion}")
                                    else:
                                        print("❌ No hay cajas activas disponibles")
                                        continue
                                
                                # ✅ CREAR FORMA DE PAGO - Ajustar campos según el modelo real
                                try:
                                    # Intentar diferentes combinaciones de campos
                                    forma_pago_data = {
                                        'factura': factura,
                                        'total': monto
                                    }
                                    
                                    # Agregar campo de forma de pago (probar diferentes nombres)
                                    if hasattr(FormaPago._meta.get_field('forma_pago'), 'choices'):
                                        forma_pago_data['forma_pago'] = sri_pago
                                    elif hasattr(FormaPago._meta, 'get_field') and 'tipo_pago' in [f.name for f in FormaPago._meta.fields]:
                                        forma_pago_data['tipo_pago'] = sri_pago
                                    
                                    # Agregar campo de caja (probar diferentes nombres)
                                    if 'caja' in [f.name for f in FormaPago._meta.fields]:
                                        forma_pago_data['caja'] = caja_obj
                                    elif 'caja_id' in [f.name for f in FormaPago._meta.fields]:
                                        forma_pago_data['caja_id'] = caja_obj.id if caja_obj else None
                                    
                                    forma_pago_creada = FormaPago.objects.create(**forma_pago_data)
                                    print(f"✅ Forma de pago creada: ID={forma_pago_creada.id}, Tipo={sri_pago}, Monto=${monto}, Caja={caja_obj.descripcion if caja_obj else 'N/A'}")
                                    
                                except Exception as create_error:
                                    print(f"❌ Error creando forma de pago: {create_error}")
                                    print(f"Campos del modelo FormaPago: {[f.name for f in FormaPago._meta.fields]}")
                                    # Intentar crear con campos mínimos
                                    try:
                                        forma_pago_minima = FormaPago.objects.create(
                                            factura=factura,
                                            total=monto
                                        )
                                        print(f"✅ Forma de pago básica creada: ID={forma_pago_minima.id}, Monto=${monto}")
                                    except Exception as min_error:
                                        print(f"❌ Error creando forma de pago básica: {min_error}")
                            else:
                                print(f"⚠️ Pago {i+1} ignorado por monto cero o negativo: ${monto}")
                                
                        except Exception as pago_error:
                            print(f"❌ Error procesando pago individual {i+1}: {pago_error}")
                            continue
                    
                except json.JSONDecodeError as json_error:
                    print(f"❌ Error decodificando JSON de pagos: {json_error}")
                    print(f"Datos recibidos: {pagos_data}")
                    # 🚫 NO MÁS FALLBACKS - DATOS INCORRECTOS = ERROR CRÍTICO
                    raise Exception(f"DATOS DE PAGO INVÁLIDOS - JSON malformado: {json_error}")
                except Exception as general_error:
                    print(f"❌ Error general procesando formas de pago: {general_error}")
                    # 🚫 NO MÁS FALLBACKS - ERROR EN PROCESAMIENTO = FALLA CRÍTICA
                    raise Exception(f"ERROR PROCESANDO FORMAS DE PAGO: {general_error}")
                else:
                    print("❌ No se recibieron datos de pagos válidos")
                    # � ÚLTIMA LÍNEA DE DEFENSA: Crear pago automático si es factura pequeña
                    if factura.monto_general <= Decimal('100.00'):
                        print(f"🤖 CREANDO PAGO AUTOMÁTICO DE EMERGENCIA para factura de ${factura.monto_general}")
                        # Buscar primera caja activa
                        caja_obj = Caja.objects.filter(activo=True).first()
                        
                        # Importar FormaPago dinamicamente
                        from django.apps import apps
                        FormaPago = apps.get_model('inventario', 'FormaPago')
                        
                        forma_pago_emergencia = FormaPago.objects.create(
                            factura=factura,
                            forma_pago='01',  # Sin utilización del sistema financiero
                            total=factura.monto_general,
                            caja=caja_obj if caja_obj else None
                        )
                        print(f"✅ Pago de emergencia creado: ID={forma_pago_emergencia.id}, Monto=${factura.monto_general}")
                    else:
                        # �🚫 NO MÁS FALLBACKS - SIN DATOS = FALLA CRÍTICA
                        raise Exception("FORMAS DE PAGO REQUERIDAS - No se recibieron datos validos")
                        
        except Exception as e:
            print(f"❌ Error crítico en procesamiento de formas de pago: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # 🚫 NO MÁS FALLBACKS - ERROR CRÍTICO DEBE DETENER TODO
            raise Exception(f"PROCESAMIENTO DE FORMAS DE PAGO FALLÓ: {e}")

        # 🔍 VALIDACIÓN CRÍTICA: Verificar coherencia entre pagos y total de factura
        try:
            print("🔍 Validando coherencia entre formas de pago y total de factura...")
            
            # Calcular suma total de las formas de pago
            suma_pagos = Decimal('0.00')
            formas_pago_creadas = factura.formas_pago.all()
            
            print(f"📊 Total factura: ${factura.monto_general}")
            print(f"📊 Formas de pago creadas: {formas_pago_creadas.count()}")
            
            for forma_pago in formas_pago_creadas:
                print(f"  • Pago: ${forma_pago.total} (Código: {forma_pago.forma_pago})")
                suma_pagos += forma_pago.total
            
            print(f"📊 Suma total de pagos: ${suma_pagos}")
            
            # Validar que las sumas coincidan (con tolerancia mínima para decimales)
            tolerancia = Decimal('0.01')  # 1 centavo de tolerancia
            diferencia = abs(factura.monto_general - suma_pagos)
            
            if diferencia > tolerancia:
                # 🔧 INTENTO DE CORRECCIÓN AUTOMÁTICA para diferencias pequeñas por redondeos
                if diferencia <= Decimal('0.50') and formas_pago_creadas.count() == 1:
                    forma_pago = formas_pago_creadas.first()
                    print(f"🔧 CORRIGIENDO diferencia de ${diferencia} en pago único")
                    print(f"   Pago anterior: ${forma_pago.total}")
                    print(f"   Total factura: ${factura.monto_general}")
                    
                    # Ajustar el pago al total de la factura
                    forma_pago.total = factura.monto_general
                    forma_pago.save()
                    
                    print(f"✅ Pago corregido a: ${forma_pago.total}")
                    
                    # Recalcular para verificar
                    from django.db import models
                    suma_pagos_corregida = factura.formas_pago.all().aggregate(
                        total=models.Sum('total')
                    )['total'] or Decimal('0.00')
                    
                    diferencia_corregida = abs(factura.monto_general - suma_pagos_corregida)
                    print(f"📊 Diferencia después de corrección: ${diferencia_corregida}")
                    
                    if diferencia_corregida <= tolerancia:
                        print("✅ Corrección exitosa - coherencia restaurada")
                    else:
                        error_msg = (
                            f"INCOHERENCIA PERSISTENTE: "
                            f"Total factura (${factura.monto_general}) ≠ Suma pagos (${suma_pagos_corregida}). "
                            f"Diferencia: ${diferencia_corregida}"
                        )
                        print(f"❌ {error_msg}")
                        raise Exception(f"VALIDACIÓN FALLIDA - {error_msg}")
                else:
                    error_msg = (
                        f"INCOHERENCIA EN FORMAS DE PAGO: "
                        f"Total factura (${factura.monto_general}) ≠ Suma pagos (${suma_pagos}). "
                        f"Diferencia: ${diferencia}"
                    )
                    print(f"❌ {error_msg}")
                    raise Exception(f"VALIDACIÓN FALLIDA - {error_msg}")
            else:
                print(f"✅ Coherencia validada: Diferencia ${diferencia} dentro de tolerancia")
                
        except Exception as validation_error:
            print(f"❌ Error crítico en validación de coherencia: {validation_error}")
            # Eliminar formas de pago creadas para mantener consistencia
            try:
                factura.formas_pago.all().delete()
                print("🧹 Formas de pago eliminadas por error de validación")
            except:
                pass
            raise Exception(f"VALIDACIÓN DE COHERENCIA FALLÓ: {validation_error}")

        # ✅ AHORA SÍ: Guardar factura final (con formas de pago ya creadas y validadas)
        factura.save()
        try:
            from .sri.xml_generator import SRIXMLGenerator
            from .sri.firmador_xades import firmar_xml_xades_bes
            from django.conf import settings
            import os

            xml_generator = SRIXMLGenerator()
            media_root = getattr(settings, 'MEDIA_ROOT', 'media')
            xml_dir = os.path.join(media_root, 'facturas_xml')
            os.makedirs(xml_dir, exist_ok=True)
            print("=== DEBUG FACTURA ===")
            print(f"Factura ID: {factura.id}")
            print(f"Detalles: {factura.detallefactura_set.count()}")
            for d in factura.detallefactura_set.all():
                print(f"Detalle {d.id}: producto={d.producto}, servicio={d.servicio}, subtotal={d.sub_total}, impuestos={d.impuestos_detalle.count()}")
            print(f"Totales de impuestos: {factura.totales_impuestos.count()}")
            for ti in factura.totales_impuestos.all():
                print(f"TotalImpuesto: codigo={ti.codigo}, porcentaje={ti.codigo_porcentaje}, base={ti.base_imponible}, valor={ti.valor}")
            print(f"Formas de pago: {factura.formas_pago.count()}")
            xml_content = xml_generator.generar_xml_factura(factura)
            xml_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.xml"
            xml_output_path = os.path.join(xml_dir, xml_filename)
            with open(xml_output_path, 'w', encoding='utf-8') as xml_file:
                xml_file.write(xml_content)

            # Validar XML contra XSD oficial antes de firmar
            xml_generator.validar_xml_contra_xsd(xml_content, xml_generator._obtener_ruta_xsd())
            print("✅ XML validado exitosamente contra XSD")

            # Firmar el XML con XAdES-BES (NO XMLDSig básico)
            xml_firmado_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmada.xml"
            xml_firmado_output_path = os.path.join(xml_dir, xml_firmado_filename)
            try:
                print("🔐 Firmando XML con XAdES-BES (requerido por SRI)...")
                firmar_xml_xades_bes(xml_output_path, xml_firmado_output_path)
                print(f"✅ XML firmado exitosamente: {xml_firmado_output_path}")
            except Exception as e:
                print(f"❌ Error al firmar el XML: {e}")
                messages.error(request, f"Error al firmar el XML: {e}")

        except Exception as e:
            print(f"❌ Error generando/firmando XML SRI: {e}")
            messages.error(request, f"Error en el proceso electrónico: {e}")
        print(f"=== FACTURA ACTUALIZADA ===")
        print(f"Sub monto (totalSinImpuestos): {sub_monto}")
        print(f"Base imponible: {base_imponible}")
        print(f"Monto general (importeTotal): {monto_general}")
        print(f"Productos procesados: {productos_procesados}")
        print(f"Clave de acceso: {getattr(factura, 'clave_acceso', 'Se generará automáticamente')}")

        # ✅ IMPORTANTE: Limpiar la sesión ANTES de redirigir
        if 'factura_id' in request.session:
            del request.session['factura_id']
            print("🧹 Sesión limpiada correctamente")

        # ✅ Redirigir INMEDIATAMENTE a ver la factura cuando se finalice
        print(f"🚀 Redirigiendo a ver factura ID: {factura.id}")
        
        # Redirigir directamente a la vista de factura
        return redirect('inventario:verFactura', p=factura.id)

    # 🚫 FUNCIÓN ELIMINADA: _crear_forma_pago_por_defecto
    # Esta función creaba automáticamente pagos con código "01" cuando había errores,
    # lo que enviaba información incompleta al SRI. 
    # AHORA: Si no hay datos válidos de pago, el proceso DEBE fallar completamente.

    def get(self, request):
        try:
            # ✅ AGREGAR: Obtener las cajas activas
            cajas_activas = Caja.objects.filter(activo=True).order_by('descripcion')
            
            # ✅ AGREGAR: Obtener la factura de la sesión para mostrarla
            factura_id = request.session.get('factura_id')
            factura = None
            if factura_id:
                factura = Factura.objects.filter(pk=factura_id).first()
                if not factura:
                    messages.error(request, 'No se pudo encontrar la factura. Por favor, cree una nueva factura.')
                    return redirect('inventario:emitirFactura')
            else:
                messages.error(request, 'No se encontró la factura. Por favor, cree una nueva factura.')
                return redirect('inventario:emitirFactura')
            
            contexto = {
                'cajas': cajas_activas,  # ✅ ENVIAR cajas al template
                'factura': factura,      # ✅ ENVIAR factura al template
            }
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/factura/detallesFactura.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar detalles de factura: {str(e)}')
            return redirect('inventario:emitirFactura')
    
    def _obtener_codigo_porcentaje_iva(self, iva_percent):
        """
        Mapea el porcentaje de IVA al código que requiere el SRI
        Según tabla 17 de la ficha técnica SRI
        """
        mapping = {
            Decimal('0.00'): '0',    # 0%
            Decimal('0.12'): '2',    # 12% (tarifa actual)
            Decimal('0.15'): '3',    # 15% (tarifa histórica)
            Decimal('0.14'): '4',    # 14% (tarifa histórica)
        }
        return mapping.get(iva_percent, '0')  # Default 0% si no se encuentra

# Función mejorada para buscar productos
def buscar_producto(request):
    """
    Busca productos y servicios por código exacto o parcial.
    """
    try:
        codigo = request.GET.get('q', '').strip()
        print(f"🔍 Buscando producto o servicio con código: '{codigo}'")

        if not codigo:
            print("❌ Código vacío")
            return JsonResponse([], safe=False)

        resultados = []

        # Buscar producto exacto
        producto = Producto.objects.filter(codigo__iexact=codigo).first()
        if producto:
            resultados.append({
                'codigo': producto.codigo,
                'nombre': producto.descripcion,
                'precio': float(producto.precio) if producto.precio else 0.0,
                'tipo': 'producto'
            })

        # Buscar servicio exacto
        servicio = Servicio.objects.filter(codigo__iexact=codigo).first()
        if servicio:
            resultados.append({
                'codigo': servicio.codigo,
                'nombre': servicio.descripcion,
                'precio': float(servicio.precio1) if servicio.precio1 else 0.0,
                'tipo': 'servicio'
            })

        # Si no hay exactos, buscar parciales
        if not resultados:
            productos_similares = Producto.objects.filter(codigo__icontains=codigo)[:5]
            for p in productos_similares:
                resultados.append({
                    'codigo': p.codigo,
                    'nombre': p.descripcion,
                    'precio': float(p.precio) if p.precio else 0.0,
                    'tipo': 'producto'
                })
            servicios_similares = Servicio.objects.filter(codigo__icontains=codigo)[:5]
            for s in servicios_similares:
                resultados.append({
                    'codigo': s.codigo,
                    'nombre': s.nombre,
                    'precio': float(s.precio1) if s.precio1 else 0.0,
                    'tipo': 'servicio'
                })

        return JsonResponse(resultados, safe=False)

    except Exception as e:
        print(f"❌ Error en buscar_producto: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse([], safe=False)

#Muestra y procesa los detalles de cada producto de la factura--------------------------------#
class ListarFacturas(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        #Lista de productos de la BDD
        facturas = Factura.objects.all()
        
        # La sincronización automática con el SRI ha sido deshabilitada para mejorar el rendimiento
        # Solo se ejecutará cuando el usuario haga clic en "Autorizar documento" o similar
        # Si necesita verificar estados pendientes, use el botón de sincronización manual
        #Crea el paginador

        contexto = {'tabla': facturas}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/factura/listarFacturas.html', contexto)

    #Fin de vista---------------------------------------------------------------------------------------#


# Vista para autorizar documentos en el SRI - ELIMINADA (DUPLICADA)
# Esta función fue movida al final del archivo con la implementación actualizada


# Vista para consultar estado individual de una factura en el SRI ------------------------------#
@csrf_exempt
@require_http_methods(["POST"])
def consultar_estado_sri(request, factura_id):
    """
    Vista para consultar el estado individual de una factura en el SRI
    y mostrar los mensajes de error específicos
    """
    try:
        # Obtener la factura
        factura = get_object_or_404(Factura, id=factura_id)
        
        # Verificar que tenga clave de acceso
        if not hasattr(factura, 'clave_acceso') or not factura.clave_acceso:
            return JsonResponse({
                'success': False,
                'message': 'Esta factura no tiene clave de acceso. No se puede consultar el estado en el SRI.'
            })
        
        logger.info(f"Consultando estado SRI para factura {factura_id} - Clave: {factura.clave_acceso}")
        
        # Importar el módulo de integración SRI
        from .sri.integracion_django import SRIIntegration
        
        # Crear instancia de integración
        integration = SRIIntegration()
        
        # Consultar estado
        resultado = integration.consultar_autorizacion(factura.clave_acceso)
        
        # Procesar resultado
        if resultado['success']:
            # Actualizar la factura con la información obtenida
            estado_anterior = factura.estado_sri
            
            # El resultado contiene toda la información procesada
            nueva_info = {
                'estado': resultado.get('estado', 'DESCONOCIDO'),
                'mensaje': resultado.get('mensaje', ''),
                'detalle': resultado.get('mensaje_detalle', ''),
                'numero_autorizacion': resultado.get('numero_autorizacion', ''),
                'fecha_autorizacion': resultado.get('fecha_autorizacion', '')
            }
            
            # Actualizar campos de la factura
            factura.estado_sri = nueva_info['estado']
            if nueva_info['mensaje']:
                factura.mensaje_sri = nueva_info['mensaje']
            if nueva_info['detalle']:
                factura.mensaje_sri_detalle = nueva_info['detalle']
            if nueva_info['numero_autorizacion']:
                factura.numero_autorizacion = nueva_info['numero_autorizacion']
            if nueva_info['fecha_autorizacion']:
                try:
                    from datetime import datetime
                    factura.fecha_autorizacion = datetime.strptime(nueva_info['fecha_autorizacion'], '%d/%m/%Y %H:%M:%S')
                except:
                    pass
            
            factura.save()
            
            # Determinar si cambió el estado
            estado_cambio = estado_anterior != nueva_info['estado']
            
            logger.info(f"Estado consultado exitosamente: {nueva_info['estado']}")
            
            return JsonResponse({
                'success': True,
                'estado': nueva_info['estado'],
                'mensaje': nueva_info['mensaje'] or 'Consulta realizada exitosamente',
                'detalle': nueva_info['detalle'],
                'numero_autorizacion': nueva_info['numero_autorizacion'],
                'fecha_autorizacion': nueva_info['fecha_autorizacion'],
                'estado_cambio': estado_cambio
            })
        else:
            logger.error(f"Error al consultar estado: {resultado.get('message')}")
            return JsonResponse({
                'success': False,
                'message': f"""❌ Error al consultar el estado:

{resultado.get('message', 'Error desconocido')}

Posibles causas:
• Problemas de conectividad con el SRI
• Clave de acceso incorrecta
• Servicios del SRI temporalmente no disponibles"""
            })
            
    except ImportError:
        logger.error("No se pudo importar el módulo de integración del SRI")
        return JsonResponse({
            'success': False,
            'message': """❌ Error del sistema: Módulo de integración SRI no disponible

El sistema de consulta del SRI no está correctamente configurado.
Contacte al administrador del sistema."""
        })
    except Exception as e:
        logger.error(f"Error crítico al consultar estado de factura {factura_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f"""❌ Error interno del servidor:

{str(e)}

Si el problema persiste, contacte al soporte técnico."""
        })

#Fin de vista consultar estado SRI------------------------------------------------------------#


# Vista para listar facturas con problemas del SRI ------------------------------------------#
class FacturasSRIProblemas(LoginRequiredMixin, View):
    """
    Vista para mostrar todas las facturas que tienen problemas con el SRI
    """
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        from django.db.models import Q
        from datetime import datetime, timedelta
        
        # Obtener parámetros de filtro
        estado_filtro = request.GET.get('estado', '')
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        
        # Query base: facturas que tienen clave de acceso pero no están autorizadas
        query = Q(clave_acceso__isnull=False) & Q(clave_acceso__gt='')
        
        # Facturas con problemas: PENDIENTE, RECHAZADA, ERROR, o sin estado pero con más de 1 día
        problemas_query = (
            Q(estado_sri__in=['PENDIENTE', 'RECHAZADA', 'ERROR']) |
            Q(estado_sri__isnull=True, fecha_emision__lt=datetime.now().date() - timedelta(days=1)) |
            Q(estado_sri='', fecha_emision__lt=datetime.now().date() - timedelta(days=1))
        )
        
        query &= problemas_query
        
        # Aplicar filtros
        if estado_filtro:
            if estado_filtro == 'PENDIENTE':
                query &= (Q(estado_sri='PENDIENTE') | Q(estado_sri__isnull=True) | Q(estado_sri=''))
            else:
                query &= Q(estado_sri=estado_filtro)
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                query &= Q(fecha_emision__gte=fecha_desde_obj)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                query &= Q(fecha_emision__lte=fecha_hasta_obj)
            except ValueError:
                pass
        
        # Obtener facturas con problemas
        facturas = Factura.objects.filter(query).order_by('-fecha_emision', '-id')
        
        # Calcular estadísticas por estado
        from django.db.models import Count
        estadisticas = {}
        
        # Contar por estados específicos
        estados_count = facturas.values('estado_sri').annotate(count=Count('id'))
        for item in estados_count:
            estado = item['estado_sri'] or 'PENDIENTE'
            estadisticas[estado] = item['count']
        
        # Asegurar que siempre tengamos los estados principales
        estados_principales = ['PENDIENTE', 'RECHAZADA', 'ERROR', 'RECIBIDA']
        for estado in estados_principales:
            if estado not in estadisticas:
                estadisticas[estado] = 0
        
        contexto = {
            'facturas': facturas,
            'estadisticas': estadisticas,
            'filtros': {
                'estado': estado_filtro,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta
            }
        }
        contexto = complementarContexto(contexto, request.user)
        
        return render(request, 'inventario/factura/facturas_sri_problemas.html', contexto)

#Fin de vista facturas SRI problemas--------------------------------------------------------#


#Muestra los detalles individuales de una factura------------------------------------------------#
# Agregar estos imports al inicio del archivo views.py (después de las importaciones existentes)

# Reemplazar la clase VerFactura existente
class VerFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        try:
            # Obtener la factura
            factura = get_object_or_404(Factura, id=p)
            
            # Obtener los detalles de la factura
            detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto')
            
            # Obtener las opciones generales de la empresa
            try:
                opciones = Opciones.objects.first()
            except Opciones.DoesNotExist:
                opciones = None
            
            # === USAR FUNCIONES DE ADAPTACIÓN PARA XML Y RIDE ===
            datos_factura = adapt_factura(factura, detalles=detalles, opciones=opciones)
            
            # ✅ GENERAR XML ELECTRÓNICO SRI
            xml_path = None
            try:
                if opciones and detalles.exists():
                    from .sri.xml_generator import SRIXMLGenerator
                    xml_generator = SRIXMLGenerator(ambiente=datos_factura['emisor'].get('tipo_ambiente', '1'))
                    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
                    xml_dir = os.path.join(media_root, 'facturas_xml')
                    os.makedirs(xml_dir, exist_ok=True)
                    xml_content = xml_generator.generar_xml_factura(factura)
                    xml_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.xml"
                    xml_output_path = os.path.join(xml_dir, xml_filename)
                    with open(xml_output_path, 'w', encoding='utf-8') as xml_file:
                        xml_file.write(xml_content)
                    xml_path = xml_filename
                    logger.info(f"XML SRI generado exitosamente: {xml_output_path}")
            except Exception as e:
                logger.error(f"Error generando XML SRI: {e}")
                messages.warning(request, f'Error generando XML electrónico: {str(e)}')
            
            # ✅ GENERAR RIDE AUTOMÁTICAMENTE
            ride_path = None
            try:
                if opciones and detalles.exists():
                    ride_generator = RIDEGenerator()
                    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
                    pdf_dir = os.path.join(media_root, 'facturas_pdf')
                    logo_dir = os.path.join(media_root, 'logos')
                    os.makedirs(pdf_dir, exist_ok=True)
                    filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.pdf"
                    output_path = os.path.join(pdf_dir, filename)
                    logo_path = None
                    possible_logos = ['logo.png', 'logo.jpg', 'logo.jpeg', 'logo2.png']
                    for logo_name in possible_logos:
                        logo_test_path = os.path.join(logo_dir, logo_name)
                        if os.path.exists(logo_test_path):
                            logo_path = logo_test_path
                            break
                    if not logo_path:
                        static_logo = os.path.join('inventario', 'static', 'inventario', 'assets', 'logo', 'logo2.png')
                        if os.path.exists(static_logo):
                            logo_path = static_logo
                    clave_acceso = None
                    if xml_path:
                        try:
                            import xml.etree.ElementTree as ET
                            xml_file_path = os.path.join(media_root, 'facturas_xml', xml_path)
                            if os.path.exists(xml_file_path):
                                tree = ET.parse(xml_file_path)
                                clave_element = tree.find('.//claveAcceso')
                                if clave_element is not None:
                                    clave_acceso = clave_element.text
                        except Exception as e:
                            logger.warning(f"No se pudo extraer clave de acceso: {e}")
                    # Generar RIDE con firma electrónica opcional
                    try:
                        # Intentar generar y firmar el RIDE
                        ride_generator = RIDEGenerator()
                        result = ride_generator.generar_ride_factura_firmado(
                            factura=factura,
                            output_dir=pdf_dir,
                            firmar=True
                        )
                        
                        if isinstance(result, tuple):
                            # Si se firmó correctamente, devuelve (original, firmado)
                            ride_path = Path(result[1]).name  # Usar el PDF firmado
                        else:
                            # Si no se firmó, devuelve solo el path original
                            ride_path = Path(result).name
                            
                    except ImportError as e:
                        # 🚫 NO MÁS FALLBACKS - SI NO HAY FIRMA, NO SE GENERA NADA
                        logger.error(f"🚫 CRÍTICO: Error de importación para firma de PDF: {e}")
                        logger.error("🚫 NO SE GENERARÁ PDF SIN FIRMA VÁLIDA")
                        raise Exception(f"FIRMA DE PDF REQUERIDA - Error de importación: {e}")
                    except Exception as e:
                        # 🚫 NO MÁS FALLBACKS - SI LA FIRMA FALLA, TODO SE DETIENE
                        logger.error(f"🚫 CRÍTICO: Error en firma de PDF: {e}")
                        logger.error("🚫 NO SE GENERARÁ PDF SIN FIRMA VÁLIDA")
                        raise Exception(f"FIRMA DE PDF REQUERIDA - Error en firma: {e}")
                    logger.info(f"RIDE generado exitosamente: {output_path}")
            except Exception as e:
                logger.error(f"Error generando RIDE: {e}")
                messages.warning(request, f'La factura se muestra correctamente, pero hubo un error generando el PDF: {str(e)}')
            
            # ✅ AGREGAR MENSAJE DE FACTURA PROCESADA SOLO SI VIENE RECIÉN COMPLETADA
            if 'HTTP_REFERER' in request.META and 'detallesDeFactura' in request.META['HTTP_REFERER']:
                if detalles.exists():
                    mensaje_exito = f'🎉 ¡FACTURA PROCESADA EXITOSAMENTE! Número: {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia} | Total: ${factura.monto_general:.2f}'
                    if xml_path and ride_path:
                        mensaje_exito += ' | ✅ XML y RIDE generados'
                    messages.success(request, mensaje_exito)
            
            print(f"✅ Mostrando factura ID: {factura.id}")
            print(f"   - Número: {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}")
            print(f"   - Cliente: {factura.nombre_cliente}")
            print(f"   - Total: ${factura.monto_general}")
            print(f"   - Detalles encontrados: {detalles.count()}")
            print(f"   - XML SRI: {xml_path or 'No generado'}")
            print(f"   - RIDE PDF: {ride_path or 'No generado'}")
            
            contexto = {
                'factura': factura, 
                'detalles': detalles,
                'opciones': opciones,
                'xml_sri': xml_path,   # ✅ NUEVO: Ruta del XML generado
                'ride_pdf': ride_path  # ✅ EXISTENTE: Ruta del PDF generado
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/factura/verFactura.html', contexto)
            
        except Exception as e:
            print(f"❌ Error al mostrar factura: {e}")
            messages.error(request, f'Error al cargar la factura: {str(e)}')
            return redirect('inventario:listarFacturas')

    def post(self, request, p):
        """Permite descargar el RIDE (PDF) o el XML SRI - SIEMPRE FIRMA EL PDF"""
        try:
            factura = get_object_or_404(Factura, id=p)
            action = request.POST.get('action', 'download_pdf')
            media_root = getattr(settings, 'MEDIA_ROOT', 'media')

            if action == 'download_xml':
                # Descargar XML
                xml_dir = os.path.join(media_root, 'facturas_xml')
                xml_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmada.xml"
                xml_file_path = os.path.join(xml_dir, xml_filename)

                if os.path.exists(xml_file_path):
                    return FileResponse(open(xml_file_path, 'rb'), as_attachment=True, filename=xml_filename, content_type='application/xml')
                else:
                    messages.error(request, 'El archivo XML no está disponible.')
                    return redirect('inventario:verFactura', p=p)

            else:
                # Descargar PDF (RIDE) - SIEMPRE GENERAR Y FIRMAR
                pdf_dir = os.path.join(media_root, 'facturas_pdf')
                signed_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmado.pdf"
                unsigned_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.pdf"
                
                signed_path = os.path.join(pdf_dir, signed_filename)
                unsigned_path = os.path.join(pdf_dir, unsigned_filename)
                
                # Siempre intentar generar y firmar el PDF
                try:
                    # Obtener detalles y opciones necesarias
                    detalles = DetalleFactura.objects.filter(factura=factura)
                    opciones = Opciones.objects.first()
                    
                    # Generar directorio si no existe
                    os.makedirs(pdf_dir, exist_ok=True)
                    
                    # Generar RIDE firmado
                    ride_generator = RIDEGenerator()
                    result = ride_generator.generar_ride_factura_firmado(
                        factura=factura,
                        output_dir=pdf_dir,
                        firmar=True
                    )
                    
                    if isinstance(result, tuple):
                        # Se firmó correctamente, devuelve (original, firmado)
                        pdf_path = result[1]  # Usar el PDF firmado
                    else:
                        # No se firmó, devuelve solo el path original
                        pdf_path = result
                        
                    # Verificar que el archivo firmado existe
                    if os.path.exists(signed_path):
                        return FileResponse(open(signed_path, 'rb'), as_attachment=True, filename=signed_filename, content_type='application/pdf')
                    elif os.path.exists(pdf_path):
                        # Si no se pudo firmar, devolver el no firmado
                        return FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=os.path.basename(pdf_path), content_type='application/pdf')
                    else:
                        messages.error(request, 'Error al generar el PDF firmado.')
                        return redirect('inventario:verFactura', p=p)
                        
                except Exception as e:
                    logger.error(f"Error generando PDF firmado: {e}")
                    messages.error(request, f'Error al generar el PDF firmado: {str(e)}')
                    return redirect('inventario:verFactura', p=p)

        except Exception as e:
            messages.error(request, f'Error descargando archivo: {str(e)}')
            return redirect('inventario:verFactura', p=p)

#Fin de vista--------------------------------------------------------------------------------------#


#Genera la factura en CSV--------------------------------------------------------------------------#
class GenerarFactura(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        import csv

        factura = Factura.objects.get(id=p)
        detalles = DetalleFactura.objects.filter(id_factura_id=p)

        nombre_factura = "factura_%s.csv" % (factura.id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_factura
        writer = csv.writer(response)

        writer.writerow(['Producto', 'Cantidad', 'Sub-total', 'Total',
                         'Porcentaje IVA utilizado: %s' % (factura.iva.valor_iva)])

        for producto in detalles:
            writer.writerow([producto.id_producto.descripcion, producto.cantidad, producto.sub_total, producto.total])

        writer.writerow(['Total general:', '', '', factura.monto_general])

        return response

        #Fin de vista--------------------------------------------------------------------------------------#


#Genera la factura en PDF--------------------------------------------------------------------------#
class GenerarFacturaPDF(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        """Generar y descargar RIDE PDF - SIEMPRE FIRMA"""
        from django.conf import settings
        import os

        factura = get_object_or_404(Factura, id=p)
        media_root = getattr(settings, 'MEDIA_ROOT', 'media')
        pdf_dir = os.path.join(media_root, 'facturas_pdf')
        
        signed_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}_firmado.pdf"
        unsigned_filename = f"factura_{factura.establecimiento}_{factura.punto_emision}_{factura.secuencia}.pdf"
        
        signed_path = os.path.join(pdf_dir, signed_filename)
        unsigned_path = os.path.join(pdf_dir, unsigned_filename)
        
        # Siempre generar y firmar el PDF
        try:
            # Obtener detalles y opciones necesarias
            detalles = DetalleFactura.objects.filter(factura=factura)
            opciones = Opciones.objects.first()
            
            # Generar directorio si no existe
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Generar RIDE firmado
            ride_generator = RIDEGenerator()
            result = ride_generator.generar_ride_factura_firmado(
                factura=factura,
                output_dir=pdf_dir,
                firmar=True
            )
            
            if isinstance(result, tuple):
                # Se firmó correctamente, devuelve (original, firmado)
                pdf_path = result[1]  # Usar el PDF firmado
            else:
                # No se firmó, devuelve solo el path original
                pdf_path = result
                
            # Verificar que el archivo firmado existe
            if os.path.exists(signed_path):
                return FileResponse(open(signed_path, 'rb'), as_attachment=True, filename=signed_filename, content_type='application/pdf')
            elif os.path.exists(pdf_path):
                # Si no se pudo firmar, devolver el no firmado
                return FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=os.path.basename(pdf_path), content_type='application/pdf')
            else:
                messages.error(request, 'Error al generar el PDF firmado.')
                return redirect('inventario:verFactura', p=p)
                
        except Exception as e:
            logger.error(f"Error generando PDF firmado: {e}")
            messages.error(request, f'Error al generar el PDF firmado: {str(e)}')
            return redirect('inventario:verFactura', p=p)

        #Fin de vista--------------------------------------------------------------------------------------#


#Crea una lista de los clientes, 10 por pagina----------------------------------------#
class ListarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        #Saca una lista de todos los clientes de la BDD
        proveedores = Proveedor.objects.all()
        contexto = {'tabla': proveedores}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/proveedor/listarProveedores.html', contexto)
    #Fin de vista--------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar a un proveedor---------------------------------#
class AgregarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos:
        form = ProveedorFormulario(request.POST)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere

            cedula = form.cleaned_data['cedula']
            nombre = form.cleaned_data['nombre']
            apellido = form.cleaned_data['apellido']
            direccion = form.cleaned_data['direccion']
            nacimiento = form.cleaned_data['nacimiento']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            telefono2 = form.cleaned_data['telefono2']
            correo2 = form.cleaned_data['correo2']

            proveedor = Proveedor(cedula=cedula, nombre=nombre, apellido=apellido,
                                  direccion=direccion, nacimiento=nacimiento, telefono=telefono,
                                  correo=correo, telefono2=telefono2, correo2=correo2)
            proveedor.save()
            form = ProveedorFormulario()

            messages.success(request, 'Ingresado exitosamente bajo la ID %s.' % proveedor.id)
            request.session['proveedorProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarProveedor")
        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})

    def get(self, request):
        form = ProveedorFormulario()
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('proveedorProcesado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/agregarProveedor.html', contexto)


#Fin de vista-----------------------------------------------------------------------------#

#Formulario simple que procesa un script para importar los proveedores-----------------#
class ImportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesImportados'] = True
            return HttpResponseRedirect("/inventario/importarClientes")

    def get(self, request):
        form = ImportarClientesFormulario()

        if request.session.get('clientesImportados') == True:
            importado = request.session.get('clientesImportados')
            contexto = {'form': form, 'clientesImportados': importado}
            request.session['clientesImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/importarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los proveedores-----------------------#
class ExportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ExportarClientesFormulario(request.POST)
        if form.is_valid():
            request.session['clientesExportados'] = True

            #Se obtienen las entradas de producto en formato JSON
            data = serializers.serialize("json", Cliente.objects.all())
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("clientes.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("clientes.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="clientes.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarClientesFormulario()

        if request.session.get('clientesExportados') == True:
            exportado = request.session.get('clientesExportados')
            contexto = {'form': form, 'clientesExportados': exportado}
            request.session['clientesExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/cliente/exportarClientes.html', contexto)


#Fin de vista-------------------------------------------------------------------------#


#Muestra el mismo formulario del cliente pero con los datos a editar----------------------#
class EditarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        # Crea una instancia del formulario y la llena con los datos:
        proveedor = Proveedor.objects.get(id=p)
        form = ProveedorFormulario(request.POST, instance=proveedor)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            cedula = form.cleaned_data['cedula']
            nombre = form.cleaned_data['nombre']
            apellido = form.cleaned_data['apellido']
            direccion = form.cleaned_data['direccion']
            nacimiento = form.cleaned_data['nacimiento']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            telefono2 = form.cleaned_data['telefono2']
            correo2 = form.cleaned_data['correo2']

            proveedor.cedula = cedula
            proveedor.nombre = nombre
            proveedor.apellido = apellido
            proveedor.direccion = direccion
            proveedor.nacimiento = nacimiento
            proveedor.telefono = telefono
            proveedor.correo = correo
            proveedor.telefono2 = telefono2
            proveedor.correo2 = correo2
            proveedor.save()
            form = ProveedorFormulario(instance=proveedor)

            messages.success(request, 'Actualizado exitosamente el proveedor de ID %s.' % p)
            request.session['proveedorProcesado'] = 'editado'
            return HttpResponseRedirect("/inventario/editarProveedor/%s" % proveedor.id)
        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})

    def get(self, request, p):
        proveedor = Proveedor.objects.get(id=p)
        form = ProveedorFormulario(instance=proveedor)
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('proveedorProcesado'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/agregarProveedor.html', contexto)
    #Fin de vista--------------------------------------------------------------------------------#


#Agrega un pedido-----------------------------------------------------------------------------------#      
class AgregarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        cedulas = Proveedor.cedulasRegistradas()
        form = EmitirPedidoFormulario(cedulas=cedulas)
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/pedido/emitirPedido.html', contexto)

    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos:
        cedulas = Proveedor.cedulasRegistradas()
        form = EmitirPedidoFormulario(request.POST, cedulas=cedulas)
        # Revisa si es valido:
        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            request.session['form_details'] = form.cleaned_data['productos']
            request.session['id_proveedor'] = form.cleaned_data['proveedor']
            return HttpResponseRedirect("detallesPedido")
        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/pedido/emitirPedido.html', {'form': form})


#--------------------------------------------------------------------------------------------------#


#Lista todos los pedidos---------------------------------------------------------------------------#
class ListarPedidos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        #Saca una lista de todos los clientes de la BDD
        pedidos = Pedido.objects.all()
        contexto = {'tabla': pedidos}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/pedido/listarPedidos.html', contexto)

    #------------------------------------------------------------------------------------------------#


#Muestra y procesa los detalles de cada producto de la factura--------------------------------#
class DetallesPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        cedula = request.session.get('id_proveedor')
        productos = request.session.get('form_details')
        PedidoFormulario = formset_factory(DetallesPedidoFormulario, extra=productos)
        formset = PedidoFormulario()
        contexto = {'formset': formset}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/pedido/detallesPedido.html', contexto)

    def post(self, request):
        cedula = request.session.get('id_proveedor')
        productos = request.session.get('form_details')

        PedidoFormulario = formset_factory(DetallesPedidoFormulario, extra=productos)

        inicial = {
            'descripcion': '',
            'cantidad': 0,
            'subtotal': 0,
        }

        data = {
            'form-TOTAL_FORMS': productos,
            'form-INITIAL_FORMS': 0,
            'form-MAX_NUM_FORMS': '',
        }

        formset = PedidoFormulario(request.POST, data)

        if formset.is_valid():

            id_producto = []
            cantidad = []
            subtotal = []
            total_general = []
            sub_monto = 0
            monto_general = 0

            for form in formset:
                desc = form.cleaned_data['descripcion'].descripcion
                cant = form.cleaned_data['cantidad']
                sub = form.cleaned_data['valor_subtotal']

                id_producto.append(
                    obtenerIdProducto(desc))  #esta funcion, a estas alturas, es innecesaria porque ya tienes la id
                cantidad.append(cant)
                subtotal.append(sub)

                #Ingresa la factura
            #--Saca el sub-monto
            for index in subtotal:
                sub_monto += index

            #--Saca el monto general
            for index, element in enumerate(subtotal):
                if productoTieneIva(id_producto[index]):
                    nuevoPrecio = sacarIva(element)
                    monto_general += nuevoPrecio
                    total_general.append(nuevoPrecio)
                else:
                    monto_general += element
                    total_general.append(element)

            from datetime import date

            proveedor = Proveedor.objects.get(cedula=cedula)
            iva = ivaActual('objeto')
            presente = False
            pedido = Pedido(proveedor=proveedor, fecha=date.today(), sub_monto=sub_monto, monto_general=monto_general,
                            iva=iva,
                            presente=presente)

            pedido.save()
            id_pedido = pedido

            for indice, elemento in enumerate(id_producto):
                objetoProducto = obtenerProducto(elemento)
                cantidadDetalle = cantidad[indice]
                subDetalle = subtotal[indice]
                totalDetalle = total_general[indice]

                detallePedido = DetallePedido(id_pedido=id_pedido, id_producto=objetoProducto, cantidad=cantidadDetalle
                                              , sub_total=subDetalle, total=totalDetalle)
                detallePedido.save()

            messages.success(request, 'Pedido de ID %s insertado exitosamente.' % id_pedido.id)
            return HttpResponseRedirect("/inventario/agregarPedido")

        #Fin de vista-----------------------------------------------------------------------------------#


#Muestra los detalles individuales de un pedido------------------------------------------------#
class VerPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        pedido = Pedido.objects.get(id=p)
        detalles = DetallePedido.objects.filter(id_pedido_id=p)
        recibido = Pedido.recibido(p)
        contexto = {'pedido': pedido, 'detalles': detalles, 'recibido': recibido}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/pedido/verPedido.html', contexto)


#Fin de vista--------------------------------------------------------------------------------------#

#Valida un pedido ya insertado------------------------------------------------#
class ValidarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        pedido = Pedido.objects.get(id=p)
        detalles = DetallePedido.objects.filter(id_pedido_id=p)

        #Agrega los productos del pedido
        for elemento in detalles:
            elemento.id_producto.disponible += elemento.cantidad
            elemento.id_producto.save()

        pedido.presente = True
        pedido.save()
        messages.success(request, 'Pedido de ID %s verificado exitosamente.' % pedido.id)
        return HttpResponseRedirect("/inventario/verPedido/%s" % p)
    #Fin de vista--------------------------------------------------------------------------------------#


#Genera el pedido en CSV--------------------------------------------------------------------------#
class GenerarPedido(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        import csv

        pedido = Pedido.objects.get(id=p)
        detalles = DetallePedido.objects.filter(id_pedido_id=p)

        nombre_pedido = "pedido_%s.csv" % (pedido.id)

        response = HttpResponse(content_type='text/csv')

        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_pedido
        writer = csv.writer(response)

        writer.writerow(['Producto', 'Cantidad', 'Sub-total', 'Total',
                         'Porcentaje IVA utilizado: %s' % (pedido.iva.valor_iva)])

        for producto in detalles:
            writer.writerow([producto.id_producto.descripcion, producto.cantidad, producto.sub_total, producto.total])

        writer.writerow(['Total general:', '', '', pedido.monto_general])

        return response

        #Fin de vista--------------------------------------------------------------------------------------#


#Genera el pedido en PDF--------------------------------------------------------------------------#
class GenerarPedidoPDF(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        pedido = Pedido.objects.get(id=p)
        general = Opciones.objects.get(id=1)
        detalles = DetallePedido.objects.filter(id_pedido_id=p)

        data = {
            'fecha': pedido.fecha,
            'monto_general': pedido.monto_general,
            'nombre_proveedor': pedido.proveedor.nombre + " " + pedido.proveedor.apellido,
            'cedula_proveedor': pedido.proveedor.cedula,
            'id_reporte': pedido.id,
            'iva': pedido.iva.valor_iva,
            'detalles': detalles,
            'modo': 'pedido',
            'general': general
        }

        nombre_pedido = "pedido_%s.pdf" % (pedido.id)

        pdf = render_to_pdf('inventario/PDF/prueba.html', data)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="%s"' % nombre_pedido

        return response
        #Fin de vista--------------------------------------------------------------------------------------#


#Crea un nuevo usuario--------------------------------------------------------------#
class CrearUsuario(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        if request.user.is_superuser:
            form = NuevoUsuarioFormulario()
            #Envia al usuario el formulario para que lo llene
            contexto = {'form': form, 'modo': request.session.get('usuarioCreado')}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/usuario/crearUsuario.html', contexto)
        else:
            messages.error(request, 'No tiene los permisos para crear un usuario nuevo')
            return HttpResponseRedirect('/inventario/panel')

    def post(self, request):
        form = NuevoUsuarioFormulario(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            rep_password = form.cleaned_data['rep_password']
            level = form.cleaned_data['level']

            error = 0

            if password == rep_password:
                pass

            else:
                error = 1
                messages.error(request, 'La clave y su repeticion tienen que coincidir')

            if usuarioExiste(Usuario, 'username', username) is False:
                pass

            else:
                error = 1
                messages.error(request, "El nombre de usuario '%s' ya existe. eliga otro!" % username)

            if usuarioExiste(Usuario, 'email', email) is False:
                pass

            else:
                error = 1
                messages.error(request, "El correo '%s' ya existe. eliga otro!" % email)

            if (error == 0):
                if level == '0':
                    nuevoUsuario = Usuario.objects.create_user(username=username, password=password, email=email)
                    nivel = 0
                elif level == '1':
                    nuevoUsuario = Usuario.objects.create_superuser(username=username, password=password, email=email)
                    nivel = 1

                nuevoUsuario.first_name = first_name
                nuevoUsuario.last_name = last_name
                nuevoUsuario.nivel = nivel
                nuevoUsuario.save()

                messages.success(request, 'Usuario creado exitosamente')
                return HttpResponseRedirect('/inventario/crearUsuario')

            else:
                return HttpResponseRedirect('/inventario/crearUsuario')


#Fin de vista----------------------------------------------------------------------


#Lista todos los usuarios actuales--------------------------------------------------------------#
class ListarUsuarios(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        usuarios = Usuario.objects.all()
        #Envia al usuario el formulario para que lo llene
        contexto = {'tabla': usuarios}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/usuario/listarUsuarios.html', contexto)

    def post(self, request):
        pass

    #Fin de vista----------------------------------------------------------------------


#Importa toda la base de datos, primero crea una copia de la actual mientras se procesa la nueva--#
class ImportarBDD(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        if request.user.is_superuser == False:
            messages.error(request, 'Solo los administradores pueden importar una nueva base de datos')
            return HttpResponseRedirect('/inventario/panel')

        form = ImportarBDDFormulario()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/BDD/importar.html', contexto)

    def post(self, request):
        form = ImportarBDDFormulario(request.POST, request.FILES)

        if form.is_valid():
            ruta = 'inventario/archivos/BDD/inventario_respaldo.xml'
            manejarArchivo(request.FILES['archivo'], ruta)

            try:
                call_command('loaddata', ruta, verbosity=0)
                messages.success(request, 'Base de datos subida exitosamente')
                return HttpResponseRedirect('/inventario/importarBDD')
            except Exception:
                messages.error(request, 'El archivo esta corrupto')
                return HttpResponseRedirect('/inventario/importarBDD')


#Fin de vista--------------------------------------------------------------------------------


#Descarga toda la base de datos en un archivo---------------------------------------------#
class DescargarBDD(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        #Se obtiene la carpeta donde se va a guardar y despues se crea el respaldo ahi
        fs = FileSystemStorage('inventario/archivos/tmp/')
        with fs.open('inventario_respaldo.xml', 'w') as output:
            call_command('dumpdata', 'inventario', indent=4, stdout=output, format='xml',
                         exclude=['contenttypes', 'auth.permission'])

            output.close()

        #Lo de abajo es para descargarlo
        with fs.open('inventario_respaldo.xml', 'r') as output:
            response = HttpResponse(output.read(), content_type="application/force-download")
            response['Content-Disposition'] = 'attachment; filename="inventario_respaldo.xml"'

            #Cierra el archivo
            output.close()

            #Borra el archivo
            ruta = 'inventario/archivos/tmp/inventario_respaldo.xml'
            call_command('erasefile', ruta)

            #Regresa el archivo a descargar
            return response


#Fin de vista--------------------------------------------------------------------------------


#Configuracion general de varios elementos--------------------------------------------------#
class ConfiguracionGeneral(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        conf = Opciones.objects.get(id=1)
        form = OpcionesFormulario()
        
        # Campos existentes
        # Campos de texto simple
        form['identificacion'].field.widget.attrs['value'] = conf.identificacion
        form['razon_social'].field.widget.attrs['value'] = conf.razon_social
        form['nombre_comercial'].field.widget.attrs['value'] = conf.nombre_comercial
        form['correo'].field.widget.attrs['value'] = conf.correo
        form['telefono'].field.widget.attrs['value'] = conf.telefono
        form['moneda'].field.widget.attrs['value'] = conf.moneda
        form['valor_iva'].field.widget.attrs['value'] = conf.valor_iva
        form['nombre_negocio'].field.widget.attrs['value'] = conf.nombre_negocio
        
        # Campos Textarea usan .initial en lugar de .widget.attrs['value']
        form.fields['direccion_establecimiento'].initial = conf.direccion_establecimiento
        form.fields['mensaje_factura'].initial = conf.mensaje_factura
        
        # Campos Select
        form.fields['obligado'].initial = conf.obligado
        form.fields['tipo_regimen'].initial = conf.tipo_regimen
        
        # CAMPOS NUEVOS QUE FALTABAN - Información tributaria especial
        form.fields['es_contribuyente_especial'].initial = conf.es_contribuyente_especial
        if conf.numero_contribuyente_especial:
            form['numero_contribuyente_especial'].field.widget.attrs['value'] = conf.numero_contribuyente_especial
        else:
            form['numero_contribuyente_especial'].field.widget.attrs['value'] = ''
        
        form.fields['es_agente_retencion'].initial = conf.es_agente_retencion
        if conf.numero_agente_retencion:
            form['numero_agente_retencion'].field.widget.attrs['value'] = conf.numero_agente_retencion
        else:
            form['numero_agente_retencion'].field.widget.attrs['value'] = ''
        
        # Agregar la configuración al contexto para acceder directamente en la plantilla
        contexto = {
            'form': form,
            'configuracion': conf  # Añadir la configuración al contexto
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/configuracion.html', contexto)
    
    def post(self, request):
        form = OpcionesFormulario(request.POST, request.FILES)
        if form.is_valid():
            conf = Opciones.objects.get(id=1)
            conf.identificacion = form.cleaned_data['identificacion']
            conf.razon_social = form.cleaned_data['razon_social']
            conf.nombre_comercial = form.cleaned_data['nombre_comercial']
            conf.direccion_establecimiento = form.cleaned_data['direccion_establecimiento']  # <-- SOLO ESTE
            conf.correo = form.cleaned_data['correo']
            conf.telefono = form.cleaned_data['telefono']
            conf.obligado = form.cleaned_data['obligado']
            conf.tipo_regimen = form.cleaned_data['tipo_regimen']
            conf.moneda = form.cleaned_data['moneda']
            conf.valor_iva = form.cleaned_data['valor_iva']
            conf.mensaje_factura = form.cleaned_data['mensaje_factura']
            conf.nombre_negocio = form.cleaned_data['nombre_negocio']
            conf.es_contribuyente_especial = form.cleaned_data['es_contribuyente_especial']
            conf.numero_contribuyente_especial = form.cleaned_data['numero_contribuyente_especial'] or None
            conf.es_agente_retencion = form.cleaned_data['es_agente_retencion']
            conf.numero_agente_retencion = form.cleaned_data['numero_agente_retencion'] or None

            imagen = request.FILES.get('imagen', False)
            if imagen:
                conf.imagen = imagen  # Solo si se subió una nueva imagen

            conf.save()
            messages.success(request, 'Configuración actualizada exitosamente!')
            return HttpResponseRedirect("/inventario/configuracionGeneral")
        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/configuracion.html', contexto)
#Fin de vista--------------------------------------------------------------------------------


#Accede a los modulos del manual de usuario---------------------------------------------#
class VerManualDeUsuario(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, pagina):
        if pagina == 'inicio':
            return render(request, 'inventario/manual/index.html')

        if pagina == 'producto':
            return render(request, 'inventario/manual/producto.html')

        if pagina == 'proveedor':
            return render(request, 'inventario/manual/proveedor.html')

        if pagina == 'pedido':
            return render(request, 'inventario/manual/pedido.html')

        if pagina == 'clientes':
            return render(request, 'inventario/manual/clientes.html')

        if pagina == 'factura':
            return render(request, 'inventario/manual/factura.html')

        if pagina == 'usuarios':
            return render(request, 'inventario/manual/usuarios.html')

        if pagina == 'opciones':
            return render(request, 'inventario/manual/opciones.html')


#Fin de vista--------------------------------------------------------------------------------

class Secuencias(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            secuencias = Secuencia.objects.all()
            form = SecuenciaFormulario()  # Formulario vacío para crear una nueva secuencia
            contexto = {'form': form, 'secuencias': secuencias}
            contexto = complementarContexto(contexto, request.user)  # Añade información adicional al contexto
            return render(request, 'inventario/opciones/secuencias.html', contexto)
        except Exception as e:
            messages.error(request, f"Error al cargar las secuencias: {e}")
            return redirect('inventario:panel')

    def post(self, request):
        secuencia_id = request.POST.get('id', None)  # Recuperar el ID del formulario (puede ser None)
        form = SecuenciaFormulario(request.POST)

        if form.is_valid():
            try:
                # Si se proporciona un ID, intenta buscar la secuencia para actualizar
                if secuencia_id and Secuencia.objects.filter(id=secuencia_id).exists():
                    secuencia = Secuencia.objects.get(id=secuencia_id)
                    for field, value in form.cleaned_data.items():
                        setattr(secuencia, field, value)
                    secuencia.save()
                    messages.success(request, f'Secuencia actualizada exitosamente con ID {secuencia.id}!')
                else:
                    # Si no hay ID, o el ID no existe, crear una nueva secuencia
                    nueva_secuencia = form.save()
                    messages.success(request, f'Nueva secuencia creada exitosamente con ID {nueva_secuencia.id}!')
                return redirect('inventario:secuencias')

            except Exception as e:
                messages.error(request, f'Error al actualizar o crear la secuencia: {e}')
        else:
            messages.error(request, 'Error en los datos del formulario.')

        # Recargar las secuencias si hay errores
        try:
            secuencias = Secuencia.objects.all()
            contexto = {'form': form, 'secuencias': secuencias}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/secuencias.html', contexto)
        except Exception as e:
            messages.error(request, f"Error al recargar las secuencias: {e}")
            return redirect('inventario:panel')


class ListaSecuencias(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        # Recuperar todas las secuencias de la base de datos
        secuencias = Secuencia.objects.all()
        contexto = {'secuencias': secuencias}
        contexto = complementarContexto(contexto, request.user)  # Añade información al contexto si es necesario
        return render(request, 'inventario/opciones/lista_secuencias.html', contexto)


class EliminarSecuencia(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        secuencia = get_object_or_404(Secuencia, id=id)
        secuencia.delete()
        messages.success(request, f'Secuencia con ID {id} eliminada exitosamente.')
        return redirect('inventario:lista_secuencias')


class EditarSecuencia(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, *args, **kwargs):
        try:
            # Extraemos el 'id' desde los argumentos de la URL
            secuencia_id = kwargs.get('id')
            # Obtenemos la secuencia o lanzamos 404 si no existe
            secuencia = get_object_or_404(Secuencia, id=secuencia_id)
            # Inicializamos el formulario con la instancia de la secuencia
            form = SecuenciaFormulario(instance=secuencia)
            # Renderizamos la plantilla con el formulario
            return render(request, 'inventario/opciones/editar_secuencia.html', {'form': form, 'secuencia': secuencia})
        except Exception as e:
            messages.error(request, f"Error al cargar la secuencia para edición: {e}")
            return redirect('inventario:secuencias')

    def post(self, request, *args, **kwargs):
        try:
            # Extraemos el 'id' desde los argumentos de la URL
            secuencia_id = kwargs.get('id')
            # Obtenemos la secuencia o lanzamos 404 si no existe
            secuencia = get_object_or_404(Secuencia, id=secuencia_id)
            # Vinculamos los datos enviados con la instancia existente
            form = SecuenciaFormulario(request.POST, instance=secuencia)

            if form.is_valid():
                # Guardamos los cambios si el formulario es válido
                form.save()
                messages.success(request, 'Secuencia actualizada correctamente.')
                return redirect('inventario:lista_secuencias')  # Redirige a la lista de secuencias
            else:
                messages.error(request, 'Error en los datos enviados.')
                return render(request, 'inventario/opciones/editar_secuencia.html', {'form': form, 'secuencia': secuencia})
        except Exception as e:
            messages.error(request, f"Error al actualizar la secuencia: {e}")
            return redirect('inventario:secuencias')

class CrearFacturador(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        form = FacturadorForm()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/facturador_form.html', contexto)

    def post(self, request):
        form = FacturadorForm(request.POST)
        
        if form.is_valid():
            try:
                # Crear el facturador usando el manager personalizado
                facturador = Facturador.objects.create_facturador(
                    nombres=form.cleaned_data['nombres'],
                    telefono=form.cleaned_data.get('telefono', ''),
                    correo=form.cleaned_data['correo'],
                    password=form.cleaned_data['password'],  # Se encriptará automáticamente
                    descuento_permitido=form.cleaned_data.get('descuento_permitido', 0.00),
                    activo=form.cleaned_data.get('activo', True)
                )
                
                messages.success(request, f'Facturador {facturador.nombres} creado exitosamente.')
                return redirect('inventario:listar_facturadores')
                
            except Exception as e:
                print(f"Error al crear facturador: {e}")
                messages.error(request, f'Error al crear el facturador: {str(e)}')
        else:
            print("Errores en el formulario:", form.errors)
            messages.error(request, 'Por favor, corrija los errores en el formulario.')
        
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/facturador_form.html', contexto)

# Listar Facturadores
class ListarFacturadores(View):
    def get(self, request):
        facturadores = Facturador.objects.all()
        # Asegúrate de que la plantilla esté en la ruta correcta
        return render(request, 'inventario/opciones/facturador_list.html', {'facturadores': facturadores})

# Editar Facturador
class EditarFacturador(View):
    def get(self, request, id):
        # Recupera el facturador o lanza 404 si no existe
        facturador = get_object_or_404(Facturador, id=id)
        # Crea el formulario con los datos existentes
        form = FacturadorForm(instance=facturador)
        return render(request, 'inventario/opciones/editar_facturador.html', {
            'form': form,
            'facturador': facturador
        })

    def post(self, request, id):
        # Recupera el facturador o lanza 404 si no existe
        facturador = get_object_or_404(Facturador, id=id)

        # Copia los datos del formulario para evitar problemas con el checkbox
        data = request.POST.copy()
        # Si el checkbox no se envía, se considera como False
        data['activo'] = data.get('activo') == 'True'

        # Crea el formulario con los datos enviados y el facturador a editar
        form = FacturadorForm(data, instance=facturador)

        if form.is_valid():
            # Guarda los cambios si el formulario es válido
            form.save()
            messages.success(request, 'Facturador actualizado exitosamente.')
            return redirect('inventario:listar_facturadores')
        else:
            # Muestra los errores en la consola para depuración
            print(form.errors)
            messages.error(request, 'Revise los datos proporcionados. Hay errores en el formulario.')
            # Reenvía el formulario con los errores al usuario
            return render(request, 'inventario/opciones/editar_facturador.html', {
                'form': form,
                'facturador': facturador
            })

# Eliminar Facturador
class EliminarFacturador(View):
    def get(self, request, id):
        facturador = get_object_or_404(Facturador, id=id)
        facturador.delete()
        messages.success(request, 'Facturador eliminado exitosamente.')
        return redirect('inventario:listar_facturadores')

class LoginFacturador(View):
    def post(self, request):
        try:
            # Obtener solo la contraseña del formulario
            password = request.POST.get('password')
            
            if not password:
                messages.error(request, 'La contraseña es requerida.')
                return render(request, 'inventario/facturador/login_facturador.html')
            
            # Buscar el facturador que tenga esta contraseña entre todos los activos
            facturadores = Facturador.objects.filter(activo=True)
            facturador_valido = None
            
            for facturador in facturadores:
                if facturador.check_password(password):
                    facturador_valido = facturador
                    break
            
            if facturador_valido:
                # Guardar la sesión del facturador
                request.session['facturador_id'] = facturador_valido.id
                request.session['facturador_nombre'] = facturador_valido.nombres
                
                messages.success(request, f'Bienvenido {facturador_valido.nombres}')
                return redirect('inventario:emitirFactura')
            else:
                messages.error(request, 'Contraseña incorrecta. Verifique e intente nuevamente.')
                return render(request, 'inventario/facturador/login_facturador.html')
                
        except Exception as e:
            print(f"Error en LoginFacturador: {e}")
            messages.error(request, 'Error interno del servidor.')
            return render(request, 'inventario/facturador/login_facturador.html')

    def get(self, request):
        # Mostrar el formulario de login
        return render(request, 'inventario/facturador/login_facturador.html')

#Para agregar los almacénes
def gestion_almacenes(request):
    if request.method == 'POST':
        form = AlmacenForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Almacén agregado exitosamente.")
            return redirect('inventario:gestion_almacenes')
  # Asegúrate de que el nombre de la URL es correcto
    else:
        form = AlmacenForm()

    almacenes = Almacen.objects.all()
    context = {
        'form': form,
        'almacenes': almacenes,
    }
    return render(request, 'inventario/opciones/almacenes.html', context)


def editar_almacen(request, id):
    almacen = get_object_or_404(Almacen, id=id)
    if request.method == 'POST':
        form = AlmacenForm(request.POST, instance=almacen)
        if form.is_valid():
            form.save()
            messages.success(request, "Almacén editado exitosamente.")
            return redirect('inventario:gestion_almacenes')
    else:
        form = AlmacenForm(instance=almacen)

    context = {
        'form': form,
        'edit_mode': True,
        'almacen': almacen,
    }
    return render(request, 'inventario/opciones/almacenes_form.html', context)

def eliminar_almacen(request, id):
    almacen = get_object_or_404(Almacen, id=id)
    almacen.delete()
    messages.success(request, "Almacén eliminado exitosamente.")
    return redirect('inventario:gestion_almacenes')


# Agregar al final del archivo views.py, antes de las funciones de almacén

class RideView(LoginRequiredMixin, View):
    """Vista para mostrar el RIDE en HTML"""
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        try:
            # Obtener la factura
            factura = get_object_or_404(Factura, id=p)
            
            # Obtener los detalles de la factura
            detalles = DetalleFactura.objects.filter(factura=factura).select_related('producto')
            
            # Obtener las opciones generales de la empresa
            try:
                opciones = Opciones.objects.first()
            except Opciones.DoesNotExist:
                opciones = None
            
            if not detalles.exists():
                messages.error(request, 'La factura no tiene detalles para mostrar.')
                return redirect('inventario:verFactura', p=p)
            
            contexto = {
                'factura': factura,
                'detalles': detalles,
                'opciones': opciones
            }
            
            return render(request, 'inventario/sri/factura_ride.html', contexto)
            
        except Exception as e:
            messages.error(request, f'Error al mostrar RIDE: {str(e)}')
            return redirect('inventario:verFactura', p=p)

# === FUNCIONES DE ADAPTACIÓN PARA SRI/XML/PDF ===
def adapt_opciones(opciones):
    """
    Adapta una instancia de Opciones a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'ruc': getattr(opciones, 'identificacion', '0000000000000'),
        'razon_social': getattr(opciones, 'razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
        'nombre_comercial': getattr(opciones, 'nombre_comercial', ''),
        'direccion_matriz': getattr(opciones, 'direccion_establecimiento', '[CONFIGURAR DIRECCIÓN]'),
        'telefono': getattr(opciones, 'telefono', ''),
        'email': getattr(opciones, 'correo', ''),
        'contribuyente_especial': getattr(opciones, 'numero_contribuyente_especial', None) if getattr(opciones, 'es_contribuyente_especial', False) else None,
        'obligado_contabilidad': 'SI' if getattr(opciones, 'obligado', 'SI') == 'SI' else 'NO',
        'tipo_ambiente': getattr(opciones, 'tipo_ambiente', '1'),
        'tipo_emision': getattr(opciones, 'tipo_emision', '1'),
        'moneda': getattr(opciones, 'moneda', 'DOLAR'),
        'valor_iva': getattr(opciones, 'valor_iva', 15),
    }

def adapt_cliente(cliente):
    """
    Adapta una instancia de Cliente a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'tipo_identificacion': getattr(cliente, 'tipoIdentificacion', '04'),
        'identificacion': getattr(cliente, 'identificacion', '9999999999999'),
        'razon_social': getattr(cliente, 'razon_social', 'CONSUMIDOR FINAL'),
        'nombre_comercial': getattr(cliente, 'nombre_comercial', ''),
        'direccion': getattr(cliente, 'direccion', ''),
        'telefono': getattr(cliente, 'telefono', ''),
        'correo': getattr(cliente, 'correo', ''),
    }

def adapt_producto(producto):
    """
    Adapta una instancia de Producto a un dict compatible con SRI/ride_generator/xml_generator
    """
    return {
        'codigo': getattr(producto, 'codigo', ''),
        'descripcion': getattr(producto, 'descripcion', ''),
        'precio': float(getattr(producto, 'precio', 0)),
        'iva': getattr(producto, 'iva', '0'),
        'categoria': getattr(producto, 'categoria', ''),
        'disponible': getattr(producto, 'disponible', 0),
    }

def adapt_detallefactura(detalle):
    """
    Adapta una instancia de DetalleFactura a un dict compatible con SRI/ride_generator/xml_generator
    """
    producto = getattr(detalle, 'producto', None)
    prod_dict = adapt_producto(producto) if producto else {}
    return {
        'codigo_principal': prod_dict.get('codigo', ''),
        'descripcion': prod_dict.get('descripcion', ''),
        'cantidad': float(getattr(detalle, 'cantidad', 0)),
        'precio_unitario': float(getattr(detalle, 'precio_unitario', prod_dict.get('precio', 0))),
        'descuento': float(getattr(detalle, 'descuento', 0) or 0),
        'precio_total_sin_impuesto': float(getattr(detalle, 'total', getattr(detalle, 'sub_total', 0))),
        'codigo_porcentaje_iva': prod_dict.get('iva', '0'),
    }

def adapt_factura(factura, detalles=None, opciones=None):
    """
    Adapta una instancia de Factura y sus detalles a un dict compatible con SRI/ride_generator/xml_generator
    """
    detalles = detalles or []
    opciones_dict = adapt_opciones(opciones) if opciones else {}
    fecha_emision = getattr(factura, 'fecha_emision', None)
    if isinstance(fecha_emision, str):
        fecha_emision_str = fecha_emision
    elif fecha_emision is not None:
        fecha_emision_str = fecha_emision.strftime("%d/%m/%Y")
    else:
        fecha_emision_str = ''
    return {
        'emisor': opciones_dict,
        'fecha_emision': fecha_emision_str,
        'establecimiento': getattr(factura, 'establecimiento', '001'),
        'punto_emision': getattr(factura, 'punto_emision', '001'),
        'secuencial': getattr(factura, 'secuencia', '000000001'),
        'cliente': adapt_cliente(getattr(factura, 'cliente', None)) if getattr(factura, 'cliente', None) else {},
        'identificacion_cliente': getattr(factura, 'identificacion_cliente', '9999999999999'),
        'nombre_cliente': getattr(factura, 'nombre_cliente', 'CONSUMIDOR FINAL'),
        'direccion_cliente': getattr(factura, 'direccion_cliente', ''),
        'detalles': [adapt_detallefactura(d) for d in detalles],
        'totales': {
            'subtotal_sin_impuestos': float(getattr(factura, 'sub_total', getattr(factura, 'sub_monto', 0))),
            'subtotal_0': 0.0,  # Ajustar si hay lógica para 0%
            'subtotal_15': float(getattr(factura, 'sub_total', getattr(factura, 'sub_monto', 0))),  # Ajustar según IVA
            'descuento_total': float(getattr(factura, 'descuento', 0) or 0),
            'iva_15': float(getattr(factura, 'iva', getattr(factura, 'monto_general', 0) - getattr(factura, 'sub_monto', 0))),
            'importe_total': float(getattr(factura, 'monto_general', 0)),
        },
        'concepto': getattr(factura, 'concepto', ''),
        'clave_acceso': getattr(factura, 'clave_acceso', None),
    }

#Crea una lista de los proveedores, 10 por pagina----------------------------------------#
class ListarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        from django.db import models
        #Saca una lista de todos los proveedores de la BDD
        proveedores = Proveedor.objects.all()
        contexto = {'tabla': proveedores}
        contexto = complementarContexto(contexto, request.user)

        return render(request, 'inventario/proveedor/listarProveedores.html', contexto)

#Fin de vista--------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar a un proveedor---------------------------------#
class AgregarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        # Crea una instancia del formulario y la llena con los datos:
        form = ProveedorFormulario(request.POST)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos con form.cleaned_data como se requiere
            nombre = form.cleaned_data['nombre']
            apellido = form.cleaned_data['apellido']
            cedula = form.cleaned_data['cedula']
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            telefono_secundario = form.cleaned_data['telefono_secundario']
            observaciones = form.cleaned_data['observaciones']

            proveedor = Proveedor(nombre=nombre, apellido=apellido, cedula=cedula, direccion=direccion,
                                  telefono=telefono,
                                  correo=correo, telefono_secundario=telefono_secundario,
                                  observaciones=observaciones)

            proveedor.save()
            form = ProveedorFormulario()
            messages.success(request, 'Ingresado exitosamente bajo la ID %s.' % proveedor.id)
            request.session['proveedorProcesado'] = 'agregado'
            return HttpResponseRedirect("/inventario/agregarProveedor")
        else:
            #De lo contrario lanzara el mismo formulario
            messages.error(request, 'Error al agregar el proveedor, ya existe o se encuentra en la base de datos')
            return render(request, 'inventario/proveedor/agregarProveedor.html', {'form': form})

    def get(self, request):
        form = ProveedorFormulario()
        #Envia al usuario el formulario para que lo llene
        contexto = {'form': form, 'modo': request.session.get('proveedorProcesado')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/agregarProveedor.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Formulario simple que procesa un script para importar los proveedores-----------------#
class ImportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ImportarProveedoresFormulario(request.POST)
        if form.is_valid():
            request.session['proveedoresImportados'] = True
            return HttpResponseRedirect("/inventario/importarProveedores")

    def get(self, request):
        form = ImportarProveedoresFormulario()

        if request.session.get('proveedoresImportados') == True:
            importado = request.session.get('proveedoresImportados')
            contexto = {'form': form, 'proveedoresImportados': importado}
            request.session['proveedoresImportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/importarProveedores.html', contexto)

#Fin de vista-------------------------------------------------------------------------#


#Formulario simple que crea un archivo y respalda los proveedores-----------------------#
class ExportarProveedores(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        form = ExportarProveedoresFormulario(request.POST)
        if form.is_valid():
            request.session['proveedoresExportados'] = True

            #Se obtienen las entradas de proveedor en formato JSON
            data = serializers.serialize("json", Proveedor.objects.all())
            fs = FileSystemStorage('inventario/tmp/')

            #Se utiliza la variable fs para acceder a la carpeta con mas facilidad
            with fs.open("proveedores.json", "w") as out:
                out.write(data)
                out.close()

            with fs.open("proveedores.json", "r") as out:
                response = HttpResponse(out.read(), content_type="application/force-download")
                response['Content-Disposition'] = 'attachment; filename="proveedores.json"'
                out.close()
                #------------------------------------------------------------
            return response

    def get(self, request):
        form = ExportarProveedoresFormulario()

        if request.session.get('proveedoresExportados') == True:
            exportado = request.session.get('proveedoresExportados')
            contexto = {'form': form, 'proveedoresExportados': exportado}
            request.session['proveedoresExportados'] = False

        else:
            contexto = {'form': form}
            contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/exportarProveedores.html', contexto)

#Fin de vista-------------------------------------------------------------------------#


#Muestra el mismo formulario del proveedor pero con los datos a editar----------------------#
class EditarProveedor(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, p):
        # Crea una instancia del formulario y la llena con los datos:
        form = ProveedorFormulario(request.POST)
        # Revisa si es valido:

        if form.is_valid():
            # Procesa y asigna los datos with form.cleaned_data como se requiere
            nombre = form.cleaned_data['nombre']
            apellido = form.cleaned_data['apellido']
            cedula = form.cleaned_data['cedula']
            direccion = form.cleaned_data['direccion']
            telefono = form.cleaned_data['telefono']
            correo = form.cleaned_data['correo']
            telefono_secundario = form.cleaned_data['telefono_secundario']
            observaciones = form.cleaned_data['observaciones']

            proveedor = Proveedor.objects.get(id=p)
            proveedor.nombre = nombre
            proveedor.apellido = apellido
            proveedor.cedula = cedula
            proveedor.direccion = direccion
            proveedor.telefono = telefono
            proveedor.correo = correo
            proveedor.telefono_secundario = telefono_secundario
            proveedor.observaciones = observaciones
            proveedor.save()

            messages.success(request, 'Proveedor editado exitosamente')
            return HttpResponseRedirect("/inventario/editarProveedor/%s" % p)

        else:
            #De lo contrario lanzara el mismo formulario
            return render(request, 'inventario/proveedor/editarProveedor.html', {'form': form})

    def get(self, request, p):
        proveedor = Proveedor.objects.get(id=p)
        form = ProveedorFormulario()

        #Llena el formulario con los datos del proveedor
        form['nombre'].field.widget.attrs['value'] = proveedor.nombre
        form['apellido'].field.widget.attrs['value'] = proveedor.apellido
        form['cedula'].field.widget.attrs['value'] = proveedor.cedula
        form['direccion'].field.widget.attrs['value'] = proveedor.direccion
        form['telefono'].field.widget.attrs['value'] = proveedor.telefono
        form['correo'].field.widget.attrs['value'] = proveedor.correo
        form['telefono_secundario'].field.widget.attrs['value'] = proveedor.telefono_secundario
        form['observaciones'].field.widget.attrs['value'] = proveedor.observaciones

        contexto = {'form': form, 'proveedor': proveedor}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/proveedor/editarProveedor.html', contexto)
        
#VISTAS PARA CAJA
class ListarCajas(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            cajas = Caja.objects.all().order_by('descripcion')
            contexto = {'tabla': cajas}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/listar_cajas.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar las cajas: {str(e)}')
            return redirect('inventario:panel')

#Fin de vista--------------------------------------------------------------------------------#


#Crea y procesa un formulario para agregar una caja-----------------------------------------#
class AgregarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        form = CajaFormulario()
        contexto = {'form': form, 'modo': request.session.get('cajaProcesada')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/crear_caja.html', contexto)

    def post(self, request):
        form = CajaFormulario(request.POST)
        if form.is_valid():
            try:
                caja = form.save(commit=False)
                caja.creado_por = request.user
                caja.save()
                messages.success(request, f'Caja "{caja.descripcion}" creada exitosamente.')
                request.session['cajaProcesada'] = 'agregada'
                return redirect('inventario:agregarCaja')
            except Exception as e:
                messages.error(request, f'Error al crear la caja: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{form.fields[field].label}: {error}')
        
        contexto = {'form': form, 'modo': request.session.get('cajaProcesada')}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/crear_caja.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Muestra el mismo formulario pero con los datos a editar--------------------------------#
class EditarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            caja = get_object_or_404(Caja, id=id)
            form = CajaFormulario(instance=caja)
            contexto = {'form': form, 'caja': caja, 'modo': request.session.get('cajaProcesada'), 'editar': True}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/editar_caja.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la caja: {str(e)}')
            return redirect('inventario:listarCajas')

    def post(self, request, id):
        try:
            caja = get_object_or_404(Caja, id=id)
            form = CajaFormulario(request.POST, instance=caja)
            if form.is_valid():
                caja_actualizada = form.save()
                messages.success(request, f'Caja "{caja_actualizada.descripcion}" actualizada exitosamente.')
                request.session['cajaProcesada'] = 'editada'
                return redirect('inventario:editarCaja', id=caja.id)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{form.fields[field].label}: {error}')
        except Exception as e:
            messages.error(request, f'Error al actualizar la caja: {str(e)}')
        
        contexto = {'form': form, 'caja': caja, 'modo': request.session.get('cajaProcesada'), 'editar': True}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/cajas/editar_caja.html', contexto)

#Fin de vista-----------------------------------------------------------------------------#


#Muestra los detalles de una caja en modo solo lectura----------------------------------#
class VerCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            caja = get_object_or_404(Caja, id=id)
            from django.utils import timezone
            dias_desde_creacion = (timezone.now().date() - caja.fecha_creacion.date()).days
            contexto = {'caja': caja, 'dias_desde_creacion': dias_desde_creacion, 'modo': 'ver'}
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/cajas/ver_caja.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar los detalles de la caja: {str(e)}')
            return redirect('inventario:listarCajas')

#Fin de vista-----------------------------------------------------------------------------#


#Elimina una caja con validaciones-------------------------------------------------------#
class EliminarCaja(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, id):
        try:
            caja = get_object_or_404(Caja, id=id)
            nombre_caja = caja.descripcion
            caja.delete()
            messages.success(request, f'Caja "{nombre_caja}" eliminada exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar la caja: {str(e)}')
        return redirect('inventario:listarCajas')

    def get(self, request, id):
        messages.warning(request, 'Método no permitido para eliminar cajas.')
        return redirect('inventario:listarCajas')


# === VISTAS PARA GESTIÓN DE BANCOS ===

#Lista todos los cuentas bancarias--------------------------------------------------------------#
class ListarBancos(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        try:
            # Obtener todas las cuentas bancarias ordenadas por banco
            bancos = Banco.objects.all().order_by('banco', 'titular')
            
            # Agregar contexto común del sistema
            contexto = {'bancos': bancos}
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/listar_bancos.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar las cuentas bancarias: {str(e)}')
            return redirect('inventario:panel')

#Fin de vista--------------------------------------------------------------------------------#


class CrearBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        form = BancoFormulario()
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/bancos/crear_banco.html', contexto)

    def post(self, request):
        form = BancoFormulario(request.POST)
        
        if form.is_valid():
            try:
                # Crear nueva cuenta bancaria
                banco = form.save(commit=False)
                banco.creado_por = request.user
                banco.save()
                messages.success(request, 'Cuenta bancaria creada exitosamente.')
                return redirect('inventario:listar_bancos')  # ✅ CORRECTO
            except Exception as e:
                messages.error(request, f'Error al crear la cuenta bancaria: {str(e)}')
        else:
            # Mostrar errores de validación
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        # ❌ ESTABA MAL: return render(request, 'cajas/crear_caja.html', {'title': 'Agregar Caja', 'form': form})
        # ✅ CORRECTO:
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/bancos/crear_banco.html', contexto)


class EditarBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            banco = get_object_or_404(Banco, id=id)
            form = BancoFormulario(instance=banco)
            
            contexto = {
                'form': form, 
                'banco': banco,
                'modo': 'editar'
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/bancos/editar_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
    
    def post(self, request, id):
        try:
            banco = get_object_or_404(Banco, id=id)
            form = BancoFormulario(request.POST, instance=banco)
            if form.is_valid():
                form.save()
                # ❌ ESTABA MAL: messages.success(request, 'Caja actualizada exitosamente.')
                # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
                # ✅ CORRECTO:
                messages.success(request, 'Cuenta bancaria actualizada exitosamente.')
                return redirect('inventario:listar_bancos')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        except Exception as e:
            # ❌ ESTABA MAL: messages.error(request, f'Error al actualizar la caja: {str(e)}')
            # ✅ CORRECTO:
            messages.error(request, f'Error al actualizar la cuenta bancaria: {str(e)}')
        
        # ❌ ESTABA MAL: return render(request, 'cajas/editar_caja.html', {'title': 'Editar Caja', 'form': form, 'caja': banco})
        # ✅ CORRECTO:
        contexto = {
            'form': form, 
            'banco': banco,
            'modo': 'editar'
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/editar_banco.html', contexto)


class VerBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            banco = get_object_or_404(Banco, id=id)
            
            # Calcular información adicional
            from django.utils import timezone
            dias_desde_apertura = (timezone.now().date() - banco.fecha_apertura).days if banco.fecha_apertura else 0
            
            contexto = {
                'banco': banco,  # ✅ CORRECTO: banco, no caja
                'dias_desde_apertura': dias_desde_apertura,
                'modo': 'ver'
            }
            contexto = complementarContexto(contexto, request.user)
            
            return render(request, 'inventario/opciones/ver_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar los detalles de la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')


class EliminarBanco(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, id):
        try:
            banco = get_object_or_404(Banco, id=id)
            # ❌ ESTABA MAL: return render(request, 'cajas/eliminar_caja.html', {'title': 'Eliminar Caja', 'caja': banco})
            # ✅ CORRECTO:
            contexto = {
                'banco': banco,
                'titulo': 'Eliminar Cuenta Bancaria'
            }
            contexto = complementarContexto(contexto, request.user)
            return render(request, 'inventario/opciones/eliminar_banco.html', contexto)
        except Exception as e:
            messages.error(request, f'Error al cargar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
    
    def post(self, request, id):
        try:
            banco = get_object_or_404(Banco, id=id)
            nombre_banco = f"{banco.banco} - {banco.titular}"
            banco.delete()
            # ❌ ESTABA MAL: messages.success(request, 'Caja eliminada exitosamente.')
            # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
            # ✅ CORRECTO:
            messages.success(request, f'Cuenta bancaria "{nombre_banco}" eliminada exitosamente.')
            return redirect('inventario:listar_bancos')
        except Exception as e:
            # ❌ ESTABA MAL: messages.error(request, f'Error al eliminar la caja: {str(e)}')
            # ❌ ESTABA MAL: return redirect('inventario:listarCajas')
            # ✅ CORRECTO:
            messages.error(request, f'Error al eliminar la cuenta bancaria: {str(e)}')
            return redirect('inventario:listar_bancos')
        

        
class FirmaElectronicaView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None
    
    def get(self, request):
        # Usar get_or_create para asegurar que existe una instancia
        opciones, created = Opciones.objects.get_or_create(pk=1)
        
        # Si se creó una nueva instancia, mostrar mensaje informativo
        if created:
            messages.info(request, 'Se ha creado una nueva configuración de empresa. Por favor, complete los datos.')
        
        form = FirmaElectronicaForm(instance=opciones)
        aviso_caducidad = self._obtener_aviso_caducidad(opciones)
        
        contexto = {
            'form': form,
            'aviso_caducidad': aviso_caducidad,
            'now': date.today(),
            'opciones': opciones  # Agregar opciones al contexto para debugging
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/firma_electronica.html', contexto)
    
    def post(self, request):
        # Usar get_or_create para asegurar que existe una instancia
        opciones, created = Opciones.objects.get_or_create(pk=1)
        form = FirmaElectronicaForm(request.POST, request.FILES, instance=opciones)
        
        if form.is_valid():
            try:
                # Guardar el formulario
                opciones_guardadas = form.save()
                
                # Validar la firma electrónica si se subió
                if opciones_guardadas.firma_electronica and opciones_guardadas.password_firma:
                    messages.success(request, 'Firma electrónica actualizada correctamente.')
                else:
                    messages.success(request, 'Configuración actualizada correctamente.')
                # Recargar la instancia para mostrar datos actualizados
                opciones.refresh_from_db()
                form = FirmaElectronicaForm(instance=opciones)
                
            except ValidationError as e:
                messages.error(request, f'Error de validación: {e.message}')
            except Exception as e:
                messages.error(request, f'Error al guardar la firma electrónica: {str(e)}')
                # En caso de error, mantener el formulario con los datos ingresados
        else:
            # Si el formulario no es válido, mostrar errores
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        # Obtener aviso de caducidad actualizado
        aviso_caducidad = self._obtener_aviso_caducidad(opciones)
        
        contexto = {
            'form': form,
            'aviso_caducidad': aviso_caducidad,
            'now': date.today(),
            'opciones': opciones
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/opciones/firma_electronica.html', contexto)
        
    def _obtener_aviso_caducidad(self, opciones):
        """
        Método privado para obtener el aviso de caducidad
        """
        aviso_caducidad = None
        if opciones and opciones.fecha_caducidad_firma:
            try:
                dias_restantes = (opciones.fecha_caducidad_firma - date.today()).days
                if dias_restantes < 0:
                    aviso_caducidad = "¡La firma electrónica ha caducado!"
                elif dias_restantes <= 30:
                    aviso_caducidad = f"Atención: La firma electrónica caduca en {dias_restantes} días."
                elif dias_restantes <= 90:
                    aviso_caducidad = f"Información: La firma electrónica caduca en {dias_restantes} días."
            except Exception as e:
                print(f"Error calculando días restantes: {e}")
        return aviso_caducidad
class EliminarFirmaElectronicaView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request):
        opciones = Opciones.objects.get(pk=1)
        eliminado = False
        if opciones.firma_electronica:
            # Intenta borrar el archivo físico usando el método delete()
            try:
                opciones.firma_electronica.delete(save=False)
                eliminado = True
            except Exception as e:
                messages.error(request, f'Error eliminando archivo físico: {e}')
            # Limpia la referencia en la base de datos
            opciones.firma_electronica = None
            opciones.fecha_caducidad_firma = None
            opciones.save()
            if eliminado:
                messages.success(request, 'Firma electrónica eliminada correctamente.')
            else:
                messages.warning(request, 'No se pudo eliminar el archivo físico, pero la referencia fue eliminada.')
        else:
            messages.info(request, 'No hay firma electrónica para eliminar.')
        return HttpResponseRedirect(reverse('inventario:firma_electronica'))


from .models import Servicio
from .forms import ServicioFormulario
from django.urls import reverse_lazy

# Listar servicios
class ListarServicios(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        servicios = Servicio.objects.all().order_by('-fecha_creacion')
        contexto = {'servicios': servicios}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/listarServicios.html', contexto)
# Agregar servicio
from .funciones import generar_codigo_servicio

class AgregarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request):
        codigo_nuevo = generar_codigo_servicio()
        form = ServicioFormulario(initial={'codigo': codigo_nuevo})
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)

    def post(self, request):
        form = ServicioFormulario(request.POST)
        contexto = {'form': form}
        contexto = complementarContexto(contexto, request.user)
        if form.is_valid():
            form.save()
            return redirect('inventario:listarServicios')
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)
# Editar servicio
class EditarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        servicio = Servicio.objects.get(pk=p)
        form = ServicioFormulario(instance=servicio)
        contexto = {'form': form, 'edit_mode': True, 'servicio': servicio}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)

    def post(self, request, p):
        servicio = Servicio.objects.get(pk=p)
        form = ServicioFormulario(request.POST, instance=servicio)
        contexto = {'form': form, 'edit_mode': True, 'servicio': servicio}
        contexto = complementarContexto(contexto, request.user)
        if form.is_valid():
            form.save()
            return redirect('inventario:listarServicios')
        return render(request, 'inventario/servicios/agregarServicio.html', contexto)


class EliminarServicio(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, p):
        servicio = Servicio.objects.get(pk=p)
        servicio.delete()
        return redirect('inventario:listarServicios')
    

@csrf_exempt
@require_http_methods(["GET"])
def buscar_empresa(request):
    ruc = request.GET.get('q', '')
    if not ruc:
        return JsonResponse({'error': True, 'message': 'El RUC es requerido'}, status=400)
    try:
        from services import consultar_ruc as servicio_consultar_ruc
        resultado = servicio_consultar_ruc(ruc)
        
        # Registrar los datos recibidos para depuración
        logger.info(f"Datos recibidos de la API: {resultado}")
        
        # Extraer los campos básicos
        razon_social = resultado.get('razon_social', '')
        nombre_comercial = resultado.get('nombre_comercial', '')
        direccion = resultado.get('direccion', '')
        
        # Usar directamente los campos ya mapeados en services.py
        tipo_regimen = resultado.get('tipo_regimen', 'GENERAL')
        obligado_contabilidad = resultado.get('obligado_contabilidad', 'NO')
        
        # Registrar los valores que se enviarán al frontend
        logger.info(f"Valores que se enviarán al frontend:")
        logger.info(f"  razon_social: {razon_social}")
        logger.info(f"  nombre_comercial: {nombre_comercial}")
        logger.info(f"  direccion: {direccion}")
        logger.info(f"  correo: {resultado.get('email', '')}")
        logger.info(f"  telefono: {resultado.get('telefono', '')}")
        logger.info(f"  obligado_contabilidad: {obligado_contabilidad}")
        logger.info(f"  tipo_regimen: {tipo_regimen}")
        logger.info(f"  actividad_economica: {resultado.get('actividad_economica', '')}")
        
        # Construir y devolver la respuesta JSON
        respuesta = {
            'error': False,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'direccion': direccion,
            'correo': resultado.get('email', ''),
            'telefono': resultado.get('telefono', ''),
            'obligado_contabilidad': obligado_contabilidad,
            'tipo_regimen': tipo_regimen,
            'actividad_economica': resultado.get('actividad_economica', ''),
        }
        
        logger.info(f"Respuesta JSON completa: {respuesta}")
        return JsonResponse(respuesta)
    except Exception as e:
        logger.error(f"Error en buscar_empresa: {e}")
        return JsonResponse({'error': True, 'message': f'Error consultando API externa: {e}'}, status=500)


class FormasPagoView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def get(self, request, factura_id):
        # Obtener la factura
        factura = get_object_or_404(Factura, pk=factura_id)
        
        # Obtener cajas activas
        cajas = Caja.objects.filter(activo=True).order_by('descripcion')
        
        # Usar las opciones de forma de pago del modelo FormaPago directamente
        formas_pago_sri = FormaPago.FORMAS_PAGO_CHOICES
        
        # Seleccionar la primera caja por defecto
        primera_caja = cajas.first()
        
        contexto = {
            'factura': factura,
            'cajas': cajas,
            'formas_pago_sri': formas_pago_sri,
            'primera_caja': primera_caja,
            'total': factura.monto_general or factura.sub_monto or 0,
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/factura/formas_pago.html', contexto)


class GuardarFormaPagoView(LoginRequiredMixin, View):
    login_url = '/inventario/login'
    redirect_field_name = None

    def post(self, request, factura_id):
        factura = get_object_or_404(Factura, pk=factura_id)
        
        try:
            # Obtener datos del formulario
            forma_pago_codigo = request.POST.get('forma_pago')  # Ahora es el código directamente
            caja_id = request.POST.get('caja')
            monto_recibido = request.POST.get('monto_recibido') or request.POST.get('monto_efectivo')
            
            # Validar datos
            if not forma_pago_codigo or not caja_id or not monto_recibido:
                return JsonResponse({
                    'success': False,
                    'message': 'Todos los campos son obligatorios'
                })
            
            # Obtener objetos
            caja = get_object_or_404(Caja, pk=caja_id)
            
            # Validar que el código de forma de pago sea válido
            codigos_validos = [codigo for codigo, _ in FormaPago.FORMAS_PAGO_CHOICES]
            if forma_pago_codigo not in codigos_validos:
                return JsonResponse({
                    'success': False,
                    'message': 'Código de forma de pago inválido'
                })
            
            # Convertir monto
            try:
                monto = Decimal(str(monto_recibido))
            except:
                return JsonResponse({
                    'success': False,
                    'message': 'Monto inválido'
                })
            
            # Calcular cambio
            total_factura = factura.monto_general or factura.sub_monto or 0
            cambio = monto - total_factura
            
            # Guardar forma de pago usando el modelo correcto
            forma_pago_factura = FormaPago.objects.create(
                factura=factura,
                forma_pago=forma_pago_codigo,  # Usar directamente el código
                caja=caja,
                total=monto  # El modelo FormaPago usa 'total', no 'monto'
            )
            
            # Log para debugging
            logger.info(f"✅ Forma de pago guardada: ID={forma_pago_factura.id}, Código={forma_pago_codigo}, Total=${monto}")
            
            return JsonResponse({
                'success': True,
                'message': 'Forma de pago guardada exitosamente',
                'cambio': str(cambio) if cambio > 0 else '0.00',
                'redirect_url': reverse('inventario:detallesDeFactura')
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al guardar forma de pago: {str(e)}'
            })

def validar_facturador(request):
    """Vista para validar las credenciales del facturador solo con contraseña"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password')

            if not password:
                return JsonResponse({'success': False, 'error': 'La contraseña es requerida'})

            # Buscar el facturador que tenga esta contraseña entre todos los activos
            facturadores = Facturador.objects.filter(activo=True)
            facturador_valido = None
            
            for facturador in facturadores:
                if check_password(password, facturador.password):
                    facturador_valido = facturador
                    break

            if facturador_valido:
                # Guardar el facturador en la sesión
                request.session['facturador_id'] = facturador_valido.id
                request.session['facturador_nombre'] = facturador_valido.nombres
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Contraseña incorrecta'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error del servidor: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


# ✅ NUEVAS VISTAS PARA INTEGRACIÓN SRI COMPLETA
@csrf_exempt
def autorizar_documento_sri(request, factura_id):
    """
    Vista para autorizar un documento electrónico en el SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe
        factura = get_object_or_404(Factura, id=factura_id)
        
        # Procesar factura en el SRI
        integration = SRIIntegration()
        resultado = integration.procesar_factura(factura_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'message': 'Documento procesado correctamente en el SRI',
                'resultado': {
                    'estado': factura.estado_sri or resultado.get('resultado', {}).get('estado', 'PROCESADO'),
                    'numero_autorizacion': factura.numero_autorizacion,
                    'fecha_autorizacion': factura.fecha_autorizacion.isoformat() if factura.fecha_autorizacion else None,
                    'clave_acceso': factura.clave_acceso,
                    'mensaje': resultado.get('message', 'Procesado exitosamente')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error desconocido'),
                'error_detalle': resultado.get('resultado', {})
            })
            
    except Factura.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en autorizar_documento_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


@csrf_exempt
def consultar_estado_sri(request, factura_id):
    """
    Vista para consultar el estado de un documento en el SRI
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe
        factura = get_object_or_404(Factura, id=factura_id)
        
        if not factura.clave_acceso:
            return JsonResponse({
                'success': False,
                'message': 'La factura no tiene clave de acceso generada'
            })
        
        # Consultar estado en el SRI
        integration = SRIIntegration()
        resultado = integration.consultar_estado_factura(factura_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'resultado': {
                    'estado_sri': factura.estado_sri,
                    'numero_autorizacion': factura.numero_autorizacion,
                    'fecha_autorizacion': factura.fecha_autorizacion.isoformat() if factura.fecha_autorizacion else None,
                    'clave_acceso': factura.clave_acceso,
                    'mensaje_sri': factura.mensaje_sri
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error consultando estado')
            })
            
    except Factura.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en consultar_estado_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


@csrf_exempt
def sincronizar_masivo_sri(request):
    """
    Sincroniza masivamente el estado de todas las facturas pendientes con el SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        from django.db.models import Q
        
        # Obtener facturas que necesitan sincronización
        facturas_pendientes = Factura.objects.filter(
            Q(estado_sri__isnull=True) | 
            Q(estado_sri='PENDIENTE') | 
            Q(estado_sri='RECIBIDA') |
            Q(estado_sri='') |
            Q(estado_sri='NO_AUTORIZADA')
        ).filter(
            clave_acceso__isnull=False
        ).exclude(
            clave_acceso=''
        ).order_by('-fecha_emision')
        
        total_facturas = facturas_pendientes.count()
        actualizadas = 0
        errores = 0
        rechazadas = 0
        
        integration = SRIIntegration()
        resultados = []
        
        for factura in facturas_pendientes[:50]:  # Limitar a 50 para evitar timeout
            try:
                estado_anterior = factura.estado_sri or 'SIN_ESTADO'
                
                # Consultar estado en el SRI
                resultado = integration.consultar_estado_factura(factura.id)
                
                if resultado['success']:
                    # Recargar la factura para obtener el estado actualizado
                    factura.refresh_from_db()
                    estado_nuevo = factura.estado_sri
                    
                    if estado_nuevo in ('RECHAZADA', 'NO_AUTORIZADA'):
                        rechazadas += 1
                    
                    resultados.append({
                        'numero': factura.numero,
                        'clave_acceso': factura.clave_acceso,
                        'estado_anterior': estado_anterior,
                        'estado_nuevo': estado_nuevo,
                        'fecha_autorizacion': factura.fecha_autorizacion.isoformat() if factura.fecha_autorizacion else None,
                        'mensaje': factura.mensaje_sri or '',
                        'success': True
                    })
                    actualizadas += 1
                else:
                    resultados.append({
                        'numero': factura.numero,
                        'clave_acceso': factura.clave_acceso,
                        'estado_anterior': estado_anterior,
                        'error': resultado.get('message', 'Error desconocido'),
                        'success': False
                    })
                    errores += 1
                        
            except Exception as e:
                resultados.append({
                    'numero': factura.numero,
                    'clave_acceso': factura.clave_acceso,
                    'estado_anterior': estado_anterior,
                    'error': str(e),
                    'success': False
                })
                errores += 1
        
        return JsonResponse({
            'success': True,
            'total_facturas': total_facturas,
            'procesadas': len(resultados),
            'actualizadas': actualizadas,
            'rechazadas': rechazadas,
            'errores': errores,
            'resultados': resultados
        })
                
    except Exception as e:
        logger.error(f"Error en sincronización masiva SRI: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }, status=500)


@csrf_exempt
def validar_xml_factura(request, factura_id):
    """
    Valida el XML de una factura específica contra el XSD del SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe
        factura = get_object_or_404(Factura, id=factura_id)
        
        if not factura.clave_acceso:
            return JsonResponse({
                'success': False,
                'message': 'La factura no tiene clave de acceso generada'
            })
        
        integration = SRIIntegration()
        
        try:
            # Generar XML con validación
            xml_path = integration.generar_xml_factura(factura, validar_xsd=True)
            
            return JsonResponse({
                'success': True,
                'message': 'XML generado y validado exitosamente',
                'xml_path': xml_path,
                'validacion': 'XML cumple con el XSD del SRI'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'XML no válido según XSD del SRI',
                'error': str(e),
                'validacion': 'XML NO cumple con el XSD'
            })
            
    except Factura.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en validar_xml_factura: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


@csrf_exempt
def reenviar_factura_sri(request, factura_id):
    """
    Vista para reenviar una factura rechazada al SRI
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)
    
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe
        factura = get_object_or_404(Factura, id=factura_id)
        
        # Reenviar factura
        integration = SRIIntegration()
        resultado = integration.reenviar_factura(factura_id)
        
        if resultado['success']:
            return JsonResponse({
                'success': True,
                'message': 'Factura reenviada exitosamente',
                'resultado': {
                    'estado': factura.estado_sri,
                    'mensaje': resultado.get('message', 'Reenviado exitosamente')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': resultado.get('message', 'Error reenviando factura')
            })
            
    except Factura.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error en reenviar_factura_sri: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        })


def generar_xml_factura_view(request, factura_id):
    """
    Vista para generar solo el XML de una factura (sin enviar al SRI)
    """
    try:
        from inventario.sri.integracion_django import SRIIntegration
        
        # Verificar que la factura existe
        factura = get_object_or_404(Factura, id=factura_id)
        
        # Generar XML
        integration = SRIIntegration()
        xml_path = integration.generar_xml_factura(factura)
        
        # Leer el XML generado
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Devolver como respuesta HTTP
        response = HttpResponse(xml_content, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="factura_{factura.numero}.xml"'
        
        return response
        
    except Factura.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'No se encontró la factura con ID {factura_id}'
        })
    except Exception as e:
        logger.error(f"Error generando XML: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error generando XML: {str(e)}'
        })