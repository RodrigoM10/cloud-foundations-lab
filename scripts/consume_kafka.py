"""
Consumidor Kafka: lee mensajes del topic cloud-events.
Soporta --from-beginning para demostrar replay (diferencia clave vs SQS).

Diferencia con SQS:
  - Los mensajes NO se eliminan al leerlos.
  - Podés releer desde el offset 0 con --from-beginning.
  - Múltiples consumer groups pueden leer el mismo topic independientemente.

Equivalente AWS: Kinesis GetRecords / MSK consumer.
"""

import json
import os
import sys

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC     = os.getenv("KAFKA_TOPIC", "cloud-events")
GROUP_ID  = os.getenv("KAFKA_GROUP_ID", "analytics-group")

try:
    from kafka import KafkaConsumer
    from kafka.errors import NoBrokersAvailable
except ImportError:
    print("Instalar kafka-python: pip install kafka-python")
    sys.exit(1)


def main() -> None:
    from_beginning = "--from-beginning" in sys.argv
    offset_reset = "earliest" if from_beginning else "latest"

    print(f"Consumidor '{GROUP_ID}' en {TOPIC} @ {BOOTSTRAP}")
    if from_beginning:
        print("Modo replay: leyendo desde offset 0")

    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=BOOTSTRAP,
            group_id=GROUP_ID if not from_beginning else f"{GROUP_ID}-replay",
            auto_offset_reset=offset_reset,
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=5000,
        )
    except NoBrokersAvailable:
        print(f"No se pudo conectar a {BOOTSTRAP}")
        print("Verificar: docker compose up -d redpanda && docker compose ps redpanda")
        sys.exit(1)

    count = 0
    try:
        for msg in consumer:
            count += 1
            event = msg.value
            event_type = event.get("type", "?")
            actor = event.get("actor", "-")
            repo  = event.get("repo", "")

            extras = f", repo={repo}" if repo else ""
            print(f"[offset={msg.offset}] {event_type:20s} | actor={actor}{extras}")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

    if count == 0:
        print("No hay mensajes. Ejecutar primero: python scripts/produce_kafka.py")
    else:
        print(f"\nTotal leídos: {count} mensajes. (Ctrl+C para salir si está esperando)")


if __name__ == "__main__":
    main()
