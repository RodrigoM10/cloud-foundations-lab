"""
Lab 08 — Tres formas de tener la base: postgres-on-EC2 vs docker vs RDS.

LocalStack 3.x community NO incluye RDS (es Pro). El lab pivota a comparación:
  1. postgres-on-EC2: instancia con user_data_postgres.sh (self-managed)
  2. docker postgres: container del compose (lo que tenemos)
  3. RDS: documentado como referencia para AWS real

Las tres comparten el secret + el SG. Lo que cambia es la carga operativa.

Cierra el stack base IAM(04) → EC2(05) → S3(06) → VPC(07) → datos (hoy).

Uso:
    python scripts/rds_demo.py
"""

import json
import os
import secrets as pysecrets
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
CFG = json.loads((ROOT / "rds" / "rds_config.json").read_text())
SEED_SQL = ROOT / "rds" / "seed.sql"
EC2_USER_DATA = ROOT / "ec2" / "user_data_postgres.sh"

AMI_ID = "ami-0c02fb55956c7d316"
INSTANCE_TYPE = "t3.micro"
INSTANCE_TAG = "db-on-ec2"

PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = os.environ.get("POSTGRES_USER", "postgres")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
PG_DB = os.environ.get("POSTGRES_DB", "course")

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


def client(service):
    return boto3.client(service, **BOTO_KWARGS)


def _already_exists(e: ClientError) -> bool:
    code = e.response["Error"].get("Code", "")
    return (
        "AlreadyExists" in code
        or "Duplicate" in code
        or "already exists" in code.lower()
        or "ResourceExistsException" == code
    )


def create_secret(sm):
    name = CFG["secret"]["Name"]
    password = pysecrets.token_urlsafe(16)
    payload = {
        "username": CFG["db_instance"]["MasterUsername"],
        "password": password,
        "dbname": CFG["db_instance"]["DBName"],
        "port": CFG["db_instance"]["Port"],
        "host": f"{PG_HOST}:{PG_PORT}",
    }
    try:
        sm.create_secret(
            Name=name,
            Description=CFG["secret"]["Description"],
            SecretString=json.dumps(payload),
        )
        print(f"  secret '{name}' creado (password generada)")
        return password
    except ClientError as e:
        if _already_exists(e):
            existing = json.loads(sm.get_secret_value(SecretId=name)["SecretString"])
            print(f"  secret '{name}' ya existe — reuso password")
            return existing["password"]
        raise


def get_vpc_resources(ec2):
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": ["course-vpc"]}])["Vpcs"]
    if not vpcs:
        raise SystemExit("ERROR: no encuentro 'course-vpc'. Corré 'python scripts/vpc_demo.py' antes.")
    vpc_id = vpcs[0]["VpcId"]

    private_subnets = ec2.describe_subnets(Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "tag:Tier", "Values": ["private"]},
    ])["Subnets"]

    app_sg = ec2.describe_security_groups(Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "group-name", "Values": ["app-private-sg"]},
    ])["SecurityGroups"]
    if not app_sg:
        raise SystemExit("ERROR: no encuentro 'app-private-sg'. Corré vpc_demo.py antes.")

    print(f"  VPC:             {vpc_id}")
    print(f"  Subnet privada:  {private_subnets[0]['SubnetId']} ({private_subnets[0]['CidrBlock']})")
    print(f"  SG de la app:    {app_sg[0]['GroupId']} (app-private-sg)")
    return vpc_id, private_subnets[0]["SubnetId"], app_sg[0]["GroupId"]


def create_db_sg(ec2, vpc_id: str, app_sg_id: str) -> str:
    cfg = CFG["security_group"]
    existing = ec2.describe_security_groups(Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "group-name", "Values": [cfg["Name"]]},
    ])["SecurityGroups"]
    if existing:
        sg_id = existing[0]["GroupId"]
        print(f"  SG '{cfg['Name']}' ya existe: {sg_id}")
    else:
        sg_id = ec2.create_security_group(
            VpcId=vpc_id, GroupName=cfg["Name"], Description=cfg["Description"],
        )["GroupId"]
        ec2.create_tags(Resources=[sg_id], Tags=[
            {"Key": "Name", "Value": cfg["Name"]}, {"Key": "Lab", "Value": "08"},
        ])
        print(f"  SG '{cfg['Name']}' creado: {sg_id}")

    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": cfg["Port"], "ToPort": cfg["Port"],
                "UserIdGroupPairs": [{"GroupId": app_sg_id, "Description": "DB desde la app"}],
            }],
        )
        print(f"    ingress tcp/{cfg['Port']} desde app-private-sg")
    except ClientError as e:
        if "Duplicate" in str(e):
            print(f"    ingress tcp/{cfg['Port']} ya estaba")
        else:
            raise
    return sg_id


