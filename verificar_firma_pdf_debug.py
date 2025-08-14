#!/usr/bin/env python3
"""
Script para verificar y debuggear firmas PDF
"""

import os
import sys
import logging
from pathlib import Path

def verificar_firma_pdf(pdf_path):
    """
    Verifica si un PDF tiene una firma válida
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        return False
    
    # Verificar tamaño
    original_size = os.path.getsize(pdf_path)
    print(f"📄 Tamaño del archivo: {original_size} bytes")
    
    if original_size == 0:
        print("❌ Archivo vacío")
        return False
    
    # Verificar si contiene datos de firma
    with open(pdf_path, 'rb') as f:
        content = f.read()
    
    # Buscar indicadores de firma PDF
    has_signature = b'/Type /Sig' in content or b'/Sig' in content
    has_acroform = b'/AcroForm' in content
    has_cert = b'/Cert' in content
    
    print(f"🔍 Contiene firma PDF: {'✅' if has_signature else '❌'}")
    print(f"🔍 Contiene AcroForm: {'✅' if has_acroform else '❌'}")
    print(f"🔍 Contiene certificado: {'✅' if has_cert else '❌'}")
    
    # Verificar incremento de tamaño
    if original_size > 1000:  # Tamaño mínimo razonable
        print("✅ Tamaño suficiente para contener firma")
    else:
        print("⚠️ Tamaño muy pequeño, podría no tener firma")
    
    return has_signature or has_acroform

def listar_pdfs_firmados():
    """
    Lista todos los PDFs firmados en la carpeta media
    """
    base_path = Path("media/facturas_pdf")
    if not base_path.exists():
        print("❌ Carpeta media/facturas_pdf no encontrada")
        return
    
    print("📁 PDFs encontrados:")
    for pdf_file in base_path.glob("*.pdf"):
        print(f"\n📄 {pdf_file.name}")
        verificar_firma_pdf(str(pdf_file))

def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Verificando: {pdf_path}")
        verificar_firma_pdf(pdf_path)
    else:
        print("Verificando todos los PDFs firmados...")
        listar_pdfs_firmados()

if __name__ == "__main__":
    main()