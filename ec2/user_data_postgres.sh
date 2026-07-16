#!/bin/bash
# Lab 08 — user-data: bootstrap de una instancia con PostgreSQL self-managed.
#
# Comparable al user_data.sh del lab 05 (nginx), pero ahora corremos la base
# nosotros mismos en la VM — sin RDS, sin servicio gestionado.
#
# La instancia:
#   - Lee la credencial desde Secrets Manager (rol de instancia + IMDSv2)
#   - Instala postgres-server y lo arranca
#   - Configura listen + ACL para aceptar conexiones desde la red privada
#
# Lo que NO hace (y RDS sí): backups automáticos, parches del motor, Multi-AZ,
# rotación de credencial. Eso queda como carga operativa del equipo.
#
# En LocalStack Community: este script se almacena pero NO se ejecuta.

set -euo pipefail

REGION="us-east-1"
SECRET_ID="app/db"
PG_VERSION="16"

# 1. Leer credenciales desde Secrets Manager (con el rol de instancia)
yum install -y awscli jq
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --region "$REGION" --query SecretString --output text)
PG_USER=$(echo "$SECRET_JSON" | jq -r .username)
PG_PASSWORD=$(echo "$SECRET_JSON" | jq -r .password)
PG_DB=$(echo "$SECRET_JSON" | jq -r .dbname)

# 2. Instalar PostgreSQL server (la operación que RDS hace por vos)
amazon-linux-extras enable postgresql${PG_VERSION}
yum install -y postgresql-server postgresql-contrib

postgresql-setup --initdb

# 3. Configurar listen y autenticación (la operación que RDS hace por vos)
PG_DATA="/var/lib/pgsql/data"
sed -i "s/^#listen_addresses.*/listen_addresses = '*'/" "$PG_DATA/postgresql.conf"
echo "host    all    all    10.0.0.0/16    scram-sha-256" >> "$PG_DATA/pg_hba.conf"

systemctl enable postgresql
systemctl start postgresql

# 4. Crear el usuario y la base (lo que RDS recibe por --master-username/--db-name)
sudo -u postgres psql <<SQL
CREATE USER ${PG_USER} WITH PASSWORD '${PG_PASSWORD}';
CREATE DATABASE ${PG_DB} OWNER ${PG_USER};
GRANT ALL PRIVILEGES ON DATABASE ${PG_DB} TO ${PG_USER};
SQL

# 5. Backups: cron diario con pg_dump → S3 (lo que RDS hace automático)
cat > /etc/cron.daily/pg-backup-to-s3 <<'CRON'
#!/bin/bash
set -e
TS=$(date +%Y%m%d-%H%M%S)
pg_dump -U postgres course | gzip > /tmp/pg-${TS}.sql.gz
aws s3 cp /tmp/pg-${TS}.sql.gz s3://course-data-lake/db-backups/db-on-ec2/${TS}.sql.gz
rm -f /tmp/pg-${TS}.sql.gz
CRON
chmod +x /etc/cron.daily/pg-backup-to-s3

# 6. Verificación
systemctl is-active postgresql && echo "OK: postgres-on-ec2 corriendo" || echo "FAIL"

# Carga operativa que QUEDA con vos (RDS la cubriría):
#  - Parchear postgres cuando salga un CVE
#  - Rotar la credencial cuando se filtre
#  - Monitorear espacio en disco
#  - Failover si la instancia muere
#  - Restore PITR si alguien borra mal
#  - Replicar a otra AZ para HA