def launch_db_on_ec2(ec2, subnet_id: str, db_sg_id: str) -> str:
    """Postgres self-managed: EC2 con user-data que instala postgres-server."""
    existing = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [INSTANCE_TAG]},
        {"Name": "instance-state-name", "Values": ["running", "pending"]},
    ])["Reservations"]
    if existing:
        iid = existing[0]["Instances"][0]["InstanceId"]
        print(f"  instancia '{INSTANCE_TAG}' ya existe: {iid}")
        return iid

    user_data = EC2_USER_DATA.read_text()
    resp = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        MinCount=1, MaxCount=1,
        SubnetId=subnet_id,
        SecurityGroupIds=[db_sg_id],
        UserData=user_data,
        IamInstanceProfile={"Name": "app-instance-profile"},
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": INSTANCE_TAG},
                {"Key": "Role", "Value": "database"},
                {"Key": "ManagedBy", "Value": "self"},
                {"Key": "Lab", "Value": "08"},
            ],
        }],
    )
    iid = resp["Instances"][0]["InstanceId"]
    print(f"  instancia '{INSTANCE_TAG}' lanzada: {iid}")
    print(f"  user-data: {EC2_USER_DATA.name} ({len(user_data)} chars, NO se ejecuta en LocalStack)")
    return iid


def show_rds_reference():
    cfg = CFG["db_instance"]
    print(f"  En AWS real / LocalStack Pro, el equivalente managed:\n")
    print(f"    aws rds create-db-instance \\")
    print(f"      --db-instance-identifier {cfg['Identifier']} \\")
    print(f"      --engine {cfg['Engine']} --engine-version {cfg['EngineVersion']} \\")
    print(f"      --db-instance-class {cfg['InstanceClass']} \\")
    print(f"      --allocated-storage {cfg['AllocatedStorage']} --storage-encrypted \\")
    print(f"      --master-username {cfg['MasterUsername']} \\")
    print(f"      --master-user-password '<from secret>' \\")
    print(f"      --db-name {cfg['DBName']} \\")
    print(f"      --backup-retention-period {cfg['BackupRetentionPeriod']} \\")
    print(f"      --no-multi-az --no-publicly-accessible \\")
    print(f"      --vpc-security-group-ids <db-sg> --db-subnet-group-name course-db-subnets")
    print()
    print(f"  Lo que esa línea te ahorra (vs postgres-on-EC2):")
    print(f"    - instalar postgres-server, init, configurar listen y pg_hba")
    print(f"    - automatizar backups + retention + PITR")
    print(f"    - aplicar minor version patches")
    print(f"    - Multi-AZ con standby síncrono")
    print(f"    - monitoring + métricas en CloudWatch")


def show_secret_consumption(sm):
    name = CFG["secret"]["Name"]
    creds = json.loads(sm.get_secret_value(SecretId=name)["SecretString"])
    print(f"  app lee secret '{name}':")
    print(f"    username = {creds['username']}")
    print(f"    password = {'*' * len(creds['password'])}  (no se imprime)")
    print(f"    host     = {creds['host']}")
    print(f"    dbname   = {creds['dbname']}")
    print(f"  → psycopg2.connect(**parsed_secret) — mismo código para las 3 opciones")


