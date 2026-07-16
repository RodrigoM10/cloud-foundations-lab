"""
Lab 07 — VPC demo: topología de red + cierre EC2 → S3 vía VPC endpoint.

Cierra el arco IAM (04) → EC2 (05) → S3 (06) → red (hoy). Crea:
  - VPC 10.0.0.0/16
  - 2 subredes (pública y privada) en distintas AZs
  - IGW + route table pública (lo que hace pública a una subred)
  - SG público y SG privado (con referencia a SG, no por CIDR)
  - VPC endpoint Gateway a S3 → la privada llega al bucket sin Internet

LocalStack Community: la topología se modela completa. El tráfico real
(NAT, balanceo, paquetes en la subred) requiere AWS real para verificarse.

Uso:
    python scripts/vpc_demo.py
"""

import json
import boto3
from botocore.exceptions import ClientError
from pathlib import Path

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
ROOT = Path(__file__).parent.parent
CONFIG = json.loads((ROOT / "vpc" / "vpc_config.json").read_text())

BOTO_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(service: str):
    return boto3.client(service, **BOTO_KWARGS)


def find_by_tag(items, name: str, key: str = "Name") -> dict | None:
    """Encuentra el primero con tag Name=<name>."""
    for it in items:
        for tag in it.get("Tags", []) or []:
            if tag["Key"] == key and tag["Value"] == name:
                return it
    return None


def tag(ec2, resource_id: str, name: str, **extra):
    tags = [{"Key": "Name", "Value": name}, {"Key": "Lab", "Value": "07"}]
    for k, v in extra.items():
        tags.append({"Key": k, "Value": v})
    ec2.create_tags(Resources=[resource_id], Tags=tags)


# ── pasos ─────────────────────────────────────────────────────────────────────

def create_vpc(ec2):
    cfg = CONFIG["vpc"]
    existing = find_by_tag(ec2.describe_vpcs()["Vpcs"], cfg["Name"])
    if existing:
        print(f"  VPC '{cfg['Name']}' ya existe: {existing['VpcId']}")
        return existing["VpcId"]

    vpc_id = ec2.create_vpc(CidrBlock=cfg["CidrBlock"])["Vpc"]["VpcId"]
    tag(ec2, vpc_id, cfg["Name"])
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
    print(f"  VPC '{cfg['Name']}' creada: {vpc_id} ({cfg['CidrBlock']})")
    return vpc_id


def create_subnets(ec2, vpc_id: str) -> dict:
    """Returns {tier: subnet_id}."""
    result = {}
    existing_subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]

    for cfg in CONFIG["subnets"]:
        existing = find_by_tag(existing_subnets, cfg["Name"])
        if existing:
            sid = existing["SubnetId"]
            print(f"  subnet '{cfg['Name']}' ya existe: {sid}")
        else:
            sid = ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock=cfg["CidrBlock"],
                AvailabilityZone=cfg["AvailabilityZone"],
            )["Subnet"]["SubnetId"]
            tag(ec2, sid, cfg["Name"], Tier=cfg["Tier"])
            print(f"  subnet '{cfg['Name']}' creada: {sid} ({cfg['CidrBlock']} en {cfg['AvailabilityZone']})")
        result[cfg["Tier"]] = sid
    return result


def create_igw(ec2, vpc_id: str) -> str:
    existing = find_by_tag(
        ec2.describe_internet_gateways(
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
        )["InternetGateways"],
        "course-igw",
    )
    if existing:
        print(f"  IGW ya existe: {existing['InternetGatewayId']}")
        return existing["InternetGatewayId"]

    igw_id = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]
    tag(ec2, igw_id, "course-igw")
    ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    print(f"  IGW creado y attached: {igw_id}")
    return igw_id


def create_route_tables(ec2, vpc_id: str, subnets: dict, igw_id: str) -> dict:
    """Crea RT pública (con ruta a IGW) y RT privada (sin IGW)."""
    result = {}
    existing_rts = ec2.describe_route_tables(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["RouteTables"]

    for tier in ("public", "private"):
        name = f"rt-{tier}"
        existing = find_by_tag(existing_rts, name)
        if existing:
            rt_id = existing["RouteTableId"]
            print(f"  route table '{name}' ya existe: {rt_id}")
        else:
            rt_id = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]["RouteTableId"]
            tag(ec2, rt_id, name, Tier=tier)
            print(f"  route table '{name}' creada: {rt_id}")

            # Asociar a la subnet correspondiente
            ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnets[tier])
            print(f"    asociada a subnet {tier}")

        # La pública: ruta a IGW
        if tier == "public":
            try:
                ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id)
                print(f"    ruta 0.0.0.0/0 → IGW agregada (esto hace pública a la subnet)")
            except ClientError as e:
                if "RouteAlreadyExists" in str(e):
                    print(f"    ruta 0.0.0.0/0 → IGW ya existía")
                else:
                    raise

        result[tier] = rt_id
    return result


