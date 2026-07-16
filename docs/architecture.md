# Arquitectura del lab

Stack del curso: local-first con equivalentes cloud documentados por componente.

## Componentes

| Componente local         | Equivalente cloud                                  | Identidad / credencial                           |
|--------------------------|-----------------------------------------------------|--------------------------------------------------|
| PostgreSQL (Docker)      | RDS · Cloud SQL · Azure Database for PG            | usuario de BD desde variable de entorno, nunca hardcodeado |
| MinIO                    | Amazon S3 · Cloud Storage · Azure Blob Storage     | rol IAM con `s3:GetObject/PutObject` acotado al bucket |
| Redis (Docker)           | ElastiCache · Memorystore · Azure Cache for Redis  | contraseña desde variable de entorno             |
| Redpanda / Kafka         | MSK/Kinesis · Pub/Sub · Azure Event Hubs           | SASL/SCRAM o credencial de servicio, no acceso anónimo |
| LocalStack               | AWS IAM/STS/S3 real                                 | `test/test` en local; roles con STS en producción |
| Docker Compose           | ECS/Fargate · Cloud Run · Azure Container Apps     | rol de tarea (task role) asumible por el contenedor |

## Decisiones de identidad (clase 4)

- **Root no se usa**: la cuenta raíz existe pero el día a día va por un usuario/rol con MFA.
- **Privilegio mínimo**: cada componente tiene solo los permisos que necesita — ni más.
- **Credenciales temporales > llaves de larga duración**: asumir un rol vía STS en lugar de repartir access keys.
- **Secretos fuera del código**: variables de entorno, `.env` fuera del repo, o un secret manager en producción.

## Puntos únicos de falla identificados (clase 3)

| SPOF                            | Mitigación en cloud                              |
|---------------------------------|--------------------------------------------------|
| PostgreSQL single instance      | RDS Multi-AZ con réplica en standby              |
| MinIO single node               | S3 (durabilidad 99.999999999% por diseño)        |
| Un solo admin con acceso root   | MFA obligatorio + rotación de credenciales       |
| Configuración manual no versionada | IaC (Terraform / CDK) + GitOps               |

## Diagrama de flujo de datos

```
[github_events.jsonl]
        ↓
process_events.py → [push_events.json]
        ↓
query_analytics.py (DuckDB)

[olist CSVs]
        ↓
load_postgres.py → PostgreSQL ← SQL queries
                        ↓
                   postgres-comandos.md

[push_events.json]
        ↓
upload_to_object_storage.py → MinIO (S3-compatible)
        ↓
produce_kafka.py → Redpanda ← consume_kafka.py

[github_events.jsonl]
        ↓
produce_sqs.py → LocalStack SQS ← consume_sqs.py
```
