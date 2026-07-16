"""
Lab 06 — S3 demo: data lake del módulo + cierre IAM → EC2 → S3.

Crea el bucket course-data-lake como fuente de verdad durable del curso:
  - Block Public Access ON, encryption SSE-S3, versioning desde día 1
  - Carga Olist + GitHub Archive + processed
  - Demuestra versioning sobrescribiendo un archivo
  - Aplica bucket policy que autoriza solo al rol app-role (lab 04)
  - Asume el rol y descarga un objeto — sin access keys
  - Genera una presigned URL como demo de acceso temporario

Uso:
    python scripts/s3_demo.py
"""

import json
import boto3
from botocore.exceptions import ClientError
from pathlib import Path

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
S3_DIR = ROOT / "s3"

BUCKET = "course-data-lake"
ROLE_ARN = "arn:aws:iam::000000000000:role/app-role"

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _exists_error(e: ClientError) -> bool:
    code = e.response["Error"].get("Code", "")
    return code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists")


def make_client(service: str, creds: dict = None):
    if creds:
        return boto3.client(
            service,
            endpoint_url=ENDPOINT,
            region_name=REGION,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    return boto3.client(service, **BOTO_KWARGS)


# ── pasos ─────────────────────────────────────────────────────────────────────

def create_bucket(s3):
    try:
        s3.create_bucket(Bucket=BUCKET)
        print(f"  bucket '{BUCKET}' creado")
    except ClientError as e:
        if _exists_error(e):
            print(f"  bucket '{BUCKET}' ya existe")
        else:
            raise


def harden_bucket(s3):
    """Cerrado por defecto: Block Public Access ON + cifrado SSE-S3."""
    s3.put_public_access_block(
        Bucket=BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    print("  Block Public Access: ON (4 flags)")

    s3.put_bucket_encryption(
        Bucket=BUCKET,
        ServerSideEncryptionConfiguration={
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                "BucketKeyEnabled": False,
            }],
        },
    )
    print("  Encryption: SSE-S3 (AES256) por defecto")


def enable_versioning(s3):
    s3.put_bucket_versioning(
        Bucket=BUCKET,
        VersioningConfiguration={"Status": "Enabled"},
    )
    status = s3.get_bucket_versioning(Bucket=BUCKET).get("Status", "Disabled")
    print(f"  Versioning: {status}")


def upload_dataset(s3):
    """Sube Olist + GitHub Archive + processed con prefixes claros.

    Idempotente: salta archivos que ya están en el bucket (compara por size).
    Equivalente conceptual a 'aws s3 sync'.
    """
    uploads, skipped = [], 0

    def upload_if_different(local_path, key):
        nonlocal skipped
        try:
            head = s3.head_object(Bucket=BUCKET, Key=key)
            if head["ContentLength"] == local_path.stat().st_size:
                skipped += 1
                return None
        except ClientError:
            pass
        s3.upload_file(str(local_path), BUCKET, key)
        return (key, local_path.stat().st_size)

    sources = [
        (DATA_DIR / "raw" / "olist", "*.csv",  "raw/olist"),
        (DATA_DIR / "raw" / "events", "*.jsonl", "raw/events"),
        (DATA_DIR / "processed", "*.json", "processed"),
    ]
    for folder, pattern, prefix in sources:
        for f in sorted(folder.glob(pattern)):
            result = upload_if_different(f, f"{prefix}/{f.name}")
            if result:
                uploads.append(result)

    if uploads:
        total_mb = sum(s for _, s in uploads) / (1024 * 1024)
        print(f"  {len(uploads)} objetos nuevos ({total_mb:.1f} MB)")
        for key, size in uploads[:3]:
            print(f"    - {key} ({size:,} bytes)")
        if len(uploads) > 3:
            print(f"    ... y {len(uploads) - 3} más")
    if skipped:
        print(f"  {skipped} objetos ya estaban en S3 (skip)")


def demo_versioning(s3):
    """Sobreescribe un archivo para mostrar que versioning preserva la anterior."""
    key = "raw/olist/orders.csv"

    # Versión "actualizada" (agregamos una línea ficticia de "data del día")
    original = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    new_content = original + b"\nNEW_ORDER_2026_FICTICIO,99999,delivered,2026-06-18,2026-06-19,2026-06-25,,\n"
    s3.put_object(Bucket=BUCKET, Key=key, Body=new_content)
    print(f"  sobrescrito: {key} (+1 fila ficticia)")

    # Listar versiones
    versions = s3.list_object_versions(Bucket=BUCKET, Prefix=key).get("Versions", [])
    print(f"  versiones de '{key}': {len(versions)}")
    for v in versions[:3]:
        marker = " ← actual" if v["IsLatest"] else ""
        print(f"    - VersionId={v['VersionId'][:16]}... Size={v['Size']:,}{marker}")


def apply_bucket_policy(s3):
    policy = (S3_DIR / "bucket_policy.json").read_text()
    s3.put_bucket_policy(Bucket=BUCKET, Policy=policy)
    print("  bucket policy aplicada: GetObject + ListBucket para app-role sobre raw/* y processed/*")


def assume_role_and_download(sts):
    print("  asumiendo rol app-role...")
    creds = sts.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="lab06-download",
        DurationSeconds=900,
    )["Credentials"]
    print(f"  creds temporales obtenidas (expiran: {creds['Expiration']})")

    s3_assumed = make_client("s3", creds=creds)
    key = "raw/olist/customers.csv"
    head = s3_assumed.head_object(Bucket=BUCKET, Key=key)
    print(f"  GetObject como app-role: '{key}' OK ({head['ContentLength']:,} bytes)")


def presigned_url(s3):
    key = "processed/push_events.json"
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=300,
    )
    print(f"  presigned URL para '{key}' (válida 5 min):")
    print(f"    {url[:100]}...")


def summary(s3):
    objects = s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    versions = s3.list_object_versions(Bucket=BUCKET).get("Versions", [])
    total_size = sum(o["Size"] for o in objects) / (1024 * 1024)
    print(f"  objetos:   {len(objects)}")
    print(f"  versiones: {len(versions)} (incluye sobreescritas)")
    print(f"  tamaño:    {total_size:.1f} MB")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Lab 06 — S3 data lake + cierre IAM → EC2 → S3 ===\n")

    s3 = make_client("s3")
    sts = make_client("sts")

    print("1. Bucket")
    create_bucket(s3)

    print("\n2. Hardening por defecto (BPA + encryption)")
    harden_bucket(s3)

    print("\n3. Versioning")
    enable_versioning(s3)

    print("\n4. Upload del dataset (Olist + GitHub Archive + processed)")
    upload_dataset(s3)

    print("\n5. Demo versioning (sobrescribir orders.csv)")
    demo_versioning(s3)

    print("\n6. Bucket policy: solo app-role puede leer")
    apply_bucket_policy(s3)

    print("\n7. AssumeRole + GetObject — cierre del círculo")
    assume_role_and_download(sts)

    print("\n8. Presigned URL — acceso temporario sin asumir rol")
    presigned_url(s3)

    print("\n=== Resumen final ===")
    summary(s3)
    print(f"\nBucket en S3: s3://{BUCKET}/")
    print("Listar todo: awslocal s3 ls s3://course-data-lake --recursive")


if __name__ == "__main__":
    main()
