#!/bin/bash
# Lab 05 — user-data: bootstrap de una instancia que sirve contenido bajado de S3.
#
# Cierre del círculo IAM → EC2 → S3:
#   - La instancia tiene asociado el instance profile "app-instance-profile"
#   - Ese profile expone el rol "app-role" (creado en lab-04) con s3:GetObject
#   - aws s3 cp usa esas credenciales temporales vía IMDSv2 — sin claves en disco
#
# En AWS real este script corre la primera vez que arranca la instancia.
# En LocalStack Community se almacena pero NO se ejecuta (EC2 es mock).

set -euo pipefail

# 1. Instalar servidor web (Amazon Linux 2)
yum update -y
yum install -y nginx awscli
systemctl enable nginx
systemctl start nginx

# 2. Bajar contenido desde S3 usando el rol de instancia (sin access keys)
BUCKET="course-data-raw"
KEY="sample/hello.txt"
aws s3 cp "s3://${BUCKET}/${KEY}" /tmp/from-s3.txt

# 3. Publicar la página servida desde la instancia
cat > /usr/share/nginx/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head><title>Lab 05 — Compute + IAM + S3</title></head>
<body>
  <h1>Servido por EC2</h1>
  <p>Instance ID: $(curl -s http://169.254.169.254/latest/meta-data/instance-id)</p>
  <p>Contenido bajado de s3://${BUCKET}/${KEY}:</p>
  <pre>$(cat /tmp/from-s3.txt)</pre>
</body>
</html>
HTML

# 4. Verificar que nginx responde local
curl -sf http://localhost/ > /dev/null && echo "OK: nginx respondiendo" || echo "FAIL: nginx no responde"
