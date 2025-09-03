from django.http import HttpResponse
from django.shortcuts import render
from .models import Almacen, Facturador, Empresa

def debug_proforma_data(request):
    """Vista temporal para debuggear datos de proforma"""
    
    html_content = """
    <html>
    <head><title>Debug Proforma Data</title></head>
    <body>
    <h1>Debug de Datos para Proformas</h1>
    """
    
    # Verificar empresas
    empresas = Empresa.objects.all()
    html_content += f"<h2>Empresas ({empresas.count()})</h2>"
    if empresas.exists():
        html_content += "<ul>"
        for empresa in empresas:
            html_content += f"<li>{empresa.razon_social} (ID: {empresa.id})</li>"
        html_content += "</ul>"
    else:
        html_content += "<p>❌ No hay empresas</p>"
    
    # Verificar almacenes
    almacenes = Almacen.objects.all()
    almacenes_activos = Almacen.objects.filter(activo=True)
    html_content += f"<h2>Almacenes (Total: {almacenes.count()}, Activos: {almacenes_activos.count()})</h2>"
    
    if almacenes.exists():
        html_content += "<ul>"
        for almacen in almacenes:
            estado = "✅ Activo" if almacen.activo else "❌ Inactivo"
            empresa_info = f" - Empresa: {almacen.empresa}" if almacen.empresa else " - Sin empresa"
            html_content += f"<li>{almacen.descripcion} (ID: {almacen.id}) {estado}{empresa_info}</li>"
        html_content += "</ul>"
    else:
        html_content += "<p>❌ No hay almacenes</p>"
    
    # Verificar facturadores
    facturadores = Facturador.objects.all()
    facturadores_activos = Facturador.objects.filter(activo=True)
    html_content += f"<h2>Facturadores (Total: {facturadores.count()}, Activos: {facturadores_activos.count()})</h2>"
    
    if facturadores.exists():
        html_content += "<ul>"
        for facturador in facturadores:
            estado = "✅ Activo" if facturador.activo else "❌ Inactivo"
            empresa_info = f" - Empresa: {facturador.empresa}" if facturador.empresa else " - Sin empresa"
            html_content += f"<li>{facturador.nombres} (ID: {facturador.id}) {estado}{empresa_info}</li>"
        html_content += "</ul>"
    else:
        html_content += "<p>❌ No hay facturadores</p>"
    
    # Crear datos si no existen
    if request.GET.get('create_data') == '1':
        html_content += "<h2>Creando Datos de Prueba</h2>"
        
        empresa_principal = empresas.first() if empresas.exists() else None
        
        # Crear almacenes
        if not almacenes_activos.exists():
            almacen1, created1 = Almacen.objects.get_or_create(
                descripcion="Almacén Principal",
                defaults={'activo': True, 'empresa': empresa_principal}
            )
            almacen2, created2 = Almacen.objects.get_or_create(
                descripcion="Almacén Secundario",
                defaults={'activo': True, 'empresa': empresa_principal}
            )
            if created1 or created2:
                html_content += "<p>✅ Almacenes creados</p>"
        
        # Crear facturadores
        if not facturadores_activos.exists():
            try:
                facturador1, created1 = Facturador.objects.get_or_create(
                    correo="facturador1@test.com",
                    defaults={
                        'nombres': "Juan Pérez",
                        'activo': True,
                        'empresa': empresa_principal,
                        'telefono': '0999999999'
                    }
                )
                if created1:
                    facturador1.set_password("123456")
                    facturador1.save()
                
                facturador2, created2 = Facturador.objects.get_or_create(
                    correo="facturador2@test.com",
                    defaults={
                        'nombres': "María López",
                        'activo': True,
                        'empresa': empresa_principal,
                        'telefono': '0988888888'
                    }
                )
                if created2:
                    facturador2.set_password("123456")
                    facturador2.save()
                    
                if created1 or created2:
                    html_content += "<p>✅ Facturadores creados</p>"
            except Exception as e:
                html_content += f"<p>❌ Error creando facturadores: {e}</p>"
        
        html_content += '<p><a href="?">Recargar sin crear datos</a></p>'
    else:
        html_content += '<p><a href="?create_data=1">Crear datos de prueba</a></p>'
    
    html_content += """
    <hr>
    <p><a href="/inventario/proformas/emitir/">Ir a Emisión de Proforma</a></p>
    </body>
    </html>
    """
    
    return HttpResponse(html_content)
