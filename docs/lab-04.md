# Lab 04 — IAM: identidad, privilegio mínimo y credenciales temporales

Continuamos sobre el stack de la clase 2. No hay nuevos servicios: usamos
LocalStack, que ya estaba en `compose.yaml`, y lo exploramos desde el ángulo
de identidad.

> **LocalStack Community vs enforcement real**
> En Community podés crear y adjuntar policies, usuarios, grupos y roles, y
> hacer `sts:AssumeRole`. Lo que **no** funciona es el enforcement: un `Deny`
> no bloquea la llamada. Para demostrar eso necesitás LocalStack Pro o una
> cuenta AWS real. El lab documenta los puntos donde el comportamiento difiere.

---

## Prerequisitos

- Rama de trabajo: `lab-04-tuNombre` creada desde `main`
- Servicios activos: `docker compose up -d`
- Verificar LocalStack: `curl -s http://localhost:4566/_localstack/health | python3 -m json.tool`
- `awslocal` disponible: viene con `pip install -r requirements.txt` (paquete `awscli-local`)

---

## Paso 1 — Explorar lo que ya existe en LocalStack

```bash
awslocal iam list-users
awslocal iam list-roles
awslocal s3 ls
```

Al arrancar, LocalStack no tiene usuarios ni roles: partimos de cero, igual
que una cuenta AWS nueva.

---

## Paso 2 — Crear el bucket S3 de referencia

```bash
awslocal s3 mb s3://course-data-raw
awslocal s3 cp data/processed/push_events.json s3://course-data-raw/events/push_events.json
awslocal s3 ls s3://course-data-raw --recursive
```

Este bucket es el "recurso protegido" sobre el que vamos a definir permisos.

---

## Paso 3 — Crear grupo con política administrada

```bash
# grupo
awslocal iam create-group --group-name bigdata-read

# política administrada (equivalente a AmazonS3ReadOnlyAccess, acotada al bucket)
awslocal iam create-policy \
  --policy-name S3ReadOnlyLab \
  --policy-document file://iam/s3_read_policy.json

# adjuntar al grupo
awslocal iam attach-group-policy \
  --group-name bigdata-read \
  --policy-arn arn:aws:iam::000000000000:policy/S3ReadOnlyLab
```

Revisá `iam/s3_read_policy.json`: tiene `Effect: Allow`, `Action: s3:GetObject`
y `Resource` acotado al bucket. Esto es privilegio mínimo.

---

## Paso 4 — Crear usuario y asignarlo al grupo

```bash
awslocal iam create-user --user-name lab-user
awslocal iam add-user-to-group --group-name bigdata-read --user-name lab-user

# verificar membresía
awslocal iam get-group --group-name bigdata-read
```

En este punto el usuario tiene acceso a S3 por pertenecer al grupo.
No tiene credenciales propias todavía.

---

## Paso 5 — Crear access key (llave de larga duración — observar el riesgo)

```bash
awslocal iam create-access-key --user-name lab-user
```

Guardá el `AccessKeyId` y `SecretAccessKey` que devuelve. Son credenciales de
larga duración: no expiran, no dejan rastro de quién las usó, y si se filtran
dan acceso indefinido.

> **Por qué esto es riesgoso en producción**: una access key en un repo, en
> logs o en una variable de entorno mal protegida es un incidente de seguridad.
> La solución es usar roles con STS (paso 7).

---

## Paso 6 — Crear rol con trust policy para EC2

```bash
awslocal iam create-role \
  --role-name app-role \
  --assume-role-policy-document file://iam/trust_policy.json

awslocal iam put-role-policy \
  --role-name app-role \
  --policy-name InlineS3Read \
  --policy-document file://iam/s3_read_policy.json

awslocal iam get-role --role-name app-role
```

Revisá `iam/trust_policy.json`: el `Principal` es `ec2.amazonaws.com`.
Eso significa que solo una instancia EC2 (o en LocalStack, cualquier caller)
puede asumir este rol — no cualquier usuario.

---

## Paso 7 — AssumeRole vía STS → credenciales temporales

```bash
awslocal sts assume-role \
  --role-arn arn:aws:iam::000000000000:role/app-role \
  --role-session-name lab04-session \
  --duration-seconds 900
```

El response tiene tres campos clave:
- `AccessKeyId`: empieza con `ASIA` (en AWS real; en LocalStack es diferente)
- `SecretAccessKey`: rotatoria
- `SessionToken`: obligatorio para autenticar
- `Expiration`: **las credenciales expiran** — en 15 minutos en este ejemplo

Usá esas credenciales para acceder a S3:

```bash
export AWS_ACCESS_KEY_ID=<AccessKeyId del assume-role>
export AWS_SECRET_ACCESS_KEY=<SecretAccessKey>
export AWS_SESSION_TOKEN=<SessionToken>

awslocal s3 ls s3://course-data-raw --recursive
```

---

## Paso 8 — Script automatizado

El script `scripts/iam_demo.py` hace los pasos 2–7 en secuencia:

```bash
python scripts/iam_demo.py
```

Sirve como referencia y para reproducir el setup en un entorno limpio.

---

## Paso 9 — Dónde falla LocalStack Community (documentar en decisions.md)

En Community, un `Deny` explícito no bloquea la llamada:

```bash
# esto en AWS real bloquearía al usuario — en LocalStack Community pasa igual
awslocal iam put-user-policy \
  --user-name lab-user \
  --policy-name DenyEverything \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"*","Resource":"*"}]}'

awslocal s3 ls s3://course-data-raw   # en Community: sigue funcionando
```

> En AWS real (y LocalStack Pro), el Deny explícito siempre gana sobre cualquier
> Allow. Esta es la regla más importante del modelo de evaluación de políticas.

---

## Paso 10 — Documentar en decisions.md

Agregá una decisión con este formato:

```
### 005 - Identidad y credenciales en el lab

Decision: usar roles con STS en lugar de access keys de larga duración para acceso entre servicios.

Contexto: las access keys no expiran y si se filtran dan acceso indefinido.
Los roles con STS generan credenciales temporales (15 min a 12 hs) con trazabilidad.

Alternativas: access keys rotadas manualmente, vault/secret manager.

Tradeoff: asumir un rol requiere que el servicio tenga permiso de sts:AssumeRole
y que el rol tenga un trust policy correcto. Más configuración inicial, menos riesgo.

Resultado: app-role con inline policy de privilegio mínimo sobre course-data-raw.
```

---

## Checkpoint

Al finalizar deberías poder mostrar:

- [ ] Bucket `course-data-raw` con al menos un objeto
- [ ] Grupo `bigdata-read` con la policy adjuntada
- [ ] Usuario `lab-user` en el grupo
- [ ] Rol `app-role` con trust policy para EC2 e inline policy mínima
- [ ] Output del `sts assume-role` con `Expiration` visible
- [ ] Decisión 005 en `docs/decisions.md`
- [ ] Columna "identidad/credencial" en `docs/architecture.md` revisada

---

## Para llevar: en AWS real vs LocalStack

| Acción                        | LocalStack Community | AWS real          |
|-------------------------------|----------------------|-------------------|
| Crear users/groups/roles      | ✅                   | ✅                |
| Adjuntar policies             | ✅                   | ✅                |
| `sts:AssumeRole`              | ✅                   | ✅                |
| Enforcement de Deny           | ❌                   | ✅                |
| MFA virtual                   | ❌                   | ✅                |
| CloudTrail (trazabilidad)     | ❌                   | ✅                |
