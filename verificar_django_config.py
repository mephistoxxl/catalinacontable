#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar la configuración de Django sin importar Django directamente
"""

import os
import sqlite3
import json

def verificar_configuracion_sqlite():
    """Verifica directamente en la base de datos SQLite"""
    
    print("=== VERIFICACIÓN DIRECTA DE BASE DE DATOS ===\n")
    
    # Buscar archivo de base de datos
    db_files = [f for f in os.listdir('.') if f.endswith('.sqlite3') or f.endswith('.db')]
    
    if not db_files:
        print("❌ No se encontró base de datos SQLite")
        return False
    
    print(f"✅ Base de datos encontrada: {db_files[0]}")
    
    try:
        conn = sqlite3.connect(db_files[0])
        cursor = conn.cursor()
        
        # Verificar tabla inventario_opciones
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario_opciones'")
        if not cursor.fetchone():
            print("❌ No existe la tabla inventario_opciones")
            return False
            
        print("✅ Tabla inventario_opciones encontrada")
        
        # Verificar registros
        cursor.execute("SELECT id, firma_electronica, password_firma, fecha_caducidad_firma FROM inventario_opciones")
        registros = cursor.fetchall()
        
        if not registros:
            print("❌ No hay registros en Opciones")
            print("   - Debes crear una configuración en el admin")
            return False
            
        print(f"✅ {len(registros)} registros encontrados")
        
        for registro in registros:
            id_reg, firma_electronica, password_firma, fecha_caducidad = registro
            print(f"\nRegistro ID: {id_reg}")
            print(f"   Firma electrónica: {'✅ Sí' if firma_electronica else '❌ No'}")
            print(f"   Contraseña: {'✅ Sí' if password_firma else '❌ No'}")
            print(f"   Fecha caducidad: {fecha_caducidad}")
            
            # Verificar si el archivo existe
            if firma_electronica:
                firma_path = os.path.join('media', firma_electronica)
                if os.path.exists(firma_path):
                    print(f"   Archivo: ✅ Existe")
                else:
                    print(f"   Archivo: ❌ No existe ({firma_path})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error al leer base de datos: {e}")
        return False

def solucionar_cgi_error():
    """Proporciona soluciones para el error de módulo cgi"""
    
    print("\n=== SOLUCIÓN AL ERROR DE MÓDULO CGI ===\n")
    
    print("El error 'ModuleNotFoundError: No module named 'cgi'' ocurre porque:")
    print("- Estás usando Python 3.13 que eliminó el módulo cgi")
    print("- Django necesita este módulo para procesar formularios multipart")
    
    print("\nSOLUCIONES:")
    print("1. Instalar Django 4.2 o superior:")
    print("   pip install \"Django>=4.2\"")
    
    print("\n2. O instalar Python 3.11 o 3.12:")
    print("   - Descarga desde python.org")
    print("   - Reinstala tus paquetes")
    
    print("\n3. O instalar el módulo legacy-cgi:")
    print("   pip install legacy-cgi")

if __name__ == "__main__":
    verificar_configuracion_sqlite()
    solucionar_cgi_error()