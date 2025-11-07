# Política IAM: Bloqueo de Acceso Público para el bucket de medios

Para cumplir con el requerimiento de "Block Public Access" en el bucket de archivos de Catalina Facturador, habilitamos los cuatro flags de bloqueo a nivel de bucket y registramos la siguiente política IAM de referencia. Esta política impide operaciones que intenten exponer objetos de forma pública y refuerza el uso de cifrado en reposo mediante KMS.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyPublicAclChanges",
      "Effect": "Deny",
      "Principal": "*",
      "Action": [
        "s3:PutBucketAcl",
        "s3:PutObjectAcl",
        "s3:CreateBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${AWS_STORAGE_BUCKET_NAME}",
        "arn:aws:s3:::${AWS_STORAGE_BUCKET_NAME}/*"
      ],
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": [
            "public-read",
            "public-read-write",
            "authenticated-read"
          ]
        }
      }
    },
    {
      "Sid": "RequireEncryptedUploads",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${AWS_STORAGE_BUCKET_NAME}/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": [
            "aws:kms",
            "AES256"
          ]
        }
      }
    },
    {
      "Sid": "EnforceTLS",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::${AWS_STORAGE_BUCKET_NAME}",
        "arn:aws:s3:::${AWS_STORAGE_BUCKET_NAME}/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```

> **Nota:** Sustituye `${AWS_STORAGE_BUCKET_NAME}` por el nombre real del bucket. Mantener esta política adjunta al bucket junto con el "Block Public Access" habilitado garantiza que ningún objeto quede expuesto públicamente y que todas las cargas se guarden cifradas con SSE (KMS o AES256).
