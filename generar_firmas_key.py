#!/usr/bin/env python3
"""
Script para generar una clave Fernet válida para FIRMAS_KEY
Úsala en Heroku: heroku config:set FIRMAS_KEY="la_clave_generada"
"""

from cryptography.fernet import Fernet

# Generar clave Fernet válida
key = Fernet.generate_key()
key_str = key.decode('utf-8')

print("=" * 80)
print("🔐 CLAVE FERNET GENERADA:")
print("=" * 80)
print(key_str)
print("=" * 80)
print("\n📋 COPIA Y EJECUTA ESTE COMANDO EN HEROKU:\n")
print(f'heroku config:set FIRMAS_KEY="{key_str}"')
print("\n" + "=" * 80)
print("✅ Esta clave es segura y lista para usar en producción")
print("⚠️  GUÁRDALA EN UN LUGAR SEGURO - No la compartas")
print("=" * 80)
