"""
Productor Kafka: lee data/raw/events/github_events.jsonl y publica en el topic cloud-events.
Usa Redpanda como broker local (compatible con API Kafka).

Equivalente AWS: Kinesis PutRecord / MSK producer.

AWS real:
  - Para Kinesis: usar boto3 kinesis.put_record()
  - Para MSK: mismo código kafka-python con bootstrap_servers de MSK
  - Misma semántica de offset y particiones
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "data" / "raw" / "events" / "github_events.jsonl"

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC     = os.getenv("KAFKA_TOPIC", "cloud-events")

try:
    from kafka import KafkaProducer
    from kafka.errors import NoBrokersAvailable
except ImportError:
    print("Instalar kafka-python: pip install kafka-python")
    sys.exit(1)


def main() -> None:
    if not EVENTS_FILE.exists():
        print(f"Archivo no encontrado: {EVENTS_FILE}")
        print("Ejecutar primero: ./scripts/bootstrap.sh")
        return

    print(f"Topic: {TOPIC} @ {BOOTSTRAP}")

    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks="all",
        )
    except NoBrokersAvailable:
        print(f"No se pudo conectar a {BOOTSTRAP}")
        print("Verificar: docker compose up -d redpanda && docker compose ps redpanda")
        sys.exit(1)

    sent = 0
    with EVENTS_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            future = producer.send(
                TOPIC,
                key=event.get("actor", ""),
                value=event,
            )
            metadata = future.get(timeout=10)
            print(f"Publicado: {event.get('type', '?'):20s} | "
                  f"actor={event.get('actor', '-')} "
                  f"(offset={metadata.offset})")
            sent += 1

    producer.flush()
    producer.close()
    print(f"\nTotal publicados: {sent} mensajes")


if __name__ == "__main__":
    main()
