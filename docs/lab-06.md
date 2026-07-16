# Lab 06 — Almacenamiento: S3 como data lake del módulo

Cierra el arco **IAM (lab 04) → EC2 (lab 05) → S3 (hoy)**. La data que veníamos cargando localmente sube al bucket que vamos a usar el resto del módulo. El acceso es por el rol de instancia — sin claves.

> **LocalStack Community vs AWS real**
> S3 en Community es **real**: bucket policies se evalúan, versioning crea versiones reales, presigned URLs funcionan, BPA bloquea acceso público. Lo único parcial son las transiciones de lifecycle (Glacier) y replication cross-region — para eso, AWS real o Learner Lab.

---

## Por qué bucket dedicado y no expandir `course-data-raw`

- `course-data-raw` quedó como **bucket de demo** del lab 04 (IAM)
- `course-data-lake` es la **fuente de verdad durable** del curso: data real de Olist + GitHub Archive, con versioning y bucket policy desde el día uno
- Clase 16 (Analytics) va a consultar directo desde este bucket — ya queda preparado

---

## Prerequisitos

- Branch `lab-06-tuNombre` desde main
- Lab 04 corrido (necesitamos `app-role` existente): `python scripts/iam_demo.py`
- Servicios activos: `docker compose up -d`
- `awslocal --version` responde

```bash
# Verificar dependencias
awslocal iam get-role --role-name app-role --query "Role.Arn"
awslocal s3 ls   # debería responder vacío o con los buckets de labs anteriores
```

---

## Paso 1 — Crear el bucket cerrado por defecto

```bash
awslocal s3 mb s3://course-data-lake

# Block Public Access — 4 flags ON
awslocal s3api put-public-access-block \
  --bucket course-data-lake \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Encryption por defecto (SSE-S3)
awslocal s3api put-bucket-encryption \
  --bucket course-data-lake \
  --server-side-encryption-configuration '{
    "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
  }'

# Verificar
awslocal s3api get-public-access-block --bucket course-data-lake
awslocal s3api get-bucket-encryption --bucket course-data-lake
```

> S3 hoy: `Block Public Access` y `default encryption` vienen ON por default en buckets nuevos (cambio relativamente reciente de AWS). El paso queda igual para que se vea explícito en el lab.

---

## Paso 2 — Versioning desde el inicio

```bash
awslocal s3api put-bucket-versioning \
  --bucket course-data-lake \
  --versioning-configuration Status=Enabled

awslocal s3api get-bucket-versioning --bucket course-data-lake
```

Activarlo **antes** de subir data — sino las primeras versiones nunca existen.

---

## Paso 3 — Subir el dataset del curso

```bash
# Olist a raw/olist/
awslocal s3 sync data/raw/olist/ s3://course-data-lake/raw/olist/

# GitHub Archive a raw/events/
awslocal s3 sync data/raw/events/ s3://course-data-lake/raw/events/

# Processed
awslocal s3 sync data/processed/ s3://course-data-lake/processed/

# Verificar
awslocal s3 ls s3://course-data-lake --recursive | head
```

`s3 sync` es idempotente — solo sube lo que cambió.

---

## Paso 4 — Demostrar versioning

Sobrescribimos `orders.csv` agregando una línea, mostramos versiones:

```bash
# Bajar versión actual
awslocal s3 cp s3://course-data-lake/raw/olist/orders.csv /tmp/orders.csv

# Agregar una "venta nueva"
echo "NEW_ORDER_2026_FICTICIO,99999,delivered,2026-06-18,2026-06-19,2026-06-25,," >> /tmp/orders.csv

# Subir como nueva versión
awslocal s3 cp /tmp/orders.csv s3://course-data-lake/raw/olist/orders.csv

# Listar versiones
awslocal s3api list-object-versions \
  --bucket course-data-lake \
  --prefix raw/olist/orders.csv \
  --query "Versions[].{Id:VersionId,Size:Size,Latest:IsLatest}"
```

La versión anterior NO se borró — sigue accesible por su `VersionId` y sigue cobrando storage.

---

## Paso 5 — Bucket policy: solo `app-role` puede leer

```bash
# El JSON molde está en s3/bucket_policy.json (Principal=app-role, scope=raw/* y processed/*)
awslocal s3api put-bucket-policy \
  --bucket course-data-lake \
  --policy file://s3/bucket_policy.json

# Verificar
awslocal s3api get-bucket-policy --bucket course-data-lake --query Policy --output text | python3 -m json.tool
```

**Importante**: esta es **resource-based policy** (vive en el bucket). Es complementaria a la **identity-based policy** del rol que armamos en lab 04 (vive en la identidad). Para que `GetObject` funcione hace falta que **ambas** permitan — o que al menos una permita y la otra no niegue. Cualquier `Deny` explícito gana sobre cualquier `Allow`.

---

## Paso 6 — Cierre del círculo: bajar como `app-role`

