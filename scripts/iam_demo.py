"""
Lab 04 — IAM demo: grupo, usuario, rol y credenciales temporales vía STS.

Corre contra LocalStack Community (mecánica de IAM, sin enforcement real).
Para enforcement real de Deny, usá LocalStack Pro o una cuenta AWS.

Uso:
    python scripts/iam_demo.py
"""

import json
import boto3
from botocore.exceptions import ClientError
from pathlib import Path

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
BUCKET = "course-data-raw"
IAM_DIR = Path(__file__).parent.parent / "iam"

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(service: str):
    return boto3.client(service, **BOTO_KWARGS)


def ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"  bucket '{BUCKET}' ya existe")
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key="sample/hello.txt", Body=b"hello from lab-04")
        print(f"  bucket '{BUCKET}' creado con objeto de ejemplo")


def create_group_with_policies(iam):
    group = "bigdata-read"
    try:
        iam.create_group(GroupName=group)
        print(f"  grupo '{group}' creado")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"  grupo '{group}' ya existe")
        else:
            raise

    # política administrada — read-only sobre S3 (equivalente a AmazonS3ReadOnlyAccess)
    policy_doc = (IAM_DIR / "s3_read_policy.json").read_text()
    try:
        resp = iam.create_policy(
            PolicyName="S3ReadOnlyLab",
            PolicyDocument=policy_doc,
            Description="Lectura sobre course-data-raw — lab 04",
        )
        policy_arn = resp["Policy"]["Arn"]
        print(f"  policy 'S3ReadOnlyLab' creada: {policy_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            account_id = iam.get_user()["User"]["Arn"].split(":")[4]
            policy_arn = f"arn:aws:iam::{account_id}:policy/S3ReadOnlyLab"
            print(f"  policy 'S3ReadOnlyLab' ya existe: {policy_arn}")
        else:
            raise

    iam.attach_group_policy(GroupName=group, PolicyArn=policy_arn)
    print(f"  policy adjuntada al grupo '{group}'")
    return group, policy_arn


def create_user(iam, group: str):
    username = "lab-user"
    try:
        iam.create_user(UserName=username)
        print(f"  usuario '{username}' creado")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"  usuario '{username}' ya existe")
        else:
            raise

    iam.add_user_to_group(GroupName=group, UserName=username)
    print(f"  usuario '{username}' agregado al grupo '{group}'")

    # access key (equivalente a "llave de larga duración" — lo que queremos evitar en prod)
    try:
        key = iam.create_access_key(UserName=username)["AccessKey"]
        print(f"  access key creada: {key['AccessKeyId']} (larga duración — evitar en prod)")
    except ClientError as e:
        if "LimitExceeded" in str(e):
            print("  access key ya existe para este usuario")
        else:
            raise

    return username


def create_role(iam):
    role_name = "app-role"
    trust_policy = (IAM_DIR / "trust_policy.json").read_text()
    inline_policy = (IAM_DIR / "s3_read_policy.json").read_text()

    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Description="Rol asumible por EC2 con acceso mínimo a S3 — lab 04",
        )
        print(f"  rol '{role_name}' creado")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"  rol '{role_name}' ya existe")
        else:
            raise

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="InlineS3Read",
        PolicyDocument=inline_policy,
    )
    print(f"  inline policy 'InlineS3Read' adjuntada al rol '{role_name}'")

    role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    return role_name, role_arn


def assume_role_and_use_s3(sts, role_arn: str):
    print(f"\n  asumiendo rol: {role_arn}")
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="lab04-session",
        DurationSeconds=900,
    )
    creds = resp["Credentials"]
    print(f"  AccessKeyId:  {creds['AccessKeyId']}")
    print(f"  Expiration:   {creds['Expiration']}  ← credencial temporal")

    # usar las credenciales temporales para acceder a S3
    s3_temp = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

    objects = s3_temp.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    print(f"  objetos en '{BUCKET}' con credenciales temporales:")
    for obj in objects:
        print(f"    - {obj['Key']} ({obj['Size']} bytes)")

    return creds


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Lab 04 — IAM demo ===\n")
    print("AVISO: LocalStack Community no enforcea policies (Deny no bloquea).")
    print("       Practicamos la mecánica: crear, adjuntar, asumir.\n")

    iam = make_client("iam")
    s3 = make_client("s3")
    sts = make_client("sts")

    print("1. Bucket S3")
    ensure_bucket(s3)

    print("\n2. Grupo + policy administrada")
    group, policy_arn = create_group_with_policies(iam)

    print("\n3. Usuario → grupo")
    username = create_user(iam, group)

    print("\n4. Rol con trust policy (EC2) + inline policy mínima")
    role_name, role_arn = create_role(iam)

    print("\n5. AssumeRole vía STS → credenciales temporales")
    creds = assume_role_and_use_s3(sts, role_arn)

    print("\n=== Resumen de recursos creados ===")
    print(f"  Bucket:  {BUCKET}")
    print(f"  Grupo:   {group}")
    print(f"  Policy:  {policy_arn}")
    print(f"  Usuario: {username}")
    print(f"  Rol:     {role_arn}")
    print("\nListo. Revisá los JSON en iam/ para entender cada documento.")


if __name__ == "__main__":
    main()
