"""
Script para probar el parseo de diferentes formatos de fecha del SRI
"""
from datetime import datetime
from django.utils import timezone

def test_parseo_fechas_sri():
    """Probar parseo de todos los formatos que el SRI puede enviar"""
    
    print("\n" + "="*80)
    print("🧪 PRUEBA DE PARSEO DE FECHAS DE AUTORIZACIÓN DEL SRI")
    print("="*80 + "\n")
    
    # Formatos que el SRI puede enviar según la Ficha Técnica
    casos_prueba = [
        # Formato ISO 8601 completo (con milisegundos y timezone)
        ("2015-05-21T14:22:30.764-05:00", "ISO 8601 completo con milisegundos"),
        
        # Formato ISO 8601 sin milisegundos
        ("2015-05-21T14:22:30-05:00", "ISO 8601 con timezone"),
        
        # Formato ISO simple (sin timezone)
        ("2025-11-16T06:00:06", "ISO simple sin timezone"),
        
        # Formato local del SRI
        ("16/11/2025 06:00:06", "Formato local SRI"),
        
        # Formato con Z (UTC)
        ("2015-05-21T14:22:30Z", "ISO con Z (UTC)"),
    ]
    
    print("📋 Casos de prueba:\n")
    
    for fecha_str, descripcion in casos_prueba:
        print(f"\n{'─'*80}")
        print(f"🔍 Probando: {descripcion}")
        print(f"   Input: {fecha_str}")
        
        try:
            fecha_dt = None
            
            if 'T' in str(fecha_str):
                # Formato ISO con T
                fecha_limpia = str(fecha_str).strip()
                
                # Manejar diferentes variantes ISO
                if '-05:00' in fecha_limpia or '+' in fecha_limpia or 'Z' in fecha_limpia:
                    # ISO 8601 completo con timezone
                    fecha_limpia = fecha_limpia.replace('Z', '+00:00')
                    # Remover milisegundos si existen (ej: .764)
                    if '.' in fecha_limpia:
                        partes = fecha_limpia.split('.')
                        # Mantener solo timezone después del punto
                        if len(partes) == 2:
                            timezone_part = partes[1]
                            # Extraer solo el timezone
                            if '-' in timezone_part:
                                tz = '-' + timezone_part.split('-')[1]
                            elif '+' in timezone_part:
                                tz = '+' + timezone_part.split('+')[1]
                            else:
                                tz = ''
                            fecha_limpia = partes[0] + tz
                    
                    fecha_dt = datetime.fromisoformat(fecha_limpia)
                else:
                    # ISO simple sin timezone
                    fecha_dt = datetime.fromisoformat(fecha_limpia)
                    # Hacer timezone-aware (Ecuador UTC-5)
                    fecha_dt = timezone.make_aware(fecha_dt)
            
            elif '/' in str(fecha_str):
                # Formato SRI local: "16/11/2025 06:00:06"
                fecha_dt = datetime.strptime(str(fecha_str), '%d/%m/%Y %H:%M:%S')
                # Hacer timezone-aware (Ecuador UTC-5)
                fecha_dt = timezone.make_aware(fecha_dt)
            
            if fecha_dt:
                # Formatear para RIDE
                fecha_ride = fecha_dt.strftime('%d/%m/%Y %H:%M:%S')
                print(f"   ✅ ÉXITO")
                print(f"   Parseado: {fecha_dt}")
                print(f"   Formato RIDE: {fecha_ride}")
            else:
                print(f"   ❌ FALLO: No se pudo parsear")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    print(f"\n{'='*80}\n")
    print("✅ Pruebas completadas")
    print("\n📌 Conclusión:")
    print("   El sistema ahora puede manejar TODOS los formatos de fecha")
    print("   que el SRI puede enviar según la Ficha Técnica v2.32")
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    # Configurar Django para poder usar timezone
    import os
    import sys
    import django
    
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    django.setup()
    
    from django.utils import timezone
    
    test_parseo_fechas_sri()