```bash
# Asumir el rol (en AWS real esto lo hace la EC2 automáticamente vía IMDSv2)
CREDS=$(awslocal sts assume-role \
  --role-arn arn:aws:iam::000000000000:role/app-role \
  --role-session-name lab06-download \
  --duration-seconds 900 \
  --query Credentials --output json)

export AWS_ACCESS_KEY_ID=$(echo $CREDS | python3 -c "import json,sys;print(json.load(sys.stdin)['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | python3 -c "import json,sys;print(json.load(sys.stdin)['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(echo $CREDS | python3 -c "import json,sys;print(json.load(sys.stdin)['SessionToken'])")

# Bajar un objeto con esas credenciales temporales
awslocal s3 cp s3://course-data-lake/raw/olist/customers.csv /tmp/customers.csv
head -3 /tmp/customers.csv

# Volver a credenciales originales
unset AWS_SESSION_TOKEN
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

En AWS real, este paso ocurre **dentro** de la EC2:
- El rol `app-role` está adjuntado como instance profile (lab 05)
- La AWS CLI dentro de la instancia obtiene credenciales temporales automáticamente vía IMDSv2
- `aws s3 cp` funciona sin que el alumno toque credenciales

---

## Paso 7 — Presigned URL: acceso temporario sin asumir rol

```bash
# URL que expira en 5 minutos
awslocal s3 presign s3://course-data-lake/processed/push_events.json --expires-in 300

# La URL contiene la firma. Cualquiera con ella puede descargar — durante 5 min
```

Útil para: dar acceso a un cliente externo sin crear IAM users; descargas de archivos privados desde un browser; APIs públicas que protegen su backend.

---

## Paso 8 — Demo automatizada

El script `scripts/s3_demo.py` hace los pasos 1–7 en secuencia:

```bash
python scripts/s3_demo.py
```

Es idempotente — segunda corrida no rompe, agrega versión nueva del archivo demo.

---

## Paso 9 — Limpieza parcial

**Importante: NO borrar el bucket.** `course-data-lake` queda como base para futuras clases (16 Analytics, 17 Cloud Platform Lab).

Sí conviene limpiar las versiones de prueba para no acumular:

```bash
# Listar TODAS las versiones (objetos + delete markers)
awslocal s3api list-object-versions \
  --bucket course-data-lake \
  --prefix raw/olist/orders.csv \
  --query "Versions[?!IsLatest].{Key:Key,VersionId:VersionId}"

# Borrar una versión específica (reemplazar VERSION_ID)
awslocal s3api delete-object \
  --bucket course-data-lake \
  --key raw/olist/orders.csv \
  --version-id <VERSION_ID>
```

---

## Paso 10 — Documentar en `decisions.md`

```
### 007 - course-data-lake como fuente durable del módulo

Decision: separar 'course-data-raw' (demo IAM del lab 04) de 'course-data-lake' (fuente
de verdad de datos reales del curso). El segundo nace con BPA, encryption y versioning
ON, y bucket policy que restringe lectura al instance role de la app.

Contexto: necesitamos un lugar durable para Olist + GitHub Archive que sobreviva al
ciclo de vida de cada lab. Mezclar con el bucket de demo IAM enmascara el propósito
de cada uno.

Tradeoff: dos buckets en lugar de uno. A favor: separación clara de intención,
escalable a futuras clases (Analytics consume directo desde la lake).

Resultado: course-data-lake con versioning + BPA + SSE + bucket policy desde el día 1.
```

---

## Checkpoint

Al finalizar deberías poder mostrar:

- [ ] Bucket `course-data-lake` con BPA + encryption + versioning ON
- [ ] Olist + GitHub Archive + processed cargados en sus prefijos correctos
- [ ] `orders.csv` con al menos 2 versiones listables
- [ ] Bucket policy aplicada con `app-role` como Principal
- [ ] GetObject funcionando con credenciales asumidas vía `sts:AssumeRole`
- [ ] Presigned URL generada y verificada
- [ ] Decisión 007 en `decisions.md`

---

## Para llevar: LocalStack Community vs AWS real

| Acción | LocalStack Community | AWS real |
|---|---|---|
| `mb` (make bucket), upload, ls | ✅ | ✅ |
| Block Public Access, encryption default | ✅ | ✅ |
| Versioning (versiones reales con `VersionId`) | ✅ | ✅ |
| `put-bucket-policy` y evaluación de acceso | ✅ | ✅ |
| Presigned URLs (funcionan de verdad) | ✅ | ✅ |
| Lifecycle (transición a Glacier por edad) | ⚠️ parcial | ✅ |
| Replication cross-region | ⚠️ parcial | ✅ |
| Cobro por GB-mes + requests | $0 | $$$ |

S3 es uno de los servicios donde LocalStack Community se acerca más a AWS real. Para el flujo del lab, el comportamiento es indistinguible.
