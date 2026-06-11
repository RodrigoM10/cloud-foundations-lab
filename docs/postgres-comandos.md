# Comandos útiles de PostgreSQL

Base de datos del curso: `course` · tablas: `customers`, `orders`

## Conectarse

```bash
# Desde el terminal del codespace
docker exec -it cloud-foundations-postgres psql -U postgres -d course

# Con psql directo (si está instalado)
psql -h localhost -U postgres -d course
# password: postgres
```

---

## Dentro de psql — meta-comandos

```sql
\l                  -- listar bases de datos
\c course           -- conectarse a la base "course"
\dt                 -- listar tablas del schema actual
\d customers        -- describir una tabla (columnas, tipos, constraints)
\d orders
\dn                 -- listar schemas
\du                 -- listar usuarios/roles
\x                  -- activar/desactivar modo expanded (útil para filas anchas)
\timing             -- mostrar tiempo de ejecución de cada query
\q                  -- salir
```

---

## Queries básicos

```sql
-- Ver todas las filas
SELECT * FROM customers;
SELECT * FROM orders;

-- Filtrar
SELECT * FROM customers WHERE country = 'AR';

-- Contar
SELECT COUNT(*) FROM customers;

-- Agrupar
SELECT country, COUNT(*) AS total
FROM customers
GROUP BY country
ORDER BY total DESC;

-- Últimos registros
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;

-- JOIN: clientes con su total de compras
SELECT c.name, c.country, SUM(o.amount) AS total
FROM customers c
JOIN orders o ON c.id = o.customer_id
GROUP BY c.name, c.country
ORDER BY total DESC;
```

---

## Explorar la base

```sql
-- Ver todas las tablas
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema');

-- Ver columnas de una tabla
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'customers';

-- Tamaño de cada tabla
SELECT
    relname AS tabla,
    pg_size_pretty(pg_total_relation_size(relid)) AS tamaño
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

---

## Insertar y modificar

```sql
-- Insertar una fila
INSERT INTO customers (name, country) VALUES ('Test', 'BR');

-- Actualizar
UPDATE customers SET country = 'MX' WHERE name = 'Test';

-- Borrar
DELETE FROM customers WHERE name = 'Test';

-- Truncar (borrar todo, más rápido que DELETE)
TRUNCATE orders;
```

---

## Transacciones

```sql
-- Deshacer cambios
BEGIN;
  INSERT INTO customers (name, country) VALUES ('Rollback', 'PE');
ROLLBACK;

-- Confirmar cambios
BEGIN;
  UPDATE customers SET country = 'AR' WHERE name = 'Grace';
COMMIT;
```

---

## Exportar a CSV

```sql
-- Dentro de psql
\copy (SELECT * FROM customers) TO '/tmp/customers.csv' CSV HEADER;
\copy (SELECT c.name, c.country, o.amount, o.created_at FROM customers c JOIN orders o ON c.id = o.customer_id) TO '/tmp/orders.csv' CSV HEADER;
```

```bash
# Desde el terminal — exportar y copiar al workspace
docker exec -i cloud-foundations-postgres \
  psql -U postgres -d course \
  -c "\copy (SELECT * FROM customers) TO '/tmp/customers.csv' CSV HEADER"

docker cp cloud-foundations-postgres:/tmp/customers.csv data/processed/customers.csv
```

---

## Diagnóstico

```sql
-- Conexiones activas
SELECT pid, usename, application_name, state, query
FROM pg_stat_activity
WHERE state != 'idle';

-- Versión
SELECT version();

-- Ver locks activos
SELECT pid, relation::regclass, mode, granted
FROM pg_locks
WHERE relation IS NOT NULL;
```

---

## Equivalentes AWS

| Comando / concepto local | Equivalente en AWS |
|--------------------------|--------------------|
| `psql` directo | RDS Query Editor / DBeaver via bastion |
| `docker exec … psql` | Session Manager + psql en instancia EC2 |
| `\copy … TO CSV` | `UNLOAD` en Redshift, S3 Export en RDS |
| `pg_stat_activity` | Performance Insights en RDS |
| `pg_statio_user_tables` | Enhanced Monitoring en RDS |
