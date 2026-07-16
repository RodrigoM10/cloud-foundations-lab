# Lab 07 — Redes: VPC, subredes pública/privada y cierre EC2 → S3 sin Internet

Cierra el arco **IAM (04) → EC2 (05) → S3 (06) → red que los une (hoy)**. La VPC es donde identidad, cómputo y storage se vuelven una arquitectura.

> **LocalStack Community vs AWS real**
> La topología (VPC, subredes, route tables, IGW, SGs, endpoints) se crea y se inspecciona en Community: alcanza para entender el diseño. El tráfico real (NAT, balanceo, paquetes que se mueven, EC2 sirviendo HTTP) requiere AWS real.

---

## Por qué este lab

- Las clases anteriores trataron cada servicio en aislamiento.
- En producción están **dentro de una VPC**: la red define qué se puede ver y qué no.
- Hoy modelamos la arquitectura de 3 capas que es el esqueleto del Proyecto Final.

---

## Prerequisitos

- Branch `lab-07-tuNombre` desde main
- Lab 06 corrido (necesitamos el bucket `course-data-lake` para el VPC endpoint): `python scripts/s3_demo.py`
- Servicios activos: `docker compose up -d`
- `awslocal --version` responde

```bash
# Verificar dependencias
awslocal s3 ls s3://course-data-lake | head -3
```

---

## Paso 1 — Crear la VPC

```bash
VPC_ID=$(awslocal ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --query "Vpc.VpcId" --output text)

awslocal ec2 create-tags --resources $VPC_ID \
  --tags Key=Name,Value=course-vpc Key=Lab,Value=07

awslocal ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames
awslocal ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support

echo "VPC: $VPC_ID"
```

`10.0.0.0/16` = 65.536 IPs. AWS permite VPC entre `/16` y `/28`. DNS hostnames + DNS support habilitados — la EC2 puede resolver nombres y obtener un nombre interno.

---

## Paso 2 — Subredes en distintas AZs (HA por diseño)

```bash
PUB_SUBNET=$(awslocal ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --query "Subnet.SubnetId" --output text)

PRIV_SUBNET=$(awslocal ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b \
  --query "Subnet.SubnetId" --output text)

awslocal ec2 create-tags --resources $PUB_SUBNET --tags Key=Name,Value=public-1a Key=Tier,Value=public
awslocal ec2 create-tags --resources $PRIV_SUBNET --tags Key=Name,Value=private-1b Key=Tier,Value=private

echo "Pública:  $PUB_SUBNET (us-east-1a)"
echo "Privada:  $PRIV_SUBNET (us-east-1b)"
```

**Cada subred vive en UNA AZ.** Para HA, distintas AZs.

`/24` = 256 IPs. AWS reserva 5 IPs por subred (.0 red, .1 router, .2 DNS, .3 reservada futuro, .255 broadcast) → quedan 251 utilizables.

---

## Paso 3 — Internet Gateway (la puerta a Internet)

```bash
IGW_ID=$(awslocal ec2 create-internet-gateway \
  --query "InternetGateway.InternetGatewayId" --output text)

awslocal ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

echo "IGW: $IGW_ID"
```

El IGW por sí solo no hace nada — es un objeto attached a la VPC. **Lo que mueve tráfico es la ruta en la route table.**

---

## Paso 4 — Route table pública (esto es lo que hace pública a la subred)

```bash
RT_PUB=$(awslocal ec2 create-route-table --vpc-id $VPC_ID \
  --query "RouteTable.RouteTableId" --output text)

awslocal ec2 create-tags --resources $RT_PUB --tags Key=Name,Value=rt-public

# La ruta crítica: cualquier IP no-local sale por el IGW
awslocal ec2 create-route \
  --route-table-id $RT_PUB \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id $IGW_ID

# Asociar la route table a la subnet pública
awslocal ec2 associate-route-table --route-table-id $RT_PUB --subnet-id $PUB_SUBNET

awslocal ec2 describe-route-tables --route-table-ids $RT_PUB \
  --query "RouteTables[0].Routes"
```

**No existe un flag "make subnet public".** Una subred es pública **si y solo si** su route table tiene una ruta a un IGW. Esto es la pieza más misunderstood de VPC.

---

## Paso 5 — Route table privada (sin Internet)

```bash
RT_PRIV=$(awslocal ec2 create-route-table --vpc-id $VPC_ID \
  --query "RouteTable.RouteTableId" --output text)

awslocal ec2 create-tags --resources $RT_PRIV --tags Key=Name,Value=rt-private

# NO se agrega ruta a 0.0.0.0/0 → la subred no llega a Internet
awslocal ec2 associate-route-table --route-table-id $RT_PRIV --subnet-id $PRIV_SUBNET
```

Lo que define el aislamiento es la **ausencia** de ruta a IGW.

---

## Paso 6 — Security Groups con referencia entre SGs (no por IP)

