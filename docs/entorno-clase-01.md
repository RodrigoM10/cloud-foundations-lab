# Qué levantamos en clase 1

Este documento explica qué es cada componente del entorno y por qué existe.

---

## El entorno: GitHub Codespaces

Cuando abrís el repo en Codespaces, GitHub construye un container usando la
configuración en `.devcontainer/devcontainer.json`. Ese container incluye:

- Python 3.12
- Docker (para correr los servicios)
- Las extensiones de VS Code ya instaladas (Python, SQLTools, Docker, Terraform)

No instalaste nada a mano. El entorno es idéntico para todos.

---

## Los servicios: Docker Compose

`compose.yaml` define 5 servicios. Los levantás con:

```bash
docker compose up -d postgres minio redis   # los tres que usamos hoy
docker compose up -d                         # todos
```

### PostgreSQL — puerto 5432

Base de datos relacional. Es el equivalente local de **Amazon RDS** o **Aurora**.

Usada para guardar datos estructurados con SQL: usuarios, eventos, transacciones.

```bash
# Conectarse
docker exec -it cloud-foundations-postgres psql -U postgres -d course
```

### MinIO — puertos 9000 / 9001

Object storage compatible con la API de S3. Es el equivalente local de **Amazon S3**.

- Puerto 9000: API (donde los scripts suben y bajan archivos)
- Puerto 9001: consola web — abrilo desde el panel Ports de VS Code

Credenciales: `minioadmin` / `minioadmin`

### Redis — puerto 6379

Almacén de clave-valor en memoria. Es el equivalente local de **Amazon ElastiCache**.

Usado para cache, sesiones, colas simples y comunicación rápida entre procesos.

```bash
docker exec -it cloud-foundations-redis redis-cli ping
# → PONG
```

### LocalStack — puerto 4566

Emula las APIs de AWS localmente: S3, SQS, SNS, Lambda, DynamoDB, EventBridge.
No necesitás cuenta de AWS ni pagar nada.

```bash
# Verificar que está up
curl http://localhost:4566/_localstack/health
```

Lo usamos a partir de clase 12 (colas, eventos).

### Redpanda — puerto 9092

Broker de mensajes compatible con la API de Kafka. Es el equivalente local de
**Amazon MSK** o **Kinesis**.

Usado para streaming de eventos en tiempo real.

```bash
docker exec -it cloud-foundations-redpanda rpk topic list
```

Lo usamos a partir de clase 15 (streaming).

---

## Los scripts

| Script | Qué hace |
|--------|----------|
| `scripts/bootstrap.sh` | Verifica dependencias, crea `.env`, directorios y datos de ejemplo. Corre una sola vez al inicio. |
| `scripts/check.sh` | Verifica que los servicios estén up y que los archivos esperados existan. Corre al inicio de cada clase. |
| `scripts/load_postgres.py` | Crea el schema `events` y la tabla `signups` en PostgreSQL, e inserta datos de ejemplo. |
| `scripts/process_events.py` | Lee `data/raw/events.jsonl`, filtra los eventos de tipo `signup` y los guarda en `data/processed/signups.json`. |

---

## Los datos

```
data/
  raw/
    events.jsonl      ← eventos sin procesar (generados por bootstrap.sh)
  processed/
    signups.json      ← salida de process_events.py (la generás vos)
```

`events.jsonl` tiene un evento por línea en formato JSON. Hay signups, logins,
purchases y logouts. El script de procesamiento filtra solo los signups.

---

## Conexión con Cloud Foundations

Todo lo que levantamos localmente tiene un equivalente directo en producción.
La diferencia es que acá lo corrés gratis, en tu cuenta de GitHub, sin riesgo de
generar costos accidentales.

| Local | AWS | Concepto |
|-------|-----|----------|
| Docker Compose | ECS / Fargate | correr containers administrados |
| PostgreSQL en Docker | Amazon RDS | base de datos relacional como servicio (PaaS) |
| MinIO | Amazon S3 | object storage |
| Redis en Docker | Amazon ElastiCache | cache en memoria como servicio |
| LocalStack | AWS real | APIs de integración (SQS, SNS, Lambda…) |
| Redpanda | Amazon MSK / Kinesis | streaming de eventos |
| `.env` | AWS Secrets Manager / Parameter Store | gestión de credenciales |
| `scripts/check.sh` | CloudWatch / health checks | observabilidad básica |
| GitHub Actions (`.github/workflows/`) | AWS CodePipeline | CI/CD |

El modelo es el mismo: levantás un servicio, le apuntás con credenciales,
escribís código que habla con su API. Lo que cambia entre local y cloud es
quién gestiona el servidor — vos o el proveedor.

Esto es la definición de **IaaS vs PaaS**: en local gestionás el container
(IaaS). En AWS, RDS gestiona el servidor, los backups y el parche del SO por vos
(PaaS). Vos solo administrás la base.

---

## Trabajo en equipo con Codespaces

Cada integrante del grupo abre su propio Codespace desde el repo compartido.
Cada uno tiene su entorno aislado — lo que rompés en el tuyo no afecta al resto.

### Flujo por clase

```bash
# Al inicio de la clase — cada uno en su codespace
git checkout main && git pull
git checkout -b lab-01-tuapellido

# Durante la clase — commitear cada cambio relevante
git add docs/decisions.md
git commit -m "lab-01: entorno levantado, decisión de Codespaces documentada"

# Al terminar
git push -u origin lab-01-tuapellido
# Abrir PR en GitHub → asignar a un compañero para review
```

### Reglas del equipo

- **Un branch por alumno por clase**: `lab-01-apellido`, `lab-02-apellido`, etc.
- **Al menos un commit por clase**: si no hay commit, no hay evidencia de participación.
- **Cada PR necesita review**: un compañero lee el diff y aprueba antes del merge.
- **Las decisiones van en `docs/decisions.md`**: no en el chat, no en la cabeza.

### Por qué esto importa

En un equipo real nadie trabaja directo en `main`. Los PRs son el lugar donde
se discute una decisión antes de que entre al código. El review de un compañero
es exactamente lo que hace un tech lead antes de aprobar un deploy.

Lo que practicamos acá no es solo Git — es el flujo de trabajo de cualquier
equipo de ingeniería en producción.

---

## El repo como evidencia

Cada cambio que hacés va en un commit. Cada decisión va en `docs/decisions.md`.

El stack puede ser cualquiera — lo que se evalúa es el razonamiento documentado.

```bash
git add docs/decisions.md
git commit -m "lab-01: entorno levantado en Codespaces"
git push
```
