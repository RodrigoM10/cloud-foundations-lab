# Decision log

## Formato

```text
Decision:
Contexto:
Alternativas:
Tradeoff:
Resultado:
```

## Decisiones

### 001 - Laboratorios locales

Decision: usar Docker Compose, MinIO y LocalStack en lugar de cuentas AWS personales.

Contexto: evitar costos accidentales y reducir friccion de setup.

Tradeoff: no se practica consola AWS real en profundidad.

Resultado: los labs son reproducibles y reutilizables.

### 003 - Formato de eventos crudos

Decision: JSONL (JSON Lines) para data/raw/events.jsonl.

Contexto: los eventos se generan uno por vez. JSONL permite procesar con streaming
sin cargar todo el archivo en memoria, y es fácil de appender.

Alternativas: JSON array, CSV, Parquet.

Tradeoff: JSONL no es legible de un vistazo como un JSON array formateado.
Parquet sería más eficiente a escala, pero requiere dependencias externas.

Resultado: JSONL para raw. CSV para processed (compatibilidad analítica máxima).

### 004 - Pipeline de procesamiento

Decision: script Python (process_events.py) lee JSONL y escribe JSON filtrado.

Contexto: necesitamos filtrar un subconjunto de eventos GitHub Archive para análisis.
El script es reproducible: misma entrada, misma salida, sin efectos secundarios.

Tradeoff: un script por transformación vs una sola función general.
Elegimos un script por transformación: más legible, más fácil de testear.

Resultado: process_events.py → data/processed/push_events.json (filtra PushEvent)

### 002 - Entorno de desarrollo

Decision: GitHub Codespaces.

Contexto: el grupo no tiene instalaciones homogéneas (mix de macOS, Windows y Linux).
Codespaces ofrece el mismo entorno para todos sin configuración local.

Alternativas: Docker Desktop local, WSL2, máquina virtual.

Tradeoff: depende de conectividad y de los free-tier hours disponibles (60 hs/mes por cuenta).
Con Docker local se trabaja offline y sin límite de tiempo.

Resultado: Codespaces para las clases, Docker local como fallback documentado en el README.

### 008 - VPC endpoint en lugar de NAT para tráfico a S3

Decision: usar VPC endpoint Gateway para que la subred privada llegue a S3,
en lugar de un NAT gateway con egress a Internet.

Contexto: una EC2 privada que necesita leer S3 puede ir por dos caminos:
(a) NAT gateway en la subred pública → Internet → S3 (más caro, expone egress),
(b) VPC endpoint Gateway → red interna de AWS (gratis, tráfico privado).

Tradeoff: VPC endpoint solo cubre S3 y DynamoDB; para otros servicios habría
que sumar PrivateLink (Interface endpoints, $/hora por endpoint).

Resultado: VPC endpoint para S3, sin NAT. Si después necesitamos egress
genuino (apt-get, pip install, APIs externas) sumamos NAT con costo conocido.