def create_security_groups(ec2, vpc_id: str) -> dict:
    """Crea SGs con referencias por SG (no por CIDR) para la capa privada."""
    result = {}
    existing_sgs = ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["SecurityGroups"]

    # Primera pasada: crear todos los SGs (sin reglas que referencien otro SG todavía)
    for cfg in CONFIG["security_groups"]:
        existing = next((s for s in existing_sgs if s["GroupName"] == cfg["Name"]), None)
        if existing:
            sg_id = existing["GroupId"]
            print(f"  SG '{cfg['Name']}' ya existe: {sg_id}")
        else:
            sg_id = ec2.create_security_group(
                VpcId=vpc_id, GroupName=cfg["Name"], Description=cfg["Description"],
            )["GroupId"]
            tag(ec2, sg_id, cfg["Name"])
            print(f"  SG '{cfg['Name']}' creado: {sg_id}")
        result[cfg["Name"]] = sg_id

    # Segunda pasada: aplicar reglas (ya tenemos todos los IDs para referenciar)
    for cfg in CONFIG["security_groups"]:
        sg_id = result[cfg["Name"]]
        for rule in cfg["IngressRules"]:
            perm = {
                "IpProtocol": rule["IpProtocol"],
                "FromPort": rule["FromPort"],
                "ToPort": rule["ToPort"],
            }
            if "CidrIp" in rule:
                perm["IpRanges"] = [{"CidrIp": rule["CidrIp"], "Description": rule.get("Description", "")}]
            elif "ReferencedSgName" in rule:
                ref_id = result[rule["ReferencedSgName"]]
                perm["UserIdGroupPairs"] = [{"GroupId": ref_id, "Description": rule.get("Description", "")}]
            try:
                ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[perm])
                ref = rule.get("ReferencedSgName") or rule.get("CidrIp")
                print(f"    {cfg['Name']}: ingress tcp/{rule['FromPort']} desde {ref}")
            except ClientError as e:
                if "Duplicate" in str(e):
                    pass
                else:
                    raise
    return result


def create_s3_endpoint(ec2, vpc_id: str, route_tables: dict) -> str:
    """VPC endpoint Gateway a S3, asociado a la route table privada."""
    service = CONFIG["endpoints"][0]["Service"]
    existing = next(
        (e for e in ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]},
                     {"Name": "service-name", "Values": [service]}]
        )["VpcEndpoints"]),
        None,
    )
    if existing:
        eid = existing["VpcEndpointId"]
        print(f"  VPC endpoint S3 ya existe: {eid}")
        return eid

    eid = ec2.create_vpc_endpoint(
        VpcId=vpc_id,
        ServiceName=service,
        VpcEndpointType="Gateway",
        RouteTableIds=[route_tables["private"]],
    )["VpcEndpoint"]["VpcEndpointId"]
    tag(ec2, eid, "course-s3-endpoint")
    print(f"  VPC endpoint S3 (Gateway) creado: {eid}")
    print(f"    asociado a route table privada → la subnet privada llega a S3 sin Internet")
    return eid


def summary(ec2, vpc_id: str):
    vpc = ec2.describe_vpcs(VpcIds=[vpc_id])["Vpcs"][0]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    rts = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["RouteTables"]
    igws = ec2.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    )["InternetGateways"]
    sgs = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["SecurityGroups"]
    endpoints = ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["VpcEndpoints"]

    print(f"  VPC:              {vpc_id} ({vpc['CidrBlock']})")
    print(f"  Subnets:          {len(subnets)} ({', '.join(s['CidrBlock'] for s in subnets)})")
    print(f"  Route tables:     {len(rts)}")
    print(f"  Internet Gateway: {len(igws)} ({'attached' if igws else 'none'})")
    print(f"  Security groups:  {len(sgs)} ({', '.join(s['GroupName'] for s in sgs if s['GroupName'] != 'default')})")
    print(f"  VPC endpoints:    {len(endpoints)} ({', '.join(e['ServiceName'].split('.')[-1] for e in endpoints)})")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Lab 07 — VPC: topología y cierre EC2 → S3 sin Internet ===\n")

    ec2 = make_client("ec2")

    print("1. VPC")
    vpc_id = create_vpc(ec2)

    print("\n2. Subredes (pública y privada en distintas AZs)")
    subnets = create_subnets(ec2, vpc_id)

    print("\n3. Internet Gateway")
    igw_id = create_igw(ec2, vpc_id)

    print("\n4. Route tables (la pública gana acceso a Internet vía ruta a IGW)")
    route_tables = create_route_tables(ec2, vpc_id, subnets, igw_id)

    print("\n5. Security Groups (referencia por SG, no por CIDR)")
    sgs = create_security_groups(ec2, vpc_id)

    print("\n6. VPC endpoint a S3 (cierre EC2 → S3 sin pasar por Internet)")
    create_s3_endpoint(ec2, vpc_id, route_tables)

    print("\n=== Resumen de la topología ===")
    summary(ec2, vpc_id)

    print(f"\nInspección manual:")
    print(f"  awslocal ec2 describe-vpcs --vpc-ids {vpc_id}")
    print(f"  awslocal ec2 describe-subnets --filters Name=vpc-id,Values={vpc_id}")
    print(f"  awslocal ec2 describe-route-tables --filters Name=vpc-id,Values={vpc_id}")
    print(f"  awslocal ec2 describe-vpc-endpoints --filters Name=vpc-id,Values={vpc_id}")


if __name__ == "__main__":
    main()
