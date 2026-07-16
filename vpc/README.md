# `vpc/` — moldes para el lab 07

Tres archivos que describen la topología de red: el diseño en JSON, el wizard que se usaría en consola AWS, y la lectura conceptual.

## Archivos

### `vpc_config.json`
Parámetros declarativos de la VPC del curso. Reproducible — el `scripts/vpc_demo.py` lo lee y aplica.

Componentes:
- **VPC** `10.0.0.0/16` con DNS habilitado
- **Subred pública** `10.0.1.0/24` en `us-east-1a` → tier público
- **Subred privada** `10.0.2.0/24` en `us-east-1b` → tier privado (otra AZ para HA)
- **SG web-public** — HTTP 80 desde Internet
- **SG app-private** — puerto 8080 solo desde el SG público (referencia por SG, no por CIDR)
- **VPC endpoint Gateway** a S3 — la subred privada llega al bucket sin pasar por internet

## La pieza clave: pública vs privada lo decide la ruta

Una subred no tiene un flag "hacer pública". Es **pública** si su route table tiene `0.0.0.0/0 → IGW`. Si no, es privada.

```
Subred pública (10.0.1.0/24) → Route Table (RT-public)
                                  ├─ 10.0.0.0/16 → local
                                  └─ 0.0.0.0/0   → IGW    ← esto la hace pública

Subred privada (10.0.2.0/24) → Route Table (RT-private)
                                  ├─ 10.0.0.0/16          → local
                                  └─ pl-id (S3 prefix list) → VPC endpoint (S3)
                                  (sin ruta a IGW = privada de Internet)
```

## El cierre EC2 → S3 sin Internet

La subred privada **no** tiene salida a Internet (no hay ruta a IGW ni a NAT). Pero gracias al **VPC endpoint Gateway**, la subred privada puede leer el bucket `course-data-lake` (lab 06) directo por la red de AWS.

Combinado con el rol del lab 04/05 (instance profile + bucket policy), la EC2 privada:
- No tiene IP pública
- No tiene access keys
- Llega a S3 sin salir a Internet
- Lee solo lo que el rol + bucket policy permiten

Eso es arquitectura defendible.

## LocalStack Community
- Crear VPC, subredes, route tables, IGW, SGs: ✅ real
- Lanzar EC2: ⚠️ mock (la instancia existe como objeto)
- NAT gateway, VPC endpoints, ELB: ⚠️ se crean como objetos, el tráfico real no se mueve

Para el lab usamos LocalStack como **modelador de topología**: el grafo de recursos es real, las consecuencias de tráfico requieren AWS real para verificarse.
