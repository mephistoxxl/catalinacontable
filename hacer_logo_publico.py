#!/usr/bin/env python
"""Script para hacer público el logo en S3"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

import boto3
from django.conf import settings

# Configurar cliente S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME
)

bucket_name = settings.AWS_STORAGE_BUCKET_NAME
logo_key = 'logos/Logo PNG - Catalina.png'

print(f"🔧 Haciendo público el archivo: {logo_key}")
print(f"📦 Bucket: {bucket_name}")

try:
    # Hacer el archivo público
    s3_client.put_object_acl(
        Bucket=bucket_name,
        Key=logo_key,
        ACL='public-read'
    )
    
    print(f"✅ ¡Archivo ahora es público!")
    
    # Generar URL pública
    url = f"https://{bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{logo_key.replace(' ', '%20')}"
    print(f"🌐 URL pública: {url}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n💡 Alternativa: Ejecuta este comando en tu terminal AWS CLI:")
    print(f'aws s3api put-object-acl --bucket {bucket_name} --key "{logo_key}" --acl public-read')
