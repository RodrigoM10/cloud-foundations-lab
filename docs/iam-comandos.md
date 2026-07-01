# Comandos útiles de IAM

Endpoint local: `http://localhost:4566` · cuenta simulada: `000000000000`

## Setup

`awslocal` es un wrapper de `aws` que apunta a LocalStack. Viene instalado con
`pip install -r requirements.txt` (paquete `awscli-local`).

```bash
# Verificar que el comando está disponible
awslocal --version

# Verificar que LocalStack responde
awslocal sts get-caller-identity
```

---

## Explorar lo que hay

```bash
# Usuarios
awslocal iam list-users

# Grupos
awslocal iam list-groups

# Roles
awslocal iam list-roles

# Políticas creadas en el lab (scope=Local = no son las managed de AWS)
awslocal iam list-policies --scope Local
```

---

## Usuarios

```bash
# Crear usuario
awslocal iam create-user --user-name ana

# Ver detalle
awslocal iam get-user --user-name ana

# Listar grupos a los que pertenece
awslocal iam list-groups-for-user --user-name lab-user

# Listar políticas adjuntas al usuario
awslocal iam list-attached-user-policies --user-name lab-user

# Listar políticas inline del usuario
awslocal iam list-user-policies --user-name lab-user

# Crear access key (llave de larga duración — observar el riesgo)
awslocal iam create-access-key --user-name lab-user

# Ver todas las access keys del usuario
awslocal iam list-access-keys --user-name lab-user

# Desactivar una key sin borrarla
awslocal iam update-access-key \
  --user-name lab-user \
  --access-key-id <KeyId> \
  --status Inactive

# Borrar la key
awslocal iam delete-access-key \
  --user-name lab-user \
  --access-key-id <KeyId>
```

---

## Grupos y políticas administradas

```bash
# Crear grupo
awslocal iam create-group --group-name bigdata-admin

# Agregar usuario al grupo
awslocal iam add-user-to-group --group-name bigdata-admin --user-name ana

# Ver miembros del grupo
awslocal iam get-group --group-name bigdata-read

# Adjuntar política administrada al grupo
awslocal iam attach-group-policy \
  --group-name bigdata-admin \
  --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab

# Ver políticas adjuntas a un grupo
awslocal iam list-attached-group-policies --group-name bigdata-read

# Desadjuntar política
awslocal iam detach-group-policy \
  --group-name bigdata-read \
  --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab

# Sacar usuario del grupo
awslocal iam remove-user-from-group --group-name bigdata-admin --user-name ana
```

---

## Políticas

```bash
# Ver el documento JSON de una política (versión activa)
awslocal iam get-policy --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab

awslocal iam get-policy-version \
  --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab \
  --version-id v1

# Crear política nueva desde archivo
awslocal iam create-policy \
  --policy-name S3AdminLab \
  --policy-document file://iam/s3_admin_policy.json

# Política inline sobre un usuario (no necesita ARN, vive dentro del usuario)
awslocal iam put-user-policy \
  --user-name lab-user \
  --policy-name DenyDelete \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"s3:DeleteObject","Resource":"*"}]}'

# Leer política inline
awslocal iam get-user-policy --user-name lab-user --policy-name DenyDelete

# Borrar política inline
awslocal iam delete-user-policy --user-name lab-user --policy-name DenyDelete
```

---

## Roles

```bash
# Ver el rol creado en el lab
awslocal iam get-role --role-name app-role

# Ver la trust policy (quién puede asumir el rol)
awslocal iam get-role --role-name app-role \
  --query "Role.AssumeRolePolicyDocument"

# Ver la inline policy del rol
awslocal iam get-role-policy --role-name app-role --policy-name InlineS3Read

# Listar todas las inline policies del rol
awslocal iam list-role-policies --role-name app-role

# Crear un segundo rol — solo lambda puede asumirlo
awslocal iam create-role \
  --role-name lambda-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"lambda.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

# Adjuntar inline policy al nuevo rol
awslocal iam put-role-policy \
  --role-name lambda-role \
  --policy-name InlineS3Read \
  --policy-document file://iam/s3_read_policy.json
```

---

## STS — credenciales temporales

```bash
# Ver quién sos ahora
awslocal sts get-caller-identity

# Asumir el rol y guardar credenciales
CREDS=$(awslocal sts assume-role \
  --role-arn arn:aws:iam::000000000000:role/app-role \
  --role-session-name mi-sesion \
  --duration-seconds 900 \
  --query "Credentials" \
  --output json)

echo $CREDS

# Extraer y exportar las credenciales temporales
export AWS_ACCESS_KEY_ID=$(echo $CREDS | python3 -c "import json,sys; print(json.load(sys.stdin)['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | python3 -c "import json,sys; print(json.load(sys.stdin)['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(echo $CREDS | python3 -c "import json,sys; print(json.load(sys.stdin)['SessionToken'])")

# Verificar que el caller ahora es el rol asumido
awslocal sts get-caller-identity

# Volver a las credenciales originales
unset AWS_SESSION_TOKEN
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

---

## S3 con credenciales temporales

```bash
# (después de exportar las credenciales del paso anterior)

# Listar objetos
awslocal s3 ls s3://course-data-raw --recursive

# Leer un objeto
awslocal s3 cp s3://course-data-raw/sample/hello.txt -

# Intentar escribir (debería fallar en AWS real — en LocalStack Community pasa igual)
awslocal s3 cp data/processed/push_events.json s3://course-data-raw/test/prueba.json

# Intentar borrar (debería fallar si hay un Deny — no se enforcea en Community)
awslocal s3 cp data/processed/push_events.json s3://course-data-raw/test/prueba.json
```

> **Nota**: en LocalStack Community el `Deny` no bloquea las operaciones.
> Para ver el enforcement real usá LocalStack Pro o una cuenta AWS.

---

## Limpieza

```bash
# Borrar inline policy del rol
awslocal iam delete-role-policy --role-name app-role --policy-name InlineS3Read

# Borrar rol (primero hay que desadjuntar todo)
awslocal iam delete-role --role-name app-role

# Sacar usuario del grupo antes de borrarlo
awslocal iam remove-user-from-group --group-name bigdata-read --user-name lab-user

# Desadjuntar política del grupo
awslocal iam detach-group-policy \
  --group-name bigdata-read \
  --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab

# Borrar grupo
awslocal iam delete-group --group-name bigdata-read

# Borrar access key antes de borrar el usuario
awslocal iam delete-access-key --user-name lab-user --access-key-id <KeyId>

# Borrar usuario
awslocal iam delete-user --user-name lab-user

# Borrar política
awslocal iam delete-policy --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab

# Borrar bucket S3
awslocal s3 rb s3://course-data-raw --force
```

---

## Equivalentes AWS

| Comando local (`awslocal`)          | En consola AWS                                   |
|--------------------------------------|--------------------------------------------------|
| `iam list-users`                    | IAM → Users                                      |
| `iam get-policy-version`            | IAM → Policies → ver JSON de la versión activa  |
| `iam list-attached-group-policies`  | IAM → Groups → Permissions tab                  |
| `sts assume-role`                   | No hay equivalente visual — es API/CLI/SDK       |
| `sts get-caller-identity`           | IAM → arriba derecha: nombre del usuario/rol     |
| Inline policy                       | IAM → entity → Add inline policy                |
| Managed policy                      | IAM → Policies → crear y adjuntar               |
| `AWS_SESSION_TOKEN` en el shell     | Credenciales temporales en `~/.aws/credentials` |
