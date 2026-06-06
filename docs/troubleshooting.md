# Troubleshooting

## Docker no responde

Verificar que Docker Desktop o el daemon esten corriendo.

```bash
docker version
docker compose version
```

## Puerto ocupado

Revisar containers activos:

```bash
docker ps
```

## MinIO no abre

Verificar:

```bash
docker compose ps minio
docker compose logs minio
```

## PostgreSQL no acepta conexiones

Esperar healthcheck o revisar logs:

```bash
docker compose logs postgres
```