def run_seed_against_postgres():
    env = {**os.environ, "PGPASSWORD": PG_PASSWORD}
    cmd_base = ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-d", PG_DB, "-v", "ON_ERROR_STOP=1"]

    try:
        subprocess.run(cmd_base + ["-q", "-f", str(SEED_SQL)], env=env, check=True, capture_output=True, text=True)
        print(f"  seed.sql aplicado a docker postgres ({PG_HOST}:{PG_PORT}/{PG_DB})")
    except FileNotFoundError:
        print("  psql no instalado. Instalá: sudo apt install -y postgresql-client")
        return False
    except subprocess.CalledProcessError as e:
        if "refused" in e.stderr.lower() or "connection" in e.stderr.lower():
            print(f"  postgres no responde. Corré 'docker compose up -d postgres'")
        else:
            print(f"  psql falló: {e.stderr.strip()[:200]}")
        return False

    result = subprocess.run(
        cmd_base + ["-tA", "-c",
         "SELECT 'app_users=' || count(*) FROM app_users UNION ALL "
         "SELECT 'app_audit_log=' || count(*) FROM app_audit_log;"],
        env=env, check=True, capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        print(f"    {line.strip()}")
    return True


def comparison_table(db_on_ec2_iid: str):
    print()
    print("  ┌─────────────────────────────┬──────────────┬──────────────┬──────────────┐")
    print("  │ Tarea                       │ Postgres-EC2 │ Docker pg    │ RDS          │")
    print("  ├─────────────────────────────┼──────────────┼──────────────┼──────────────┤")
    print("  │ Instalar el motor           │ vos          │ docker image │ AWS          │")
    print("  │ Iniciar el servicio         │ vos (systemd)│ docker       │ AWS          │")
    print("  │ Parchear minor versions     │ vos          │ vos (rebuild)│ AWS          │")
    print("  │ Backups automáticos         │ vos (cron)   │ vos          │ AWS          │")
    print("  │ Point-in-time recovery      │ vos (custom) │ no           │ AWS (7-35d)  │")
    print("  │ Multi-AZ failover           │ vos          │ no           │ AWS (1 flag) │")
    print("  │ Read replicas               │ vos          │ no           │ AWS (1 flag) │")
    print("  │ Monitoring métrico          │ vos          │ vos          │ CloudWatch   │")
    print("  │ Encryption at rest          │ vos (LUKS)   │ depende      │ KMS (1 flag) │")
    print("  │ Rotación de credenciales    │ vos          │ vos          │ Secrets+Lmb  │")
    print("  └─────────────────────────────┴──────────────┴──────────────┴──────────────┘")
    print()
    print(f"  postgres-on-EC2 modelada en LocalStack: {db_on_ec2_iid}")
    print(f"  docker postgres: corriendo, engine real para el lab")
    print(f"  RDS: ver comandos arriba, ejecutar en Learner Lab para verlo end-to-end")


def main():
    print("=== Lab 08 — Tres formas de tener la base ===\n")
    print("LocalStack 3.x community no incluye RDS. Comparamos:")
    print("  1. postgres-on-EC2 (self-managed) — EC2 modelada con user-data")
    print("  2. docker postgres — el container del compose (engine real)")
    print("  3. RDS — referencia para AWS real / Learner Lab\n")

    ec2 = client("ec2")
    sm = client("secretsmanager")

    print("1. Secret en Secrets Manager (común a las 3 opciones)")
    create_secret(sm)

    print("\n2. Recursos de la VPC (reuso de lab 07)")
    vpc_id, subnet_id, app_sg_id = get_vpc_resources(ec2)

    print("\n3. SG db-sg (referencia por SG, no CIDR — común a las 3)")
    db_sg_id = create_db_sg(ec2, vpc_id, app_sg_id)

    print("\n4. Opción 1 — postgres-on-EC2: instancia con user_data_postgres.sh")
    db_on_ec2_iid = launch_db_on_ec2(ec2, subnet_id, db_sg_id)

    print("\n5. Opción 2 — docker postgres: aplicar seed.sql (engine real)")
    sql_ok = run_seed_against_postgres()

    print("\n6. Opción 3 — RDS: cómo se haría en AWS real")
    show_rds_reference()

    print("\n7. Cómo la app consume el secret (idéntico para las 3)")
    show_secret_consumption(sm)

    print("\n=== Comparación: quién hace qué ===")
    comparison_table(db_on_ec2_iid)

    print("Inspección:")
    print(f"  awslocal secretsmanager get-secret-value --secret-id {CFG['secret']['Name']}")
    print(f"  awslocal ec2 describe-instances --instance-ids {db_on_ec2_iid}")
    print(f"  awslocal ec2 describe-instance-attribute --instance-id {db_on_ec2_iid} --attribute userData")
    print(f"  PGPASSWORD={PG_PASSWORD} psql -h {PG_HOST} -U {PG_USER} -d {PG_DB}")


if __name__ == "__main__":
    main()
