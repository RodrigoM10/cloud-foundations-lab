# Lab 02 — Pipeline de datos y base relacional

## Objetivo

Correr el pipeline completo: ingestar eventos reales de GitHub Archive,
filtrarlos con Python, cargar datos de e-commerce en PostgreSQL y
consultar el resultado con DuckDB.

---

## Requisitos previos

- Codespace levantado (ver lab-01)
- Estar en la branch de tu equipo: `lab-02-tuapellido`

```bash
git checkout main && git pull
git checkout -b lab-02-tuapellido
```

---

## Paso 1 — Bootstrap

```bash
./scripts/bootstrap.sh
```

Esto verifica dependencias, crea `.env`, instala paquetes Python y crea
los directorios `data/raw/events/`, `data/raw/olist/` y `data/processed/`.

Verificar que terminó sin errores antes de seguir.

---

## Paso 2 — Levantar los servicios

```bash
docker compose up -d postgres minio redis
```

Verificar que están corriendo:

```bash
docker compose ps
```

---

## Paso 3 — Pipeline de eventos

El repo ya incluye una muestra de 2000 eventos reales de GitHub Archive
(enero 2024) en `data/raw/events/github_events.jsonl`.

Correr el script de procesamiento:

```bash
python scripts/process_events.py
```

Salida esperada:

```
Environment: local
Eventos leidos:          2000
PushEvents encontrados:  1658
Salida: .../data/processed/push_events.json
```

Qué hizo el script: leyó el JSONL línea por línea, filtró solo los eventos
de tipo `PushEvent` y los escribió como JSON en `data/processed/`.

---

## Paso 4 — Cargar datos en PostgreSQL

```bash
python scripts/load_postgres.py
```

Esto crea el schema (8 tablas) y carga el dataset Olist Brazilian E-Commerce
(muestra de 3000 órdenes, enero–febrero 2018).

Salida esperada:

```
Creando schema...
Cargando datos...
  category_translations: 71
  customers:             3000
  sellers:               717
  products:              2120
  orders:                3000
  order_items:           3398
  order_payments:        3142
  order_reviews:         2985
Base de datos cargada.
```

---

## Paso 5 — Explorar la base de datos

Conectarse a PostgreSQL:

```bash
docker exec -it cloud-foundations-postgres psql -U postgres -d course
```

Consultas para explorar:

```sql
-- Órdenes por estado
SELECT order_status, COUNT(*) FROM orders GROUP BY order_status ORDER BY 2 DESC;

-- Ticket promedio por estado del cliente
SELECT c.customer_state, ROUND(AVG(p.payment_value)::numeric, 2) AS avg_ticket
FROM orders o
JOIN customers c USING (customer_id)
JOIN order_payments p USING (order_id)
GROUP BY c.customer_state
ORDER BY avg_ticket DESC
LIMIT 10;

-- Score promedio de reviews por categoría
SELECT ct.category_name_en, ROUND(AVG(r.review_score)::numeric, 2) AS avg_score, COUNT(*) AS reviews
FROM order_reviews r
JOIN order_items oi USING (order_id)
JOIN products pr USING (product_id)
JOIN category_translations ct ON pr.category_name = ct.category_name_pt
GROUP BY ct.category_name_en
ORDER BY avg_score DESC
LIMIT 10;
```

Salir con `\q`.

---

## Paso 6 — Consulta analítica con DuckDB

```bash
python scripts/query_analytics.py
```

Muestra los repositorios con más pushes en la hora analizada,
usando DuckDB directamente sobre el archivo JSON — sin base de datos.

---

## Paso 7 — Tests

```bash
pytest tests/ -v
```

Deben pasar 50 tests sin servicios externos corriendo (todo mockeado).

---

## Paso 8 — Documentar la decisión

Abrir `docs/decisions.md` y agregar una entrada con el formato:

```
### 005 - <título de tu decisión>

Decision:
Contexto:
Alternativas:
Tradeoff:
Resultado:
```

Ejemplo de decisiones válidas: por qué JSONL y no CSV para eventos,
por qué DuckDB y no cargar todo en Postgres, por qué una muestra de 3000 órdenes.

---

## Paso 9 — Commit y PR

```bash
git add docs/decisions.md
git commit -m "lab-02: pipeline ejecutado, decisión documentada"
git push -u origin lab-02-tuapellido
```

Abrir un PR en GitHub y asignarlo a un compañero para review.

---

## Resumen del pipeline

```
data/raw/events/github_events.jsonl   (2000 eventos, GitHub Archive)
        ↓  process_events.py
data/processed/push_events.json       (1658 PushEvents)
        ↓  query_analytics.py
Top 10 repos por pushes               (DuckDB, sin infraestructura)

data/raw/olist/*.csv                  (8 CSVs, dataset Olist)
        ↓  load_postgres.py
PostgreSQL course                     (8 tablas, 3000 órdenes)
```

## Equivalentes en AWS

| Local | AWS |
|---|---|
| `github_events.jsonl` | Kinesis Data Stream / S3 raw zone |
| `process_events.py` | Lambda / Glue ETL job |
| `push_events.json` | S3 processed zone |
| DuckDB sobre JSON | Athena sobre S3 |
| PostgreSQL | RDS / Aurora |
| Olist CSVs | S3 + Glue Crawler → Redshift |
