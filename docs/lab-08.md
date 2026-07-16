# Lab 08 — Bases de datos: tres formas de tener la base

Cierra el stack base **IAM(04) → EC2(05) → S3(06) → VPC(07) → datos (hoy)**.

> **LocalStack Community no incluye RDS** (es Pro). Pivotamos el lab a la decisión central que la clase enseña: **gestionado vs propio**. Practicamos las dos formas que sí podemos correr — postgres en EC2 (self-managed) y postgres en Docker — y dejamos RDS como referencia para AWS real.

---

## Las tres formas

| Forma | Engine | Qué corre | Quién opera |
|---|---|---|---|
| **postgres-on-EC2** | postgres-server en una instancia EC2 | LocalStack modela la instancia | el equipo: instalar, parchear, backup, failover |
| **docker postgres** | postgres en container del compose | container real, engine real | la plataforma maneja el container; nosotros, los datos |
| **RDS** | Amazon RDS for PostgreSQL | (no disponible en community) | AWS: motor, parches, backups, Multi-AZ |

Las tres comparten el mismo secret (Secrets Manager) y el mismo security group (db-sg referenciando app-private-sg). Lo que cambia es la **carga operativa**.

---

## Prerequisitos

- Branch `lab-08-tuNombre` desde main
- Labs previos corridos en orden:
  - Lab 04: `python scripts/iam_demo.py` (necesario para `app-role`)
  - Lab 05: `python scripts/ec2_demo.py` (necesario para `app-instance-profile`)
  - Lab 07: `python scripts/vpc_demo.py` (necesario para `course-vpc`, `app-private-sg`)
- Servicios: `docker compose up -d` (incluye `localstack` y `postgres`)
- `awslocal --version` responde · `psql --version` responde

> **Si `psql` no responde** (Codespaces creados antes de este lab no lo tienen):
> ```bash
> sudo apt-get update && sudo apt-get install -y postgresql-client
> ```
> Para Codespaces nuevos ya está en `postCreateCommand` del devcontainer.

```bash
# Verificar
awslocal ec2 describe-vpcs --filters Name=tag:Name,Values=course-vpc \
  --query "Vpcs[0].VpcId" --output text
awslocal iam get-instance-profile --instance-profile-name app-instance-profile \
  --query "InstanceProfile.Arn"
docker compose ps postgres
```

---

## Paso 1 — Secret en Secrets Manager (común a las 3 opciones)

```bash
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

awslocal secretsmanager create-secret \
  --name app/db \
  --description "Credencial app para la base — lab 08" \
  --secret-string "{
    \"username\": \"app\",
    \"password\": \"$DB_PASSWORD\",
    \"dbname\": \"appdb\",
    \"port\": 5432,
    \"host\": \"localhost:5432\"
  }"

awslocal secretsmanager get-secret-value --secret-id app/db \
  --query SecretString --output text | python3 -m json.tool
```

La regla aplica para las 3: la credencial nunca se escribe en el código. La app la lee en runtime con su rol (lab 04 + 05).

---

## Paso 2 — Security Group de la base (común a las 3)

```bash
VPC_ID=$(awslocal ec2 describe-vpcs --filters Name=tag:Name,Values=course-vpc \
  --query "Vpcs[0].VpcId" --output text)
APP_SG=$(awslocal ec2 describe-security-groups \
  --filters Name=vpc-id,Values=$VPC_ID Name=group-name,Values=app-private-sg \
  --query "SecurityGroups[0].GroupId" --output text)

DB_SG=$(awslocal ec2 create-security-group \
  --vpc-id $VPC_ID --group-name db-sg \
  --description "Lab 08 — DB privada, ingress solo desde app-private-sg" \
  --query "GroupId" --output text)

awslocal ec2 authorize-security-group-ingress --group-id $DB_SG \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$APP_SG,Description='DB desde la app'}]"
```

Referenciar SG (no CIDR) — la base confía en "lo que esté en el SG de la app", no en IPs específicas. Aplica igual para EC2, docker o RDS.

---

## Paso 3 — Opción 1: postgres en EC2 (self-managed)

