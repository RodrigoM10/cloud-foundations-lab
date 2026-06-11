# Lab 02 — Storage: object storage y base de datos

Objetivo: subir archivos a MinIO (S3 local), consultar desde PostgreSQL, y entender el patrón data lake en tres capas.

## Prerrequisitos

- Lab 01 completado (`data/processed/signups.json` existe)
- `docker compose up -d postgres minio` (deben estar corriendo)

## Paso 1 — Subir archivos a object storage

```bash
python scripts/upload_to_object_storage.py
```

Salida esperada:

```
Bucket creado: curso-data
Subido: events.jsonl -> s3://curso-data/raw/events.jsonl
Subido: signups.json -> s3://curso-data/processed/signups.json

Objetos en s3://curso-data:
  raw/events.jsonl (NNN bytes)
  processed/signups.json (NNN bytes)
```

## Paso 2 — Explorar MinIO Console

Abrir en el navegador: **http://localhost:9001**

- Usuario: `minioadmin` / Contraseña: `minioadmin`
- Navegar al bucket `curso-data`
- Verificar que los archivos aparecen en `raw/` y `processed/`

## Paso 3 — Exportar ventas desde PostgreSQL

El script `003_export_sales_by_country.sql` exporta un CSV con ventas por país.

```bash
docker exec -i cloud-foundations-postgres psql -U postgres -d course \
  < sql/003_export_sales_by_country.sql

docker cp cloud-foundations-postgres:/tmp/sales_by_country.csv \
  data/processed/sales_by_country.csv
```

Verificar:

```bash
cat data/processed/sales_by_country.csv
```

Subir también el CSV al bucket:

```bash
python scripts/upload_to_object_storage.py
```

## Paso 4 — Patrón raw / processed / curated

El data lake tiene tres capas:

| Capa       | Prefix          | Contenido                            |
|------------|-----------------|--------------------------------------|
| raw        | `raw/`          | Datos sin transformar (ingesta)      |
| processed  | `processed/`    | Datos limpios y normalizados         |
| curated    | `curated/`      | Agregados listos para consumo        |

En AWS la misma estructura vive en S3, con políticas de lifecycle y control de acceso por prefix.

---

## Entregable de clase

Al finalizar deberías poder mostrar:

- `data/processed/sales_by_country.csv` con filas por país
- MinIO Console con archivos en raw/ y processed/
- Diagrama o descripción escrita de las 3 capas del data lake

---

## Conexión conceptual (AWS)

| Local                           | AWS equivalente                       |
|---------------------------------|---------------------------------------|
| MinIO bucket                    | S3 bucket                             |
| `upload_to_object_storage.py`   | SDK boto3 o S3 Transfer               |
| MinIO Console (http://localhost:9001) | AWS S3 Console                  |
| PostgreSQL `\copy` → CSV        | Glue → S3 export                      |
| 3 capas en prefixes             | S3 bucket con lifecycle rules         |
