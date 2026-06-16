# Lab 05 — Cómputo: EC2, instance profile y cierre IAM → EC2 → S3

Continuamos sobre el stack del lab 04. Reutilizamos el rol `app-role` y el bucket `course-data-raw` que dejamos preparados, y los conectamos a una instancia EC2.

> **LocalStack Community vs AWS real**
> El flujo CLI/API de EC2 funciona completo (run-instances, describe, attach
> profile, terminate). Lo que **no** funciona es el arranque real de la VM ni la
> ejecución del `user-data`. La instancia es un objeto de API. Para ver `nginx`
> servir contenido bajado de S3, necesitás AWS real / Learner Lab.

---

## Prerequisitos

- Branch `lab-05-tuNombre` desde `main`
- Dependencias instaladas: `pip install -r requirements.txt`
- Servicios activos: `docker compose up -d`
- **Lab 04 corrido al menos una vez** — necesitamos `app-role` y bucket `course-data-raw`. Si no, primero: `python scripts/iam_demo.py`
- `awslocal --version` responde

---

## Paso 1 — Verificar lo que dejó el lab 04

```bash
awslocal iam get-role --role-name app-role --query "Role.Arn"
awslocal s3 ls s3://course-data-raw
```

Si alguno falla, correr `python scripts/iam_demo.py` antes de seguir.

---

## Paso 2 — Key pair (cómo se accede por SSH, conceptual)

```bash
awslocal ec2 create-key-pair --key-name lab05-key --query "KeyFingerprint"
```

En AWS real el response incluye `KeyMaterial` (la clave privada) que tenés que guardar con `chmod 400`. En LocalStack es mock — el material no se usa.

---

## Paso 3 — Security group (firewall a nivel de instancia)

```bash
SG_ID=$(awslocal ec2 create-security-group \
  --group-name web-sg \
  --description "Lab 05 — HTTP público, SSH restringido" \
  --query "GroupId" --output text)

echo "SG: $SG_ID"

# HTTP abierto al mundo
awslocal ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# SSH desde tu IP (en LocalStack da igual; en AWS real, NUNCA abierto al mundo)
awslocal ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 22 --cidr 0.0.0.0/0

# Verificar
awslocal ec2 describe-security-groups --group-ids $SG_ID
```

Los SG son **stateful**: si una request entra, la respuesta sale automáticamente sin reglas de egress adicionales. Y son **solo allow**: no hay reglas de deny — lo que no esté explícito, queda bloqueado.

---

## Paso 4 — Instance profile (rol del lab 04, ahora adjuntable a EC2)

Un **instance profile** es el wrapper que permite que una instancia EC2 use un rol IAM. Crear uno a partir del rol existente:

```bash
awslocal iam create-instance-profile --instance-profile-name app-instance-profile

awslocal iam add-role-to-instance-profile \
  --instance-profile-name app-instance-profile \
  --role-name app-role

awslocal iam get-instance-profile --instance-profile-name app-instance-profile
```

Ahora cualquier instancia que lance con `--iam-instance-profile Name=app-instance-profile` va a poder asumir `app-role` y obtener credenciales temporales vía IMDSv2 (en AWS real).

---

## Paso 5 — Lanzar la instancia

```bash
INSTANCE_ID=$(awslocal ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.micro \
  --count 1 \
  --key-name lab05-key \
  --security-group-ids $SG_ID \
  --user-data file://ec2/user_data.sh \
  --iam-instance-profile Name=app-instance-profile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=lab05-web},{Key=Lab,Value=05}]' \
  --query "Instances[0].InstanceId" --output text)

echo "Instance: $INSTANCE_ID"
```

Anatomía del comando — cada flag es una decisión:

| Flag | Qué decide |
|---|---|
| `--image-id` | Qué AMI usás (Amazon Linux 2 en este caso) |
| `--instance-type` | Familia + tamaño (CPU/RAM/red) |
| `--key-name` | Cómo te conectás por SSH |
| `--security-group-ids` | Qué puede entrar/salir por red |
| `--user-data` | Qué se ejecuta al primer boot |
| `--iam-instance-profile` | Qué permisos cloud tiene la instancia |
| `--tag-specifications` | Metadata para FinOps, ops, governance |

---

## Paso 6 — Verificar lo que quedó

