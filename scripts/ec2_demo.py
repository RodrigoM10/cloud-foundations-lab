"""
Lab 05 — EC2 demo: aprovisionamiento de una instancia con instance profile.

Cierra el círculo IAM → EC2 → S3:
- Key pair (par de claves para SSH conceptual)
- Security group (firewall a nivel de instancia)
- Instance profile a partir del 'app-role' creado en lab-04
- run-instances con user-data que baja un archivo de S3

LocalStack Community: el flujo CLI/API es real (run-instances, describe, attach
profile). El user-data se almacena pero NO se ejecuta. La instancia es un
objeto de API, no una VM corriendo.

Uso:
    python scripts/ec2_demo.py
"""

import time
import boto3
from botocore.exceptions import ClientError
from pathlib import Path

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
EC2_DIR = ROOT / "ec2"

# Resources
KEY_NAME = "lab05-key"
SG_NAME = "web-sg"
ROLE_NAME = "app-role"  # del lab-04
INSTANCE_PROFILE = "app-instance-profile"
INSTANCE_TAG = "lab05-web"
# AMI de Amazon Linux 2 (us-east-1) — en AWS real usá SSM Parameter Store.
# En LocalStack Community es solo un identificador con formato válido.
AMI_ID = "ami-0c02fb55956c7d316"
INSTANCE_TYPE = "t3.micro"

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _already_exists(e: ClientError) -> bool:
    code = e.response["Error"].get("Code", "")
    return (
        code in ("EntityAlreadyExists", "InvalidKeyPair.Duplicate", "InvalidGroup.Duplicate")
        or "already exists" in code.lower()
        or "duplicate" in code.lower()
    )


def make_client(service: str):
    return boto3.client(service, **BOTO_KWARGS)


# ── pasos ─────────────────────────────────────────────────────────────────────

def create_key_pair(ec2):
    try:
        resp = ec2.create_key_pair(KeyName=KEY_NAME)
        print(f"  key pair '{KEY_NAME}' creada (fingerprint: {resp['KeyFingerprint'][:20]}...)")
        # En AWS real guardarías el material privado en disco con chmod 400.
        # En LocalStack es un mock — el privado se descarta.
    except ClientError as e:
        if _already_exists(e):
            print(f"  key pair '{KEY_NAME}' ya existe")
        else:
            raise


def create_security_group(ec2):
    try:
        resp = ec2.create_security_group(
            GroupName=SG_NAME,
            Description="Lab 05 — HTTP público, SSH restringido",
        )
        sg_id = resp["GroupId"]
        print(f"  security group '{SG_NAME}' creado: {sg_id}")
    except ClientError as e:
        if _already_exists(e):
            sg_id = ec2.describe_security_groups(GroupNames=[SG_NAME])["SecurityGroups"][0]["GroupId"]
            print(f"  security group '{SG_NAME}' ya existe: {sg_id}")
        else:
            raise

    # Reglas — idempotentes (ignoramos duplicados)
    rules = [
        {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
         "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP público"}]},
        {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
         "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH (en real, restringir a tu IP)"}]},
    ]
    for rule in rules:
        try:
            ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[rule])
            print(f"  ingress permitido: tcp/{rule['FromPort']}")
        except ClientError as e:
            if "Duplicate" in e.response["Error"].get("Code", ""):
                print(f"  ingress tcp/{rule['FromPort']} ya estaba")
            else:
                raise
    return sg_id


def create_instance_profile(iam):
    """Wrapper que adjunta el rol 'app-role' (lab-04) a una instancia EC2."""
    try:
        iam.create_instance_profile(InstanceProfileName=INSTANCE_PROFILE)
        print(f"  instance profile '{INSTANCE_PROFILE}' creado")
    except ClientError as e:
        if _already_exists(e):
            print(f"  instance profile '{INSTANCE_PROFILE}' ya existe")
        else:
            raise

    try:
        iam.add_role_to_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE,
            RoleName=ROLE_NAME,
        )
        print(f"  rol '{ROLE_NAME}' adjuntado al profile")
    except ClientError as e:
        if "LimitExceeded" in str(e) or "already" in str(e).lower():
            print(f"  rol '{ROLE_NAME}' ya estaba adjuntado")
        else:
            raise

    arn = iam.get_instance_profile(InstanceProfileName=INSTANCE_PROFILE)["InstanceProfile"]["Arn"]
    return arn


def run_instance(ec2, sg_id: str):
    user_data = (EC2_DIR / "user_data.sh").read_text()

    resp = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        MinCount=1, MaxCount=1,
        KeyName=KEY_NAME,
        SecurityGroupIds=[sg_id],
        UserData=user_data,
        IamInstanceProfile={"Name": INSTANCE_PROFILE},
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": INSTANCE_TAG}, {"Key": "Lab", "Value": "05"}],
        }],
    )
    instance = resp["Instances"][0]
    iid = instance["InstanceId"]
    print(f"  instancia lanzada: {iid} ({instance['InstanceType']}, AMI {instance['ImageId']})")
    return iid


def describe_instance(ec2, iid: str):
    # Pequeña espera para que LocalStack registre el estado
    time.sleep(1)
    resp = ec2.describe_instances(InstanceIds=[iid])
    inst = resp["Reservations"][0]["Instances"][0]
    print(f"  estado: {inst['State']['Name']}")
    print(f"  AMI:    {inst['ImageId']}")
    print(f"  type:   {inst['InstanceType']}")
    print(f"  SG:     {[g['GroupName'] for g in inst['SecurityGroups']]}")
    if "IamInstanceProfile" in inst:
        print(f"  profile: {inst['IamInstanceProfile']['Arn']}")
    return inst


def show_user_data(ec2, iid: str):
    import base64
    resp = ec2.describe_instance_attribute(InstanceId=iid, Attribute="userData")
    encoded = resp.get("UserData", {}).get("Value")
    if encoded:
        decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
        first_line = decoded.splitlines()[0] if decoded else ""
        print(f"  user-data cargado ({len(decoded)} chars). Primera línea: {first_line!r}")
    else:
        print("  user-data: vacío")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Lab 05 — EC2 demo: IAM → EC2 → S3 ===\n")
    print("AVISO: LocalStack Community mock-ea EC2.")
    print("       El flujo CLI/API es real; la VM no arranca y el user-data no se ejecuta.\n")

    ec2 = make_client("ec2")
    iam = make_client("iam")

    print("1. Key pair")
    create_key_pair(ec2)

    print("\n2. Security group + reglas de ingress")
    sg_id = create_security_group(ec2)

    print("\n3. Instance profile (wrapper del rol app-role del lab-04)")
    profile_arn = create_instance_profile(iam)
    print(f"   profile ARN: {profile_arn}")

    print("\n4. run-instances con user-data + profile")
    iid = run_instance(ec2, sg_id)

    print("\n5. describe-instances — ver lo que quedó aprovisionado")
    describe_instance(ec2, iid)

    print("\n6. describe-instance-attribute — user-data almacenado")
    show_user_data(ec2, iid)

    print("\n=== Resumen ===")
    print(f"  Key pair:         {KEY_NAME}")
    print(f"  Security group:   {SG_NAME} ({sg_id})")
    print(f"  Instance profile: {INSTANCE_PROFILE}")
    print(f"  Instancia:        {iid}")
    print("\nPara terminar la instancia (no olvidar — cattle, not pets):")
    print(f"  awslocal ec2 terminate-instances --instance-ids {iid}")


if __name__ == "__main__":
    main()
