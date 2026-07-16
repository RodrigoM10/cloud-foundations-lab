# `rds/` — moldes para el lab 08

Lab 08 enseña la decisión "managed vs propio" desde tres formas:

1. **postgres-on-EC2** — bootstrap en `ec2/user_data_postgres.sh`
2. **docker postgres** — el `postgres` del `compose.yaml` (engine real)
3. **RDS** — referencia documentada (no corre en LocalStack community)

Las tres comparten el secret y el SG. Lo que cambia es la carga operativa.

## Archivos

### `rds_config.json`
Parámetros declarativos de la instancia RDS. **No se aplican** en LocalStack community (no hay RDS API), pero sí se usan para:
- Generar la línea `aws rds create-db-instance` de referencia
- Configurar el secret con username y dbname coincidentes
- Documentar las decisiones de arquitectura (instance class, backup retention, encryption, MultiAZ)

Decisiones tomadas:
- **`db.t3.micro`** — burstable, suficiente para el lab (free tier en AWS real)
- **`BackupRetentionPeriod: 7`** — habilita PITR (≥1)
- **`MultiAZ: false`** — dev. En prod, true (ver decisión 009)
- **`StorageEncrypted: true`** — se elige al crear, no se puede agregar después
- **`PubliclyAccessible: false`** — siempre privada

### `seed.sql`
DDL + datos para 3 tablas: `app_users`, `app_sessions`, `app_audit_log`. Se aplica contra el docker postgres (engine real). Funcionalmente equivalente a lo que se ejecutaría sobre la EC2 o la RDS.

**¿Por qué tablas nuevas y no las de Olist?** Olist (lab 02) son datos analíticos del e-commerce → viven en el data lake (lab 06). La base del lab 08 es para la **app transaccional** (sesiones, audit, usuarios CRUD). Separar las dos cosas evita confusión sobre dónde guardar qué.

## La comparación de las 3 opciones

| Tarea | postgres-EC2 | docker postgres | RDS |
|---|---|---|---|
| Instalar engine | vos | docker image | AWS |
| Iniciar servicio | vos (systemd) | docker | AWS |
| Parches minor | vos | vos (rebuild) | AWS |
| Backups automáticos | vos (cron) | vos | AWS |
| Point-in-time recovery | vos (custom) | no | AWS (7-35d) |
| Multi-AZ failover | vos | no | AWS (1 flag) |
| Read replicas | vos | no | AWS (1 flag) |
| Monitoring métrico | vos | vos | CloudWatch |
| Encryption at rest | vos (LUKS) | depende | KMS (1 flag) |
| Rotación de credenciales | vos | vos | Secrets+Lambda |

Mientras más arriba, más carga operativa. La pregunta de la clase es: **¿cuántas de esas tareas el equipo puede sostener?**

## LocalStack Community

| Acción | Estado |
|---|---|
| RDS API completa | ❌ Pro-only |
| EC2 (modelar instancia + user-data almacenado) | ✅ |
| Engine SQL real (psql, CREATE TABLE, etc.) | ✅ vía docker postgres |
| Secrets Manager (CRUD del secret) | ✅ |
| Security Groups + SG referencia SG | ✅ |
