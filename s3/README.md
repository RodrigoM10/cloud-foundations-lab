# `s3/` — moldes para el lab 06

Un archivo que define la bucket policy que cierra el círculo IAM → EC2 → S3.

## Archivos

### `bucket_policy.json`

Resource-based policy aplicada al bucket `course-data-lake`. Hace dos cosas:

1. **`AllowInstanceRoleReadObjects`** — autoriza `s3:GetObject` sobre `raw/*` y `processed/*` solo al rol `app-role` (el del lab 04, usado como instance profile en lab 05).
2. **`AllowInstanceRoleListBucket`** — autoriza `s3:ListBucket` sobre el bucket con condición de prefix.

**Principal:** `arn:aws:iam::000000000000:role/app-role` — en LocalStack la cuenta es siempre `000000000000`. Para AWS real, reemplazar por tu account ID.

## Cómo se conecta con identity-based policies (lab 04)

| Capa | Quién decide | Qué dice |
|---|---|---|
| Identity policy (lab 04) | IAM en la identidad | "el rol `app-role` puede `s3:GetObject` sobre `course-data-raw/*`" |
| Resource policy (lab 06) | El bucket | "el bucket `course-data-lake` deja entrar a `app-role` para `raw/*` y `processed/*`" |

**Regla de evaluación:** acceso = (identidad permite) Y (recurso no niega). Un `Deny` explícito en cualquier lado gana.

Para que la EC2 con instance profile lea `course-data-lake/raw/customers.csv` necesitamos las dos cosas alineadas — o agregamos el bucket a la identity policy del rol, o el bucket trust al rol (lo que hace este JSON).

## LocalStack Community
S3 en Community es real, incluyendo bucket policies. Las acciones funcionan completas: `put-bucket-policy`, `get-bucket-policy`, evaluación de acceso en `GetObject`. Lo único parcial es lifecycle (transición a Glacier) y replication cross-region.
