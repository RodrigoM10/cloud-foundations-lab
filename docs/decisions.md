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
### 009 — Postgres en docker para dev, RDS en prod

Decision: usar docker postgres del compose para desarrollo local y RDS managed
para producción. No usar postgres-on-EC2 en ningún ambiente.

Contexto: postgres-on-EC2 nos da el peor de los dos mundos para una app nueva:
toda la carga operativa de self-managed, sin las garantías de RDS y sin la
simplicidad de docker para dev.

Tradeoff: docker no es producción (sin HA, sin backups automáticos, sin Multi-AZ).
RDS cuesta plata. Postgres-on-EC2 era una opción si tuviéramos requerimientos
puntuales (extensiones no soportadas, control de SO) — no es el caso.

Resultado: dev=docker, prod=RDS. Si en algún momento aparece un requerimiento
que requiera control del SO, se reconsidera postgres-on-EC2 con el costo
operativo explícito.
```

```
### 010 — Credencial en Secrets Manager, nunca en el código

Decision: la password se guarda en Secrets Manager. La app la lee en runtime
con su rol (lab 04). El código no contiene credenciales.

Contexto: credenciales en código son el vector de incidente más común.

Tradeoff: una dependencia más. A favor: rotación automática soportada, acceso
auditado en CloudTrail, control vía IAM.

Resultado: app/db en Secrets Manager. Mismo código de conexión para las 3 opciones
(postgres-EC2, docker, RDS) — solo cambia el host del secret.