```bash
# SG pública: HTTP desde Internet
SG_PUB=$(awslocal ec2 create-security-group \
  --vpc-id $VPC_ID \
  --group-name web-public-sg \
  --description "Capa pública — HTTP 80 desde Internet" \
  --query "GroupId" --output text)

awslocal ec2 authorize-security-group-ingress \
  --group-id $SG_PUB \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# SG privada: 8080 solo desde la SG pública (referencia por SG, no CIDR)
SG_PRIV=$(awslocal ec2 create-security-group \
  --vpc-id $VPC_ID \
  --group-name app-private-sg \
  --description "Capa privada — solo desde web-public-sg" \
  --query "GroupId" --output text)

awslocal ec2 authorize-security-group-ingress \
  --group-id $SG_PRIV \
  --ip-permissions "IpProtocol=tcp,FromPort=8080,ToPort=8080,UserIdGroupPairs=[{GroupId=$SG_PUB,Description='Solo desde la capa pública'}]"

awslocal ec2 describe-security-groups --group-ids $SG_PRIV \
  --query "SecurityGroups[0].IpPermissions"
```

**Referenciar SG en lugar de IP** es la mejor práctica:
- Si las IPs de la capa pública cambian (autoscaling), la regla sigue valiendo
- Documenta intención: "la app privada confía en la web pública", no "la app confía en estas IPs"

SGs son **stateful** (la respuesta sale automática) y **solo allow** (no hay deny — lo que no esté explícito queda bloqueado).

---

## Paso 7 — VPC endpoint a S3: el cierre EC2 → S3 sin Internet

```bash
ENDPOINT_ID=$(awslocal ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.s3 \
  --vpc-endpoint-type Gateway \
  --route-table-ids $RT_PRIV \
  --query "VpcEndpoint.VpcEndpointId" --output text)

awslocal ec2 describe-route-tables --route-table-ids $RT_PRIV \
  --query "RouteTables[0].Routes"
```

Después de esto, la route table privada tiene **dos rutas**:
1. `10.0.0.0/16 → local` (tráfico dentro de la VPC)
2. `pl-* (S3 prefix list) → vpce-* (el endpoint)` — tráfico a S3 va por la red interna de AWS

La subred privada llega al bucket de la clase 6 **sin pasar por Internet** y **sin NAT**.

Esto es lo que combina con todo lo anterior:
- IAM (lab 04): rol con permisos mínimos sobre el bucket
- EC2 (lab 05): instance profile que asume el rol vía IMDSv2
- S3 (lab 06): bucket con BPA + bucket policy que reconoce al rol
- VPC (hoy): tráfico privado a S3, sin IP pública

**Arquitectura defendible.**

---

## Paso 8 — Demo automatizada

El script `scripts/vpc_demo.py` hace los pasos 1–7 en secuencia:

```bash
python scripts/vpc_demo.py
```

Es idempotente — usa tags para encontrar recursos existentes.

---

## Paso 9 — Inspección de la topología

```bash
# Listar todo lo de la VPC
awslocal ec2 describe-vpcs --filters Name=tag:Lab,Values=07
awslocal ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID
awslocal ec2 describe-route-tables --filters Name=vpc-id,Values=$VPC_ID
awslocal ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=$VPC_ID
awslocal ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC_ID
awslocal ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=$VPC_ID
```

---

## Paso 10 — Limpieza

```bash
# Orden importa — dependencias inversas
awslocal ec2 delete-vpc-endpoints --vpc-endpoint-ids $ENDPOINT_ID
awslocal ec2 delete-security-group --group-id $SG_PRIV
awslocal ec2 delete-security-group --group-id $SG_PUB
awslocal ec2 delete-route-table --route-table-id $RT_PRIV
awslocal ec2 delete-route-table --route-table-id $RT_PUB
awslocal ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
awslocal ec2 delete-internet-gateway --internet-gateway-id $IGW_ID
awslocal ec2 delete-subnet --subnet-id $PUB_SUBNET
awslocal ec2 delete-subnet --subnet-id $PRIV_SUBNET
awslocal ec2 delete-vpc --vpc-id $VPC_ID
```

En AWS real, **NAT gateway se cobra por hora** aunque no lo uses — uno de los recursos olvidados más caros. Para este lab no creamos NAT (la subred privada llega a S3 vía endpoint, no necesita NAT).

---

## Paso 11 — Documentar en `decisions.md`

```
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
```

---

## Checkpoint

- [ ] VPC `course-vpc` con `10.0.0.0/16`
- [ ] Subred pública en `us-east-1a` (`10.0.1.0/24`)
- [ ] Subred privada en `us-east-1b` (`10.0.2.0/24`)
- [ ] IGW attached + route table pública con `0.0.0.0/0 → IGW`
- [ ] SG pública con HTTP 80 abierto
- [ ] SG privada que **referencia al SG público** (no por CIDR)
- [ ] VPC endpoint Gateway a S3 asociado a la route table privada
- [ ] Decisión 008 en `decisions.md`

---

## Para llevar: LocalStack Community vs AWS real

| Acción | LocalStack | AWS real |
|---|---|---|
| Crear VPC, subnets, route tables, IGW | ✅ real | ✅ |
| Crear SGs y reglas (incluyendo referencias SG-a-SG) | ✅ real | ✅ |
| `describe-*` para inspeccionar topología | ✅ | ✅ |
| Lanzar EC2 (estado + atributos) | ⚠️ mock | ✅ |
| NAT gateway, VPC endpoint (tráfico real) | ⚠️ parcial | ✅ |
| ELB / ALB / NLB | ⚠️ parcial | ✅ |

Para validar tráfico real (que la privada llegue a S3 vía endpoint, que la app se conecte a la DB), Learner Lab del Mod 7 + 8 del AWS Academy.