```bash
# Subnet privada de la VPC (lab 07)
PRIV_SUBNET=$(awslocal ec2 describe-subnets \
  --filters Name=vpc-id,Values=$VPC_ID Name=tag:Tier,Values=private \
  --query "Subnets[0].SubnetId" --output text)

# Lanzar la instancia con user-data que instala postgres
INSTANCE_ID=$(awslocal ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.micro \
  --count 1 \
  --subnet-id $PRIV_SUBNET \
  --security-group-ids $DB_SG \
  --user-data file://ec2/user_data_postgres.sh \
  --iam-instance-profile Name=app-instance-profile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=db-on-ec2},{Key=Role,Value=database},{Key=ManagedBy,Value=self}]' \
  --query "Instances[0].InstanceId" --output text)

echo "db-on-ec2: $INSTANCE_ID"

# Verificar el user-data cargado
awslocal ec2 describe-instance-attribute \
  --instance-id $INSTANCE_ID --attribute userData \
  --query "UserData.Value" --output text | base64 --decode | head -20
```

Mirá `ec2/user_data_postgres.sh` — ese es el código que en AWS real correría al arranque. Hace 6 cosas: lee el secret, instala postgres-server, configura `listen` y `pg_hba`, arranca el servicio, crea usuario/base, y deja un cron de backups a S3.

**Todas esas 6 tareas son carga operativa tuya.** Con RDS no existirían.

> LocalStack mock-ea EC2: el user-data se almacena pero no se ejecuta. Para ver postgres realmente corriendo sobre la instancia, hay que ir a Learner Lab.

---

## Paso 4 — Opción 2: postgres en Docker (engine real, lo que tenemos)

```bash
# Aplicar seed contra el docker postgres
export PGPASSWORD=postgres
psql -h localhost -U postgres -d course -v ON_ERROR_STOP=1 -f rds/seed.sql

# Verificar
psql -h localhost -U postgres -d course -c "SELECT count(*) FROM app_users;"
psql -h localhost -U postgres -d course -c "SELECT * FROM app_users LIMIT 3;"
```

`docker compose ps postgres` te muestra el container que mantiene el engine. La carga operativa de "que el motor exista" ya la tomó la imagen `postgres:16` — vos seguís manejando la data y el schema, pero no la instalación.

Es funcionalmente equivalente a la EC2 del paso 3 desde el código de la app (mismo `psql`, mismo SQL). La diferencia está en **quién mantiene el motor**.

---

## Paso 5 — Opción 3: RDS (referencia para AWS real)

```bash
# NO ejecutable en LocalStack Community — esto es lo que correrías en AWS real
aws rds create-db-instance \
  --db-instance-identifier app-db \
  --engine postgres --engine-version 16.3 \
  --db-instance-class db.t3.micro \
  --allocated-storage 20 --storage-encrypted \
  --master-username app \
  --master-user-password "$(awslocal secretsmanager get-secret-value --secret-id app/db --query SecretString --output text | jq -r .password)" \
  --db-name appdb \
  --backup-retention-period 7 \
  --no-multi-az \
  --no-publicly-accessible \
  --vpc-security-group-ids $DB_SG \
  --db-subnet-group-name course-db-subnets
```

Esa única línea reemplaza **todo el paso 3**. RDS hace por vos:
- Instalar postgres
- Configurar `listen` y `pg_hba`
- Backups automáticos + PITR (con `--backup-retention-period`)
- Encryption at rest (con `--storage-encrypted`)
- Multi-AZ con standby síncrono (con `--multi-az`)
- Aplicar minor version patches en mantenimiento

A cambio, cedés control: no podés `apt install` extensiones arbitrarias, no podés tocar el SO, dependés de la consola/API para casi todo.

> Para correr esto en serio: AWS Academy Learner Lab del Mod 6.

---

## Paso 6 — Demo automatizada

```bash
python scripts/rds_demo.py
```

Hace los pasos 1–5 en secuencia, idempotente. Imprime una tabla final comparando las 3 opciones.

---

## Paso 7 — Comparación side-by-side