```bash
# Estado y atributos
awslocal ec2 describe-instances --instance-ids $INSTANCE_ID

# user-data está almacenado (aunque no se ejecutó en LocalStack)
awslocal ec2 describe-instance-attribute \
  --instance-id $INSTANCE_ID \
  --attribute userData \
  --query "UserData.Value" --output text | base64 --decode | head -10
```

En LocalStack Community la instancia aparece `running` instantáneamente. En AWS real pasa `pending → running` y el user-data corre.

---

## Paso 7 — Demo automatizada

El script `scripts/ec2_demo.py` hace los pasos 2–6 en secuencia:

```bash
python scripts/ec2_demo.py
```

Sirve para reproducir el setup en un entorno limpio.

> **Heads-up:** cada corrida lanza una **instancia nueva** (key pair, SG e instance profile son reutilizados). Eso es coherente con "cattle, not pets" — pero si corrés el script varias veces sin terminar las anteriores, vas a acumular instancias. Listalas con `awslocal ec2 describe-instances --query "Reservations[].Instances[].InstanceId"` y termínalas en bloque.

---

## Paso 8 — Ciclo de vida y facturación

```bash
# Stop — libera cómputo, EBS sigue cobrando (conceptual)
awslocal ec2 stop-instances --instance-ids $INSTANCE_ID

# Start — vuelve a correr
awslocal ec2 start-instances --instance-ids $INSTANCE_ID

# Terminate — libera todo
awslocal ec2 terminate-instances --instance-ids $INSTANCE_ID
```

Conexión con FinOps: **stopped no es gratis** (EBS sigue contando). Para no pagar, hay que terminar — y eso solo es posible si la instancia es descartable ("cattle, not pets").

---

## Paso 9 — Limpieza

```bash
awslocal ec2 terminate-instances --instance-ids $INSTANCE_ID
awslocal ec2 delete-security-group --group-id $SG_ID
awslocal ec2 delete-key-pair --key-name lab05-key

# Instance profile (desadjuntar rol antes de borrar)
awslocal iam remove-role-from-instance-profile \
  --instance-profile-name app-instance-profile --role-name app-role
awslocal iam delete-instance-profile --instance-profile-name app-instance-profile
```

---

## Paso 10 — Documentar en `decisions.md`

```
### 006 - Instance profile en lugar de access keys en la instancia

Decision: usar instance profile (rol via IMDSv2) en lugar de access keys hardcodeadas en la VM.

Contexto: una instancia que necesita leer S3 puede acceder por dos caminos:
(a) access keys guardadas en /home/user/.aws/credentials, o
(b) un rol asociado vía instance profile que devuelve creds temporales por IMDSv2.

Tradeoff: opción (a) es más directa pero deja claves de larga duración en disco
— si la instancia se compromete o se snapshotea, esas claves quedan expuestas.
Opción (b) requiere setup inicial pero las credenciales rotan automáticamente y
nunca tocan disco.

Resultado: instance profile 'app-instance-profile' con rol 'app-role' del lab 04.
```

---

## Checkpoint

Al finalizar deberías poder mostrar:

- [ ] `app-instance-profile` creado con `app-role` adjuntado
- [ ] Security group `web-sg` con reglas para 80 y 22
- [ ] Instancia lanzada con tags `Name=lab05-web`, `Lab=05`
- [ ] `describe-instances` mostrando el `IamInstanceProfile` asociado
- [ ] `user-data` cargado (visible vía `describe-instance-attribute`)
- [ ] Decisión 006 en `decisions.md`

---

## Para llevar: LocalStack Community vs AWS real

| Acción | LocalStack Community | AWS real |
|---|---|---|
| `create-key-pair`, `create-security-group` | ✅ mock | ✅ |
| `run-instances` con todos los flags | ✅ objeto de API | ✅ VM real |
| `describe-instances`, `describe-instance-attribute` | ✅ | ✅ |
| Adjuntar instance profile | ✅ | ✅ |
| **Ejecutar user-data** | ❌ | ✅ |
| **Servir HTTP desde la instancia** | ❌ | ✅ |
| **IMDSv2 / credenciales temporales reales** | parcial | ✅ |
| Cobro por hora de cómputo | $0 | $$$ |

Para ver el cierre completo IAM → EC2 → S3 con `nginx` sirviendo contenido bajado del bucket usando el rol de instancia, hay que correr este lab contra Learner Lab del Mod 5 del AWS Academy.
