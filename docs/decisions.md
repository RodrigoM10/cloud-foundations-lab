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

### 011 — IaC declarativa con OpenTofu en lugar de scripts de AWS CLI

Decision: usar OpenTofu (HCL declarativo) para la infra en lugar de scripts
imperativos con aws CLI o boto3.

Contexto: scripts imperativos requieren manejar idempotencia a mano,
ordenar las llamadas, y no muestran el diff antes de aplicar. IaC declarativa
hace eso por nosotros.

Alternativas: Terraform (mismo HCL, licencia BSL desde 2023),
CloudFormation (AWS-only, YAML), AWS CDK (programación), Pulumi.

Tradeoff: hay que aprender HCL y el modelo de state. A favor: diff
antes de aplicar (revisable en PR), destroy/apply idempotente, portabilidad
entre clouds (provider para AWS/GCP/Azure).

Resultado: iac/ en HCL, ejecutable con tofu o terraform indistinto.
Backend local en este lab; remoto (S3 + lock) en el proyecto final.