| Tarea operativa | postgres-EC2 | docker postgres | RDS |
|---|---|---|---|
| Instalar el motor | vos | docker image | AWS |
| Iniciar el servicio | vos (systemd) | docker | AWS |
| Parchear minor versions | vos | vos (rebuild) | AWS |
| Backups automáticos | vos (cron) | vos | AWS |
| Point-in-time recovery | vos (custom) | no | AWS (7-35d) |
| Multi-AZ failover | vos | no | AWS (1 flag) |
| Read replicas | vos | no | AWS (1 flag) |
| Monitoring métrico | vos | vos | CloudWatch |
| Encryption at rest | vos (LUKS) | depende | KMS (1 flag) |
| Rotación de credenciales | vos | vos | Secrets+Lambda |

Mientras más arriba en la tabla, más carga operativa. La decisión "managed vs propio" no es técnica, es de equipo: ¿cuántas de esas tareas querés/podés sostener?

---

## Paso 8 — Cleanup

```bash
# Opción 1: terminar la EC2
awslocal ec2 terminate-instances --instance-ids $INSTANCE_ID

# SG
awslocal ec2 delete-security-group --group-id $DB_SG

# Secret (recovery window 7 días por defecto)
awslocal secretsmanager delete-secret --secret-id app/db --force-delete-without-recovery

# Opción 2: limpiar tablas del docker postgres (dejá las de olist)
psql -h localhost -U postgres -d course \
  -c "DROP TABLE IF EXISTS app_audit_log, app_sessions, app_users CASCADE;"
```

---

## Paso 9 — Documentar en `decisions.md`

```
### 009 — Postgres en docker para dev, RDS en prod

Decision: usar docker postgres del compose para desarrollo local y RDS managed
para producción. No usar postgres-on-EC2 en ningún ambiente.

Contexto: postgres-on-EC2 nos da el peor de los dos mundos para una app nueva:
toda la carga operativa de self-managed, sin las garantías de RDS y sin la
simplicidad de docker para dev.

Tradeoff: docker no es producción (sin HA, sin backups automáticos, sin Multi-AZ).
RDS cuesta plata. Postgres-on-EC2 era una opción si tuviéramos requerimientos
puntuales (extensiones no soportadas, control de SO) — no es el caso.

Resultado: dev=docker, prod=RDS. Si en algún momento aparece un requerimiento
que requiera control del SO, se reconsidera postgres-on-EC2 con el costo
operativo explícito.
```

```
### 010 — Credencial en Secrets Manager, nunca en el código

Decision: la password se guarda en Secrets Manager. La app la lee en runtime
con su rol (lab 04). El código no contiene credenciales.

Contexto: credenciales en código son el vector de incidente más común.

Tradeoff: una dependencia más. A favor: rotación automática soportada, acceso
auditado en CloudTrail, control vía IAM.

Resultado: app/db en Secrets Manager. Mismo código de conexión para las 3 opciones
(postgres-EC2, docker, RDS) — solo cambia el host del secret.
```

---

## Checkpoint

- [ ] Secret `app/db` con `username + password + host + dbname`
- [ ] SG `db-sg` con ingress 5432 desde `app-private-sg`
- [ ] Instancia EC2 `db-on-ec2` lanzada con `user_data_postgres.sh` (modelada)
- [ ] Tablas `app_users`, `app_sessions`, `app_audit_log` en docker postgres
- [ ] Comando `aws rds create-db-instance` entendido (no ejecutado)
- [ ] Tabla de comparación leída y discutida
- [ ] Decisiones 009 y 010 en `decisions.md`

---

## Para llevar: las tres formas en perspectiva

| Aspecto | LocalStack ofrece | AWS real ofrece |
|---|---|---|
| EC2 con postgres self-managed | ⚠️ modela la instancia, no ejecuta user-data | ✅ |
| Docker postgres local | ✅ engine real | n/a (no aplica en cloud) |
| RDS managed | ❌ Pro-only | ✅ |
| Secrets Manager | ✅ | ✅ |
| SG + VPC para la red | ✅ | ✅ |

El patrón mental: **la red, la identidad y el secret son los mismos** sea cual sea la opción de base. Lo que cambia es la pieza que ejecuta el motor — y la pregunta es siempre la misma: *¿quién la opera?*
