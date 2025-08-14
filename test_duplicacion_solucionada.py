#!/usr/bin/env python3
"""
Script de verificación para confirmar que la duplicación de autorizar_documento_sri fue solucionada
"""

import os
import sys
import re

def verificar_duplicaciones():
    """Verificar que no existan definiciones duplicadas"""
    print("🔍 VERIFICANDO DUPLICACIONES RESUELTAS")
    print("=" * 50)
    
    # 1. Verificar views.py
    views_file = r"c:\Users\CORE I7\Desktop\sisfact\inventario\views.py"
    print(f"\n📄 Verificando {views_file}")
    
    if os.path.exists(views_file):
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Buscar definiciones de autorizar_documento_sri
        pattern = r'def autorizar_documento_sri\('
        matches = re.findall(pattern, content)
        
        print(f"   Definiciones encontradas: {len(matches)}")
        if len(matches) == 1:
            print("   ✅ Correcto: Solo una definición de autorizar_documento_sri")
        else:
            print(f"   ❌ Error: {len(matches)} definiciones encontradas")
            return False
    else:
        print("   ❌ Archivo no encontrado")
        return False
    
    # 2. Verificar urls.py
    urls_file = r"c:\Users\CORE I7\Desktop\sisfact\inventario\urls.py"
    print(f"\n🔗 Verificando {urls_file}")
    
    if os.path.exists(urls_file):
        with open(urls_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Buscar URLs de autorizar_documento_sri
        pattern = r'autorizar_documento_sri'
        matches = re.findall(pattern, content)
        
        print(f"   Referencias encontradas: {len(matches)}")
        if len(matches) == 1:
            print("   ✅ Correcto: Solo una URL definida")
        else:
            print(f"   ⚠️  Múltiples referencias: {len(matches)} (normal si hay comentarios)")
            
        # Verificar que use la URL correcta
        if 'sri/autorizar/' in content:
            print("   ✅ URL correcta encontrada: sri/autorizar/")
        else:
            print("   ❌ URL correcta no encontrada")
            return False
    else:
        print("   ❌ Archivo no encontrado")
        return False
    
    # 3. Verificar template
    template_file = r"c:\Users\CORE I7\Desktop\sisfact\inventario\templates\inventario\factura\listarFacturas.html"
    print(f"\n📋 Verificando {template_file}")
    
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Buscar funciones JavaScript duplicadas
        pattern = r'function autorizarDocumento\('
        matches = re.findall(pattern, content)
        
        print(f"   Funciones JavaScript encontradas: {len(matches)}")
        if len(matches) == 1:
            print("   ✅ Correcto: Solo una función autorizarDocumento")
        else:
            print(f"   ❌ Error: {len(matches)} funciones encontradas")
            return False
            
        # Verificar que use la URL correcta
        if '/inventario/sri/autorizar/' in content:
            print("   ✅ URL correcta en JavaScript: /inventario/sri/autorizar/")
        else:
            print("   ❌ URL correcta no encontrada en JavaScript")
            return False
            
        # Verificar que no use la URL antigua
        if '/inventario/autorizar-documento/' in content:
            print("   ❌ URL antigua encontrada en JavaScript")
            return False
        else:
            print("   ✅ URL antigua eliminada correctamente")
    else:
        print("   ❌ Archivo no encontrado")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 ¡VERIFICACIÓN EXITOSA!")
    print("✅ Todas las duplicaciones han sido resueltas correctamente")
    print("✅ Solo existe una definición de autorizar_documento_sri")
    print("✅ URLs actualizadas correctamente")
    print("✅ JavaScript corregido")
    return True

if __name__ == "__main__":
    try:
        verificar_duplicaciones()
    except Exception as e:
        print(f"\n❌ Error durante la verificación: {e}")
        sys.exit(1)
