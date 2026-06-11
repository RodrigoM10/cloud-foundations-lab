import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]

ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
BUCKET     = os.getenv("MINIO_BUCKET", "curso-data")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")


def ensure_bucket(s3_client, name: str) -> None:
    try:
        s3_client.head_bucket(Bucket=name)
    except ClientError:
        s3_client.create_bucket(Bucket=name)
        print(f"Bucket creado: {name}")


def upload(s3_client, local_path: Path, bucket: str, s3_key: str) -> None:
    s3_client.upload_file(str(local_path), bucket, s3_key)
    print(f"Subido: {local_path.name} -> s3://{bucket}/{s3_key}")


def main() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )

    ensure_bucket(s3, BUCKET)

    files_to_upload = []

    processed = ROOT / "data" / "processed"
    for f in processed.glob("*.csv"):
        files_to_upload.append((f, f"processed/{f.name}"))
    for f in processed.glob("*.json"):
        files_to_upload.append((f, f"processed/{f.name}"))

    for local_path, s3_key in files_to_upload:
        if local_path.exists():
            upload(s3, local_path, BUCKET, s3_key)
        else:
            print(f"WARN archivo no encontrado, se omite: {local_path}")

    response = s3.list_objects_v2(Bucket=BUCKET)
    print(f"\nObjetos en s3://{BUCKET}:")
    for obj in response.get("Contents", []):
        print(f"  {obj['Key']} ({obj['Size']} bytes)")


if __name__ == "__main__":
    main()
