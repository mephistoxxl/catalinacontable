# -*- coding: utf-8 -*-
"""
Script simple para ver fechas de factura
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
os.environ.setdefault('DATABASE_URL', 'sqlite:///db.sqlite3')

import django
django.setup()

from inventario.models import Factura

facturas = Factura.objects.filter(estado='AUTORIZADO').order_by('-id')[:3]

for f in facturas:
    print(f"Factura {f.secuencia}:")
    print(f"  Fecha emisión: {f.fecha_emision}")
    print(f"  Fecha autorización: {f.fecha_autorizacion}")
    print(f"  ¿Son iguales?: {f.fecha_emision == f.fecha_autorizacion}")
    print()
