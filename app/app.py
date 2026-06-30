"""
Lab 09 — App mínima que lee/escribe en S3.

Diseñada para correr DENTRO de un container Docker, contra LocalStack
(o AWS real, configurando AWS_ENDPOINT_URL distinto).

Variables de entorno:
    AWS_ENDPOINT_URL — endpoint S3 (default: http://host.docker.internal:4566)
    BUCKET          — bucket destino (default: lab-09-app-bucket)
    AWS_REGION      — región (default: us-east-1)
"""

import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://host.docker.internal:4566")
BUCKET = os.environ.get("BUCKET", "lab-09-app-bucket")
REGION = os.environ.get("AWS_REGION", "us-east-1")
KEY = "hello.txt"


def main() -> int:
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )

    print(f"endpoint = {ENDPOINT}")
    print(f"bucket   = {BUCKET}")

    # Write
    now = datetime.now(timezone.utc).isoformat()
    body = f"hello from app — {now}\n".encode()
    try:
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=body)
        print(f"  ✓ PUT s3://{BUCKET}/{KEY}  ({len(body)} bytes)")
    except ClientError as e:
        print(f"  ✗ PUT falló: {e}")
        return 1

    # Read
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=KEY)
        read_back = obj["Body"].read().decode()
        print(f"  ✓ GET s3://{BUCKET}/{KEY}")
        print(f"    contenido: {read_back!r}")
    except ClientError as e:
        print(f"  ✗ GET falló: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
