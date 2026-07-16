# Decision log

## Formato

```text
Decision: Se creo una rama lab-02-Mendoza, desde main, se realizo un merge de lab-02-ejemplo. En ese punto se realizaron los comandos correspondientes paso a paso.
Contexto: fork branch github / codespace 
Alternativas: -
Tradeoff: TEST.
Resultado: lab-02 completo.
```

## Decisiones

### 001 - Laboratorios locales

Decision: usar Docker Compose, MinIO y LocalStack en lugar de cuentas AWS personales.

Contexto: evitar costos accidentales y reducir friccion de setup.

Tradeoff: no se practica consola AWS real en profundidad.

Resultado: los labs son reproducibles y reutilizables.

### 002 - Entorno de desarrollo

Decision: GitHub Codespaces.

Contexto: el grupo no tiene instalaciones homogéneas (mix de macOS, Windows y Linux).
Codespaces ofrece el mismo entorno para todos sin configuración local.

Alternativas: Docker Desktop local, WSL2, máquina virtual.

Tradeoff: depende de conectividad y de los free-tier hours disponibles (60 hs/mes por cuenta).
Con Docker local se trabaja offline y sin límite de tiempo.

Resultado: Codespaces para las clases, Docker local como fallback documentado en el README.

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

### 005 - Identidad y credenciales en el lab (LAB 4)

Decision: usar roles con STS en lugar de access keys de larga duración para acceso entre servicios.

Contexto: las access keys no expiran y si se filtran dan acceso indefinido.
Los roles con STS generan credenciales temporales (15 min a 12 hs) con trazabilidad.

Alternativas: access keys rotadas manualmente, vault/secret manager.

Tradeoff: asumir un rol requiere que el servicio tenga permiso de sts:AssumeRole
y que el rol tenga un trust policy correcto. Más configuración inicial, menos riesgo.


Resultado: app-role con inline policy de privilegio mínimo sobre course-data-raw.

Nota sobre el entorno local (LocalStack): Utilizamos LocalStack Community para emular AWS. Se verificó que esta versión gratuita permite probar la mecánica de IAM (crear roles, asumir credenciales vía STS), pero no enforcea las políticas. Un `Deny` explícito no bloquea el acceso localmente. Por lo tanto, las pruebas definitivas de seguridad y políticas destructivas deberán realizarse en un entorno AWS real (Sandbox/Dev).
Resultado: Codespaces para las clases, Docker local como fallback documentado en el README.

### 006 - Instance profile en lugar de access keys en la instancia (LAB 5)

Decision: usar instance profile (rol via IMDSv2) en lugar de access keys hardcodeadas en la VM.

Contexto: una instancia que necesita leer S3 puede acceder por dos caminos:
(a) access keys guardadas en /home/user/.aws/credentials, o
(b) un rol asociado vía instance profile que devuelve creds temporales por IMDSv2.

Tradeoff: opción (a) es más directa pero deja claves de larga duración en disco
— si la instancia se compromete o se snapshotea, esas claves quedan expuestas.
Opción (b) requiere setup inicial pero las credenciales rotan automáticamente y
nunca tocan disco.

Resultado: instance profile 'app-instance-profile' con rol 'app-role' del lab 04.
