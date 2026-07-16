# `ec2/` — moldes para el lab 05

Tres archivos que sirven como **referencia y entrada** para el lab de cómputo.
No se ejecutan por sí solos: los consume `scripts/ec2_demo.py` o los usás como
guía si corrés los comandos a mano contra LocalStack o AWS real.

## Archivos

### `security_group.json`
Define el firewall a nivel de instancia. Dos reglas de ingress:
- **HTTP (80)** abierto al mundo — para que se pueda ver la página servida.
- **SSH (22)** restringido a tu IP — el placeholder `REEMPLAZAR_CON_TU_IP/32` se sustituye antes de aplicarlo.

Default deny: todo lo que no esté en la lista, queda bloqueado.

### `user_data.sh`
Bootstrap que corre la primera vez que arranca la instancia. Hace:
1. Instala `nginx` y `awscli`.
2. Baja `s3://course-data-raw/sample/hello.txt` usando el **rol de instancia** (sin access keys en disco — usa IMDSv2).
3. Publica una página que muestra el `instance-id` y el contenido bajado.

Este script materializa el cierre **IAM → EC2 → S3** que vimos en clase 4.

> **LocalStack Community:** el `user-data` se almacena (lo podés ver con `describe-instance-attribute`), pero NO se ejecuta. Para ver `nginx` realmente servir la página, necesitás AWS real o Learner Lab.

### IAM dependencias (de lab-04)
- Rol: `app-role` (trust policy permite a EC2 asumirlo)
- Inline policy: `s3:GetObject` sobre `course-data-raw/*`
- Instance profile: `app-instance-profile` — wrapper que adjunta el rol a una instancia EC2

El `scripts/ec2_demo.py` crea el instance profile a partir del rol existente.
