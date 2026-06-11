"""
Consumidor SQS: lee mensajes de la cola y los imprime hasta que está vacía.
Equivalente AWS: worker process o Lambda con SQS trigger.

La diferencia con streaming (Kafka/Kinesis):
  - Al hacer delete_message, el mensaje desaparece de la cola para siempre.
  - No hay replay ni múltiples consumer groups sobre los mismos mensajes.
  - Ventaja: semántica "cada mensaje procesado una sola vez" (at-least-once).
"""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError

ENDPOINT   = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
QUEUE_NAME = os.getenv("SQS_QUEUE_NAME", "cloud-foundations-events")


def get_queue_url(sqs_client, name: str) -> str:
    try:
        return sqs_client.get_queue_url(QueueName=name)["QueueUrl"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue":
            print(f"Cola '{name}' no existe. Ejecutar primero: python scripts/produce_sqs.py")
            raise SystemExit(1)
        raise


def main() -> None:
    sqs = boto3.client(
        "sqs",
        endpoint_url=ENDPOINT,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=REGION,
    )

    queue_url = get_queue_url(sqs, QUEUE_NAME)
    print(f"Consumiendo de {QUEUE_NAME}...")

    received_total = 0
    consecutive_empty = 0

    while consecutive_empty < 3:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2,
            MessageAttributeNames=["All"],
        )
        messages = resp.get("Messages", [])

        if not messages:
            consecutive_empty += 1
            time.sleep(0.5)
            continue

        consecutive_empty = 0
        for msg in messages:
            received_total += 1
            body = json.loads(msg["Body"])
            event_type = body.get("type", "?")
            repo = body.get("repo", "-")
            actor = body.get("actor", "-")

            print(f"[{received_total}] {event_type:20s} | actor={actor}, repo={repo}")

            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )

    print(f"\nCola vacía, se detiene. Total recibidos: {received_total} mensajes")


if __name__ == "__main__":
    main()
