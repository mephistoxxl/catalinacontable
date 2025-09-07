#!/usr/bin/env python
import os, json
from decimal import Decimal
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE','sistema.settings')
import django
django.setup()

from inventario.models import Banco, Empresa

BACKUP_FILE = 'backup_sqlite_data.json'

def parse_date(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%d','%Y-%m-%dT%H:%M:%S.%fZ','%Y-%m-%dT%H:%M:%SZ'):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None

def migrar_bancos():
    if not os.path.exists(BACKUP_FILE):
        print('❌ No existe backup_sqlite_data.json')
        return
    empresa = Empresa.objects.first()
    if not empresa:
        print('❌ No hay Empresa cargada')
        return
    with open(BACKUP_FILE,'r',encoding='utf-8') as f:
        data = json.load(f)
    bancos_data = [x for x in data if x.get('model')=='inventario.banco']
    print(f'🔎 Bancos en backup: {len(bancos_data)}')
    creados=0; saltados=0
    for item in bancos_data:
        flds = item.get('fields', {})
        numero_cuenta = flds.get('numero_cuenta')
        if not numero_cuenta:
            continue
        if Banco.objects.filter(numero_cuenta=numero_cuenta).exists():
            saltados += 1
            continue
        try:
            Banco.objects.create(
                empresa=empresa,
                banco=flds.get('banco','Banco'),
                titular=flds.get('titular','Titular'),
                numero_cuenta=numero_cuenta,
                activo=flds.get('activo',True),
                saldo_inicial=Decimal(str(flds.get('saldo_inicial','0.00'))),
                tipo_cuenta=flds.get('tipo_cuenta','AHORROS'),
                fecha_apertura=parse_date(flds.get('fecha_apertura')),
                telefono=flds.get('telefono',''),
                secuencial_cheque=flds.get('secuencial_cheque',1),
                observaciones=flds.get('observaciones','')
            )
            creados += 1
            print(f'✅ Banco migrado {numero_cuenta}')
        except Exception as e:
            print(f'❌ Error banco {numero_cuenta}: {e}')
    print(f'➡️ Bancos creados: {creados} | saltados: {saltados}')

if __name__ == '__main__':
    migrar_bancos()